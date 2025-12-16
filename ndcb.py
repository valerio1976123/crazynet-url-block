#!/usr/bin/env python3

from __future__ import annotations

import argparse
import concurrent.futures
import re
import sys
from pathlib import Path
from typing import List, Optional

from ndcb_core import Device, InventoryError, backup_one, load_inventory_raw, materialize_device


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
        devices_raw = load_inventory_raw(Path(args.inventory))
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
            devices.append(materialize_device(raw, idx=i))
    except InventoryError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    fail = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = [ex.submit(backup_one, d, output_dir, args.timeout) for d in devices]
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
