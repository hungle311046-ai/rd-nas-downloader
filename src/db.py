"""SQLite database setup and queries."""

from __future__ import annotations

import sqlite3
import os
from typing import Any

DB_PATH = os.getenv("DB_PATH", "data/state.db")


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS torrents (
        id TEXT PRIMARY KEY,
        rd_id TEXT NOT NULL,
        magnet TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        progress INTEGER DEFAULT 0,
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS torrent_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        torrent_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        filesize INTEGER DEFAULT 0,
        download_url TEXT,
        local_path TEXT,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (torrent_id) REFERENCES torrents(id)
    );
    """)
    conn.commit()
    conn.close()


def insert_torrent(
    torrent_id: str,
    rd_id: str,
    magnet: str,
    name: str,
    created_at: str,
) -> dict[str, Any]:
    conn = get_conn()
    conn.execute(
        """INSERT INTO torrents (id, rd_id, magnet, name, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'downloading', ?, ?)""",
        (torrent_id, rd_id, magnet, name, created_at, created_at),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM torrents WHERE id = ?", (torrent_id,)).fetchone()
    conn.close()
    return dict(row)


def get_torrent(torrent_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM torrents WHERE id = ?", (torrent_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_torrent_by_hash(magnet_hash: str) -> dict[str, Any] | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM torrents WHERE magnet LIKE ?", (f"%{magnet_hash}%",)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_torrents() -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM torrents ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_torrent_status(
    torrent_id: str, status: str, error: str | None = None, name: str | None = None
) -> None:
    from .models import utcnow

    conn = get_conn()
    parts = ["status = ?", "updated_at = ?"]
    params: list[Any] = [status, utcnow()]
    if error is not None:
        parts.append("error = ?")
        params.append(error)
    if name is not None:
        parts.append("name = ?")
        params.append(name)
    query = f"UPDATE torrents SET {', '.join(parts)} WHERE id = ?"
    params.append(torrent_id)
    conn.execute(query, params)
    conn.commit()
    conn.close()


def insert_torrent_files(
    torrent_id: str, files: list[dict[str, Any]]
) -> None:
    conn = get_conn()
    for f in files:
        conn.execute(
            """INSERT INTO torrent_files (torrent_id, filename, filesize, download_url, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (torrent_id, f.get("filename", ""), f.get("filesize", 0), f.get("download_url", "")),
        )
    conn.commit()
    conn.close()


def get_torrent_files(torrent_id: str) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM torrent_files WHERE torrent_id = ?", (torrent_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
