"""RD-to-NAS Downloader — FastAPI application."""

from __future__ import annotations

import asyncio
import os
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db, rd_client
from .models import ErrorResponse, TorrentResponse

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))


async def poll_loop():
    """Background task: poll RD for torrent status changes."""
    await asyncio.sleep(5)  # Wait for server to start
    while True:
        try:
            torrents = db.list_torrents()
            for t in torrents:
                if t["status"] not in ("downloading",):
                    continue
                try:
                    info = await rd_client.torrent_info(t["rd_id"])
                except Exception:
                    continue

                new_status = info.get("status", "")
                name = t["name"] or info.get("filename", "")
                progress = info.get("progress", 0)

                # Status mapping
                if new_status in ("downloaded",):
                    # Select files, get download links
                    try:
                        await rd_client.select_files(t["rd_id"])
                        info = await rd_client.torrent_info(t["rd_id"])
                        links = info.get("links", [])
                        files = []
                        for link in links:
                            files.append({
                                "filename": link.split("/")[-1] or "unknown",
                                "filesize": 0,
                                "download_url": link,
                            })
                        db.insert_torrent_files(t["id"], files)
                        db.update_torrent_status(t["id"], "ready_to_download", name=name)
                    except Exception as e:
                        db.update_torrent_status(t["id"], "error", error=str(e), name=name)

                elif new_status in ("error", "virus", "dead", "magnet_error", "magnet_conversion"):
                    db.update_torrent_status(t["id"], "error", error=new_status, name=name)

                elif new_status in ("downloading", "queued", "waiting_files_selection"):
                    db.update_torrent_status(t["id"], "downloading", name=name)
                    if progress is not None:
                        # update progress column
                        conn = db.get_conn()
                        conn.execute(
                            "UPDATE torrents SET progress = ? WHERE id = ?",
                            (progress, t["id"]),
                        )
                        conn.commit()
                        conn.close()

                await asyncio.sleep(1)  # Rate limit: 1 req/sec

        except Exception:
            pass
        finally:
            await asyncio.sleep(POLL_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    # Verify RD API key on startup
    token = os.getenv("RD_API_KEY", "")
    if not token or token.startswith("your_"):
        print("WARNING: RD_API_KEY not configured! Set the env var to enable Real-Debrid.")
    else:
        try:
            user = await rd_client.user_info()
            print(f"Real-Debrid connected: {user.get('username', 'unknown')} ({user.get('type', 'unknown')})")
        except Exception as e:
            print(f"WARNING: Real-Debrid connection failed: {e}")

    # Start background poller
    task = asyncio.create_task(poll_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="RD-to-NAS Downloader",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from .torrents import router as torrents_router  # noqa: E402

app.include_router(torrents_router)


@app.get("/api/health")
async def health():
    token = os.getenv("RD_API_KEY", "")
    rd_ok = False
    if token and not token.startswith("your_"):
        try:
            await rd_client.user_info()
            rd_ok = True
        except Exception:
            pass

    return {
        "status": "ok",
        "rd_connected": rd_ok,
        "download_path": os.getenv("DOWNLOAD_PATH", "/downloads"),
    }
