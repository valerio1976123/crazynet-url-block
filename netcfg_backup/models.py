from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Device:
    name: str
    platform: str
    host: str
    method: str = "ssh"  # ssh | panos_api
    port: int | None = None
    username: str | None = None
    password: str | None = None
    enable_secret: str | None = None
    api_key: str | None = None
    verify_ssl: bool = True
    timeout_s: int = 30
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BackupResult:
    device: Device
    ok: bool
    collected_at_iso: str
    output_path: str | None = None
    latest_path: str | None = None
    metadata_path: str | None = None
    error: str | None = None

