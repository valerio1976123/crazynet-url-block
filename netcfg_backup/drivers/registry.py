from __future__ import annotations

from ..models import Device
from .base import Driver
from .panos_api import PanosAPIDriver
from .ssh import SSHDriver


def get_driver(device: Device) -> Driver:
    method = (device.method or "ssh").lower()
    platform = (device.platform or "").lower()

    if method in {"panos_api", "api", "paloalto_api"}:
        return PanosAPIDriver()
    if platform in {"paloalto", "panos", "pan-os"} and method != "ssh":
        return PanosAPIDriver()
    return SSHDriver()

