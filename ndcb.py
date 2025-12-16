#!/usr/bin/env python3

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import os
import re
import sys
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


def _expand_env(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        if var not in os.environ:
            raise InventoryError(f"Variabile d'ambiente mancante: {var}")
        return os.environ[var]

    return ENV_PATTERN.sub(repl, value)


def _materialize_device(raw: Dict[str, Any], idx: int) -> Device:
    raw = {k: _expand_env(v) for k, v in raw.items()}

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


def _load_inventory(path: Path) -> List[Dict[str, Any]]:
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


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S%z")


def _sanitize_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("_")


def _default_commands(vendor: str) -> List[str]:
    v = vendor.lower()
    if v in {"cisco_ios", "cisco_xe", "cisco"}:
        return ["terminal length 0", "show running-config"]
    if v in {"fortinet", "fortigate", "forti"}:
        # Nota: in molti casi non pagina; se paginasse, conviene override via 'commands'
        return ["show full-configuration"]
    if v in {"mikrotik", "mikrotik_routeros", "routeros"}:
        # Evita di salvare segreti in chiaro
        return ["export hide-sensitive"]
    if v in {"paloalto_panos", "panos", "paloalto"}:
        return ["show config running"]
    # fallback: prova show running-config
    return ["show running-config"]


def _backup_via_ssh(dev: Device, timeout_s: int) -> str:
    if not dev.username or dev.password is None:
        raise InventoryError(f"Credenziali mancanti per SSH su {dev.name} ({dev.host})")

    device_type = dev.vendor
    # Normalizza alias comuni
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

    commands = dev.commands or _default_commands(dev.vendor)

    with ConnectHandler(**params) as conn:
        # Alcuni device gradiscono entering enable; lasciamo al default di netmiko
        outputs: List[str] = []
        for cmd in commands:
            # Per comandi lunghi/interactive, timing e' piu' robusto
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
        f"# collected_at: {_timestamp()}\n\n"
    )
    return header + "\n".join(outputs)


def _backup_panos_api(dev: Device, timeout_s: int) -> str:
    if not dev.api_key:
        raise InventoryError(f"api_key mancante per panos_api su {dev.name} ({dev.host})")

    # PAN-OS API: export configuration
    # https://<fw>/api/?type=export&category=configuration&key=<key>
    url = f"https://{dev.host}/api/"
    params = {"type": "export", "category": "configuration", "key": dev.api_key}

    resp = requests.get(url, params=params, timeout=timeout_s, verify=dev.verify_tls)
    if resp.status_code != 200 or not resp.text.strip():
        raise RuntimeError(f"PAN-OS API export fallito: HTTP {resp.status_code}")

    header = (
        f"<!-- ndcb backup -->\n"
        f"<!-- name: {dev.name} -->\n"
        f"<!-- host: {dev.host} -->\n"
        f"<!-- vendor: {dev.vendor} -->\n"
        f"<!-- transport: panos_api -->\n"
        f"<!-- collected_at: {_timestamp()} -->\n\n"
    )
    return header + resp.text


def _write_backup(output_dir: Path, dev: Device, content: str, suffix: str) -> Path:
    ts = _timestamp()
    name_dir = output_dir / _sanitize_filename(dev.name)
    name_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{_sanitize_filename(dev.name)}__{_sanitize_filename(dev.host)}__{_sanitize_filename(dev.vendor)}__{ts}.{suffix}"
    path = name_dir / filename
    path.write_text(content, encoding="utf-8", errors="replace")
    return path


def _backup_one(dev: Device, output_dir: Path, timeout_s: int) -> Tuple[Device, Optional[Path], Optional[str]]:
    try:
        if dev.transport.lower() in {"ssh", "netmiko"}:
            content = _backup_via_ssh(dev, timeout_s=timeout_s)
            suffix = "cfg"
        elif dev.transport.lower() in {"panos_api", "pan_api", "paloalto_api"}:
            content = _backup_panos_api(dev, timeout_s=timeout_s)
            suffix = "xml"
        else:
            raise InventoryError(f"Transport non supportato: {dev.transport}")

        path = _write_backup(output_dir, dev, content, suffix=suffix)
        return dev, path, None
    except Exception as e:
        return dev, None, str(e)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ndcb",
        description="Network Device Config Backup (Cisco / Palo Alto / Forti / MikroTik)",
    )
    parser.add_argument("--inventory", "-i", default="inventory.yml", help="Path inventario YAML")
    parser.add_argument("--output-dir", "-o", default="backups", help="Directory output backup")
    parser.add_argument("--workers", "-w", type=int, default=6, help="Numero thread paralleli")
    parser.add_argument("--timeout", "-t", type=int, default=60, help="Timeout secondi per device")
    parser.add_argument(
        "--match",
        default=None,
        help="Regex per filtrare device per name/host/vendor",
    )
    args = parser.parse_args(argv)

    try:
        devices_raw = _load_inventory(Path(args.inventory))
    except InventoryError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if args.match:
        rx = re.compile(args.match)
        devices_raw = [
            d
            for d in devices_raw
            if rx.search(str(d.get("name", "")))
            or rx.search(str(d.get("host", "")))
            or rx.search(str(d.get("vendor", "")))
        ]

    if not devices_raw:
        print("Nessun device selezionato.", file=sys.stderr)
        return 2

    # Ora espandiamo le variabili d'ambiente solo per i device selezionati.
    devices: List[Device] = []
    try:
        for i, raw in enumerate(devices_raw):
            devices.append(_materialize_device(raw, idx=i))
    except InventoryError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    fail = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = [ex.submit(_backup_one, d, output_dir, args.timeout) for d in devices]
        for fut in concurrent.futures.as_completed(futures):
            dev, path, err = fut.result()
            if err:
                fail += 1
                print(f"FAIL {dev.name} ({dev.host}) [{dev.vendor}/{dev.transport}]: {err}", file=sys.stderr)
            else:
                ok += 1
                print(f"OK   {dev.name} ({dev.host}) -> {path}")

    print(f"\nRisultato: OK={ok} FAIL={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
