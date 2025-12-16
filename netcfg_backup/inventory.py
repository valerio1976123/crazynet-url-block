from __future__ import annotations

import os
import re
from typing import Any

import yaml

from .models import Device

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def _repl(match: re.Match[str]) -> str:
            var = match.group(1)
            default = match.group(2)
            if var in os.environ:
                return os.environ[var]
            if default is not None:
                return default
            return ""

        return _ENV_PATTERN.sub(_repl, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def load_inventory(path: str) -> list[Device]:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    raw = _expand_env(raw)
    devices_raw = raw.get("devices", [])
    if not isinstance(devices_raw, list):
        raise ValueError("inventory: 'devices' deve essere una lista")

    devices: list[Device] = []
    for item in devices_raw:
        if not isinstance(item, dict):
            raise ValueError("inventory: ogni device deve essere un oggetto")
        item = dict(item)

        extras = item.pop("extras", None)
        if extras is None:
            extras = {}
        if not isinstance(extras, dict):
            raise ValueError(f"inventory: extras non valido per device={item.get('name')}")

        known_keys = {
            "name",
            "platform",
            "host",
            "method",
            "port",
            "username",
            "password",
            "enable_secret",
            "api_key",
            "verify_ssl",
            "timeout_s",
        }
        # Metti tutto ciò che non è chiave nota in extras
        for k in list(item.keys()):
            if k not in known_keys:
                extras[k] = item.pop(k)

        devices.append(
            Device(
                name=str(item["name"]),
                platform=str(item["platform"]),
                host=str(item["host"]),
                method=str(item.get("method", "ssh")),
                port=item.get("port"),
                username=item.get("username"),
                password=item.get("password"),
                enable_secret=item.get("enable_secret"),
                api_key=item.get("api_key"),
                verify_ssl=bool(item.get("verify_ssl", True)),
                timeout_s=int(item.get("timeout_s", 30)),
                extras=extras,
            )
        )

    return devices

