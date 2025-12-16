from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

from .drivers.registry import get_driver
from .models import BackupResult, Device
from .utils import atomic_write_json, atomic_write_text, iso_z, now_utc, redact, sha256_text


_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_.-]+")


def _safe_device_dir(name: str) -> str:
    name = name.strip() or "device"
    return _SAFE_NAME.sub("_", name)


def backup_one(
    device: Device,
    output_dir: str,
    *,
    redact_secrets: bool = True,
    redact_patterns: Iterable[str] | None = None,
) -> BackupResult:
    collected_at = now_utc()
    collected_iso = iso_z(collected_at)
    try:
        driver = get_driver(device)
        cfg, ext = driver.fetch_config(device)
        cfg = redact(cfg, enabled=redact_secrets, extra_patterns=redact_patterns)

        root = Path(output_dir)
        dev_dir = root / _safe_device_dir(device.name) / collected_at.strftime("%Y") / collected_at.strftime("%m")
        filename = collected_at.strftime("%Y-%m-%d_%H%M%S") + f".{ext}"
        out_path = dev_dir / filename
        latest_path = root / _safe_device_dir(device.name) / f"latest.{ext}"
        meta_path = out_path.with_suffix(out_path.suffix + ".metadata.json")

        atomic_write_text(out_path, cfg if cfg.endswith("\n") else cfg + "\n")
        atomic_write_text(latest_path, cfg if cfg.endswith("\n") else cfg + "\n")

        metadata = {
            "device": {
                "name": device.name,
                "platform": device.platform,
                "host": device.host,
                "method": device.method,
            },
            "collected_at": collected_iso,
            "output": {
                "path": str(out_path),
                "latest_path": str(latest_path),
                "sha256": sha256_text(cfg),
                "extension": ext,
                "redacted": bool(redact_secrets),
            },
        }
        atomic_write_json(meta_path, metadata)

        return BackupResult(
            device=device,
            ok=True,
            collected_at_iso=collected_iso,
            output_path=str(out_path),
            latest_path=str(latest_path),
            metadata_path=str(meta_path),
        )
    except Exception as e:
        return BackupResult(device=device, ok=False, collected_at_iso=collected_iso, error=str(e))


def backup_all(
    devices: list[Device],
    output_dir: str,
    *,
    workers: int = 4,
    redact_secrets: bool = True,
    redact_patterns: Iterable[str] | None = None,
) -> list[BackupResult]:
    if workers <= 1:
        return [
            backup_one(d, output_dir, redact_secrets=redact_secrets, redact_patterns=redact_patterns)
            for d in devices
        ]

    results: list[BackupResult] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(
                backup_one,
                d,
                output_dir,
                redact_secrets=redact_secrets,
                redact_patterns=redact_patterns,
            ): d
            for d in devices
        }
        for fut in as_completed(futs):
            results.append(fut.result())
    # Ordine stabile per nome device
    results.sort(key=lambda r: r.device.name)
    return results

