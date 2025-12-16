from __future__ import annotations

import argparse
import sys

from .backup import backup_all
from .inventory import load_inventory


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="netcfg-backup",
        description="Backup configurazioni network device (Cisco, Palo Alto, FortiGate, MikroTik).",
    )
    p.add_argument("-i", "--inventory", default="inventory.yml", help="Path inventario YAML (default: inventory.yml)")
    p.add_argument("-o", "--output-dir", default="backups", help="Directory output (default: backups)")
    p.add_argument("-w", "--workers", type=int, default=4, help="Numero worker paralleli (default: 4)")
    p.add_argument("--no-redact", action="store_true", help="Non mascherare segreti (ATTENZIONE)")
    p.add_argument(
        "--redact-pattern",
        action="append",
        default=[],
        help="Regex extra da redigere (ripetibile). Sostituisce il match con <REDACTED>.",
    )
    p.add_argument(
        "--devices",
        default="",
        help="Lista device separati da virgola (filtra per name). Vuoto = tutti.",
    )
    p.add_argument("--dry-run", action="store_true", help="Valida inventario e mostra cosa farebbe")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv if argv is not None else sys.argv[1:])

    devices = load_inventory(ns.inventory)
    if ns.devices.strip():
        wanted = {x.strip() for x in ns.devices.split(",") if x.strip()}
        devices = [d for d in devices if d.name in wanted]

    if not devices:
        print("Nessun device da processare.")
        return 0

    if ns.dry_run:
        print(f"Inventario OK: {len(devices)} device")
        for d in devices:
            print(f"- {d.name} ({d.platform}) {d.host} method={d.method}")
        print(f"Output dir: {ns.output_dir}")
        return 0

    results = backup_all(
        devices,
        ns.output_dir,
        workers=ns.workers,
        redact_secrets=not ns.no_redact,
        redact_patterns=ns.redact_pattern or None,
    )

    ok = [r for r in results if r.ok]
    ko = [r for r in results if not r.ok]

    for r in results:
        if r.ok:
            print(f"[OK]  {r.device.name} -> {r.output_path}")
        else:
            print(f"[ERR] {r.device.name}: {r.error}")

    print(f"Totale: {len(results)} | OK: {len(ok)} | ERR: {len(ko)}")
    return 0 if not ko else 2

