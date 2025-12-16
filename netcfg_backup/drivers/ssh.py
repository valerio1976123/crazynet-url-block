from __future__ import annotations

from typing import Any

from netmiko import ConnectHandler

from ..models import Device
from .base import Driver


def _default_commands(platform: str) -> list[str]:
    p = platform.lower()
    if p in {"cisco", "cisco_ios", "ios"}:
        return ["terminal length 0", "show running-config"]
    if p in {"forti", "fortigate", "fortinet"}:
        # Nota: "show full-configuration" include più dettagli (anche sensibili).
        return ["config global", "show"]
    if p in {"mikrotik", "routeros", "mikrotik_routeros"}:
        return ["export hide-sensitive"]
    # fallback generico
    return ["show running-config"]


def _netmiko_device_type(platform: str, extras: dict[str, Any]) -> str:
    # Override esplicito
    if "netmiko_device_type" in extras:
        return str(extras["netmiko_device_type"])

    p = platform.lower()
    if p in {"cisco", "cisco_ios", "ios"}:
        return "cisco_ios"
    if p in {"forti", "fortigate", "fortinet"}:
        return "fortinet"
    if p in {"mikrotik", "routeros", "mikrotik_routeros"}:
        return "mikrotik_routeros"
    return p


class SSHDriver(Driver):
    def fetch_config(self, device: Device) -> tuple[str, str]:
        if not device.username or not device.password:
            raise ValueError(f"{device.name}: username/password mancanti per SSH")

        extras = device.extras or {}
        device_type = _netmiko_device_type(device.platform, extras)
        commands = extras.get("commands") or extras.get("command") or _default_commands(device.platform)
        if isinstance(commands, str):
            commands = [commands]
        if not isinstance(commands, list) or not all(isinstance(c, str) for c in commands):
            raise ValueError(f"{device.name}: 'commands' deve essere stringa o lista di stringhe")

        connect_args: dict[str, Any] = {
            "device_type": device_type,
            "host": device.host,
            "username": device.username,
            "password": device.password,
            "timeout": device.timeout_s,
        }
        if device.port:
            connect_args["port"] = device.port
        if device.enable_secret:
            connect_args["secret"] = device.enable_secret

        # Extra passthrough controllato
        for k in ("global_delay_factor", "fast_cli", "conn_timeout", "auth_timeout", "banner_timeout"):
            if k in extras:
                connect_args[k] = extras[k]

        use_timing = bool(extras.get("use_timing", False))

        with ConnectHandler(**connect_args) as conn:
            if device.enable_secret:
                try:
                    conn.enable()
                except Exception:
                    # Non tutti i device hanno enable; ignora se fallisce
                    pass

            outputs: list[str] = []
            for cmd in commands:
                if use_timing:
                    out = conn.send_command_timing(cmd)
                else:
                    out = conn.send_command(cmd)
                outputs.append(out.rstrip() + "\n")

        header = f"! device: {device.name}\n! platform: {device.platform}\n! host: {device.host}\n\n"
        return header + "\n".join(outputs), "cfg"

