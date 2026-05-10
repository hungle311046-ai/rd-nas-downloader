"""Real-Debrid REST API client."""

from __future__ import annotations

import os
from typing import Any

import httpx

RD_BASE = "https://api.real-debrid.com/rest/1.0"

# Rate limiting: max 1 request per second
# httpx doesn't easily support this with limits directly, so we use a semaphore
# in the poller. For single calls, no rate limit needed.


def _headers() -> dict[str, str]:
    token = os.getenv("RD_API_KEY", "")
    return {"Authorization": f"Bearer {token}"}


async def add_magnet(magnet: str) -> dict[str, Any]:
    """Submit a magnet link to Real-Debrid. Returns {"id": "...", "uri": "..."}."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RD_BASE}/torrents/addMagnet",
            headers=_headers(),
            data={"magnet": magnet},
        )
        resp.raise_for_status()
        return resp.json()


async def torrent_info(rd_id: str) -> dict[str, Any]:
    """Get torrent info from Real-Debrid."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{RD_BASE}/torrents/info/{rd_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def select_files(rd_id: str, files: str = "all") -> None:
    """Select all files for a torrent."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{RD_BASE}/torrents/selectFiles/{rd_id}",
            headers=_headers(),
            data={"files": files},
        )
        resp.raise_for_status()


async def unrestrict_link(link: str) -> dict[str, Any]:
    """Convert a hoster link to a direct download URL."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{RD_BASE}/unrestrict/link",
            headers=_headers(),
            data={"link": link},
        )
        resp.raise_for_status()
        return resp.json()


async def delete_torrent(rd_id: str) -> None:
    """Remove a torrent from Real-Debrid."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{RD_BASE}/torrents/delete/{rd_id}",
            headers=_headers(),
        )
        resp.raise_for_status()


async def user_info() -> dict[str, Any]:
    """Get user info (verifies API key)."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{RD_BASE}/user",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
