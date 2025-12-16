from __future__ import annotations

from pathlib import Path


def default_db_path() -> Path:
    # Local-first: keep DB inside repo by default.
    return Path("data") / "expenses.sqlite"


def default_rules_path() -> Path:
    return Path("data") / "rules.json"
