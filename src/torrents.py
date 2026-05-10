"""Torrent API router — submit, list, get status."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from . import db, models, rd_client

router = APIRouter(prefix="/api/torrents", tags=["torrents"])


def _extract_hash(magnet: str) -> str | None:
    m = re.search(r"btih:([a-zA-Z0-9]+)", magnet)
    return m.group(1) if m else None


def _to_response(row: dict) -> models.TorrentResponse:
    files = [
        models.TorrentFile(
            id=f["id"],
            filename=f["filename"],
            filesize=f.get("filesize", 0),
            download_url=f.get("download_url"),
            local_path=f.get("local_path"),
            status=f.get("status", "pending"),
        )
        for f in db.get_torrent_files(row["id"])
    ]
    return models.TorrentResponse(
        id=row["id"],
        rd_id=row.get("rd_id", ""),
        magnet=row.get("magnet", ""),
        name=row.get("name", ""),
        status=row.get("status", "pending"),
        progress=row.get("progress", 0),
        files=files,
        error=row.get("error"),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


@router.post("", status_code=201, response_model=models.TorrentResponse)
async def submit_magnet(req: models.MagnetRequest):
    """Submit a magnet link to Real-Debrid."""
    magnet = req.magnet.strip()

    # Duplicate check
    magnet_hash = _extract_hash(magnet)
    if magnet_hash:
        existing = db.get_torrent_by_hash(magnet_hash)
        if existing:
            return _to_response(existing)

    # Submit to Real-Debrid
    try:
        result = await rd_client.add_magnet(magnet)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Real-Debrid API error: {e}",
        )

    rd_id = result.get("id", "")
    if not rd_id:
        raise HTTPException(status_code=502, detail="Real-Debrid returned no torrent ID")

    # Try to get name immediately (may be empty for newly submitted magnet)
    name = ""
    try:
        info = await rd_client.torrent_info(rd_id)
    except Exception:
        pass
    else:
        name = info.get("filename", "")

    torrent_id = models.new_id()
    now = models.utcnow()
    row = db.insert_torrent(torrent_id, rd_id, magnet, name, now)

    return _to_response(row)


@router.get("", response_model=models.TorrentListResponse)
async def list_torrents():
    """List all torrents."""
    rows = db.list_torrents()
    torrents = [_to_response(r) for r in rows]
    return models.TorrentListResponse(torrents=torrents, total=len(torrents))


@router.get("/{torrent_id}", response_model=models.TorrentResponse)
async def get_torrent(torrent_id: str):
    """Get a single torrent by ID."""
    row = db.get_torrent(torrent_id)
    if not row:
        raise HTTPException(status_code=404, detail="Torrent not found")
    return _to_response(row)


@router.delete("/{torrent_id}", status_code=204)
async def delete_torrent(torrent_id: str):
    """Delete a torrent from RD and local DB."""
    row = db.get_torrent(torrent_id)
    if not row:
        raise HTTPException(status_code=404, detail="Torrent not found")

    try:
        await rd_client.delete_torrent(row["rd_id"])
    except Exception:
        pass  # RD may have already removed it

    db.update_torrent_status(torrent_id, "done", error="deleted by user")
