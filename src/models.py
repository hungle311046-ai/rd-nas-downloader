"""Pydantic models for request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAGNET_REGEX = r"^magnet:\?xt=urn:[a-zA-Z0-9]+:[a-zA-Z0-9]+"


class MagnetRequest(BaseModel):
    magnet: str = Field(..., min_length=20, max_length=4096)

    @field_validator("magnet")
    @classmethod
    def validate_magnet(cls, v: str) -> str:
        import re

        if not re.match(MAGNET_REGEX, v):
            raise ValueError("Invalid magnet link format")
        return v


TorrentStatus = Literal[
    "pending",
    "downloading",
    "downloaded",
    "ready_to_download",
    "downloading_to_nas",
    "done",
    "error",
]


class TorrentFile(BaseModel):
    id: int
    filename: str
    filesize: int = 0
    download_url: str | None = None
    local_path: str | None = None
    status: str = "pending"


class TorrentResponse(BaseModel):
    id: str
    rd_id: str
    magnet: str
    name: str
    status: TorrentStatus
    progress: int = 0
    files: list[TorrentFile] = []
    error: str | None = None
    created_at: str
    updated_at: str


class TorrentListResponse(BaseModel):
    torrents: list[TorrentResponse]
    total: int


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
