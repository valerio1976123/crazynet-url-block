from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(dt: datetime) -> str:
    # 2025-12-16T12:34:56Z
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write_text(path: str | Path, content: str) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, p)


def atomic_write_json(path: str | Path, obj: object) -> None:
    content = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(path, content)


_DEFAULT_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Cisco/Forti style
    (re.compile(r"(?im)^(.*\bpassword\s+)(\S+)(.*)$"), r"\1<REDACTED>\3"),
    (re.compile(r"(?im)^(.*\bsecret\s+)(\S+)(.*)$"), r"\1<REDACTED>\3"),
    (re.compile(r"(?im)^(.*\bkey\s+)(\S+)(.*)$"), r"\1<REDACTED>\3"),
    (re.compile(r"(?im)^(.*\bcommunity\s+)(\S+)(.*)$"), r"\1<REDACTED>\3"),
    # PAN-OS xml-ish
    (re.compile(r"(?is)(<password>)(.*?)(</password>)"), r"\1<REDACTED>\3"),
    (re.compile(r"(?is)(<api-key>)(.*?)(</api-key>)"), r"\1<REDACTED>\3"),
]


def redact(text: str, enabled: bool, extra_patterns: Iterable[str] | None = None) -> str:
    if not enabled:
        return text
    out = text
    for rx, repl in _DEFAULT_REDACT_PATTERNS:
        out = rx.sub(repl, out)
    if extra_patterns:
        for pattern in extra_patterns:
            rx = re.compile(pattern, flags=re.MULTILINE)
            out = rx.sub("<REDACTED>", out)
    return out

