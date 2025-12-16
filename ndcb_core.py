from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from netmiko import ConnectHandler

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


class InventoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Device:
    name: str
    host: str
    vendor: str
    transport: str  # ssh | panos_api
    username: Optional[str] = None
    password: Optional[str] = None
    port: int = 22
    commands: Optional[List[str]] = None

    # Palo Alto API
    api_key: Optional[str] = None
    verify_tls: bool = True


def expand_env(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        if var not in os.environ:
            raise InventoryError(f"Variabile d'ambiente mancante: {var}")
        return os.environ[var]

    return ENV_PATTERN.sub(repl, value)


def materialize_device(raw: Dict[str, Any], idx: int) -> Device:
    raw = {k: expand_env(v) for k, v in raw.items()}

    name = str(raw.get("name") or "").strip()
    host = str(raw.get("host") or "").strip()
    vendor = str(raw.get("vendor") or "").strip()
    transport = str(raw.get("transport") or "ssh").strip()

    if not name or not host or not vendor:
        raise InventoryError(f"Inventario invalido: devices[{idx}] richiede name/host/vendor")

    port = int(raw.get("port") or 22)
    commands = raw.get("commands")
    if commands is not None and not isinstance(commands, list):
        raise InventoryError(f"Inventario invalido: devices[{idx}].commands deve essere una lista")

    verify_tls_raw = raw.get("verify_tls", True)
    if isinstance(verify_tls_raw, str):
        verify_tls = verify_tls_raw.strip().lower() not in {"0", "false", "no", "off"}
    else:
        verify_tls = bool(verify_tls_raw)

    return Device(
        name=name,
        host=host,
        vendor=vendor,
        transport=transport,
        username=raw.get("username"),
        password=raw.get("password"),
        port=port,
        commands=commands,
        api_key=raw.get("api_key"),
        verify_tls=verify_tls,
    )


def load_inventory_raw(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise InventoryError(f"Inventario non trovato: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    devices_raw = data.get("devices")
    if not isinstance(devices_raw, list) or not devices_raw:
        raise InventoryError("Inventario invalido: manca 'devices' (lista)")

    devices: List[Dict[str, Any]] = []
    for i, raw in enumerate(devices_raw):
        if not isinstance(raw, dict):
            raise InventoryError(f"Inventario invalido: devices[{i}] non e' un oggetto")
        # Non espandiamo ${VAR} qui: lo facciamo solo per i device selezionati.
        devices.append(raw)

    return devices


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S%z")


def sanitize_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("_")


def default_commands(vendor: str) -> List[str]:
    v = vendor.lower()
    if v in {"cisco_ios", "cisco_xe", "cisco"}:
        return ["terminal length 0", "show running-config"]
    if v in {"fortinet", "fortigate", "forti"}:
        return ["show full-configuration"]
    if v in {"mikrotik", "mikrotik_routeros", "routeros"}:
        return ["export hide-sensitive"]
    if v in {"paloalto_panos", "panos", "paloalto"}:
        return ["show config running"]
    return ["show running-config"]


def backup_via_ssh(dev: Device, timeout_s: int) -> str:
    if not dev.username or dev.password is None:
        raise InventoryError(f"Credenziali mancanti per SSH su {dev.name} ({dev.host})")

    device_type = dev.vendor
    if dev.vendor.lower() in {"fortigate", "forti"}:
        device_type = "fortinet"
    if dev.vendor.lower() in {"mikrotik", "routeros"}:
        device_type = "mikrotik_routeros"
    if dev.vendor.lower() in {"panos", "paloalto"}:
        device_type = "paloalto_panos"

    params: Dict[str, Any] = {
        "device_type": device_type,
        "host": dev.host,
        "username": dev.username,
        "password": dev.password,
        "port": dev.port,
        "conn_timeout": timeout_s,
        "banner_timeout": timeout_s,
        "auth_timeout": timeout_s,
        "timeout": timeout_s,
        "fast_cli": False,
    }

    commands = dev.commands or default_commands(dev.vendor)

    with ConnectHandler(**params) as conn:
        outputs: List[str] = []
        for cmd in commands:
            if dev.vendor.lower() in {"mikrotik", "mikrotik_routeros", "routeros"}:
                out = conn.send_command_timing(cmd, read_timeout=timeout_s)
            else:
                out = conn.send_command(cmd, read_timeout=timeout_s)
            outputs.append(f"$ {cmd}\n{out}\n")

    header = (
        f"# ndcb backup\n"
        f"# name: {dev.name}\n"
        f"# host: {dev.host}\n"
        f"# vendor: {dev.vendor}\n"
        f"# transport: ssh\n"
        f"# collected_at: {timestamp()}\n\n"
    )
    return header + "\n".join(outputs)


def backup_panos_api(dev: Device, timeout_s: int) -> str:
    if not dev.api_key:
        raise InventoryError(f"api_key mancante per panos_api su {dev.name} ({dev.host})")

    url = f"https://{dev.host}/api/"
    params = {"type": "export", "category": "configuration", "key": dev.api_key}

    resp = requests.get(url, params=params, timeout=timeout_s, verify=dev.verify_tls)
    if resp.status_code != 200 or not resp.text.strip():
        raise RuntimeError(f"PAN-OS API export fallito: HTTP {resp.status_code}")

    header = (
        "<!-- ndcb backup -->\n"
        f"<!-- name: {dev.name} -->\n"
        f"<!-- host: {dev.host} -->\n"
        f"<!-- vendor: {dev.vendor} -->\n"
        "<!-- transport: panos_api -->\n"
        f"<!-- collected_at: {timestamp()} -->\n\n"
    )
    return header + resp.text


def write_backup(output_dir: Path, dev: Device, content: str, suffix: str) -> Path:
    ts = timestamp()
    name_dir = output_dir / sanitize_filename(dev.name)
    name_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        f"{sanitize_filename(dev.name)}__{sanitize_filename(dev.host)}__{sanitize_filename(dev.vendor)}__{ts}.{suffix}"
    )
    path = name_dir / filename
    path.write_text(content, encoding="utf-8", errors="replace")
    return path


def backup_one(dev: Device, output_dir: Path, timeout_s: int) -> Tuple[Device, Optional[Path], Optional[str]]:
    try:
        if dev.transport.lower() in {"ssh", "netmiko"}:
            content = backup_via_ssh(dev, timeout_s=timeout_s)
            suffix = "cfg"
        elif dev.transport.lower() in {"panos_api", "pan_api", "paloalto_api"}:
            content = backup_panos_api(dev, timeout_s=timeout_s)
            suffix = "xml"
        else:
            raise InventoryError(f"Transport non supportato: {dev.transport}")

        path = write_backup(output_dir, dev, content, suffix=suffix)
        return dev, path, None
    except Exception as e:
        return dev, None, str(e)
