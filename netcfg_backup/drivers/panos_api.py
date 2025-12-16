from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET

import requests

from ..models import Device
from .base import Driver


def _base_url(device: Device) -> str:
    extras = device.extras or {}
    if "base_url" in extras:
        return str(extras["base_url"]).rstrip("/")
    scheme = str(extras.get("scheme", "https"))
    host = device.host
    # Se l'host include già scheme, non forzare
    if "://" in host:
        return host.rstrip("/")
    if device.port:
        return f"{scheme}://{host}:{device.port}"
    return f"{scheme}://{host}"


def _get_api_key(device: Device, base_url: str) -> str:
    if device.api_key:
        return device.api_key
    if not device.username or not device.password:
        raise ValueError(f"{device.name}: api_key oppure username/password richiesti per PAN-OS API")
    params = {
        "type": "keygen",
        "user": device.username,
        "password": device.password,
    }
    r = requests.get(
        f"{base_url}/api/",
        params=params,
        timeout=device.timeout_s,
        verify=device.verify_ssl,
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)
    key_el = root.find(".//key")
    if key_el is None or not key_el.text:
        raise ValueError(f"{device.name}: impossibile estrarre api key dalla risposta")
    return key_el.text.strip()


class PanosAPIDriver(Driver):
    def fetch_config(self, device: Device) -> tuple[str, str]:
        base_url = _base_url(device)
        key = _get_api_key(device, base_url)

        params = {
            "type": "export",
            "category": "configuration",
            "key": key,
        }
        r = requests.get(
            f"{base_url}/api/",
            params=params,
            timeout=device.timeout_s,
            verify=device.verify_ssl,
        )
        r.raise_for_status()

        # L'export configuration normalmente restituisce direttamente XML
        text = r.text
        # A volte ritorna un wrapper XML con <response status="success"><result>...</result></response>
        # Proviamo a srotolare se è quel formato.
        try:
            root = ET.fromstring(text)
            if root.tag == "response":
                result_el = root.find(".//result")
                if result_el is not None and result_el.text:
                    text = result_el.text.strip()
        except ET.ParseError:
            pass

        header = (
            f"<!-- device: {device.name} -->\n"
            f"<!-- platform: {device.platform} -->\n"
            f"<!-- base_url: {urllib.parse.urlsplit(base_url).geturl()} -->\n"
        )
        if not text.lstrip().startswith("<"):
            # Se non sembra XML, salva comunque il payload grezzo
            return header + "\n" + text, "txt"
        return header + "\n" + text, "xml"

