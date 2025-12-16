#!/usr/bin/env python3

from __future__ import annotations

import concurrent.futures
import queue
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ndcb_core import Device, InventoryError, backup_one, load_inventory_raw, materialize_device


@dataclass(frozen=True)
class UiDevice:
    idx: int
    raw: Dict
    name: str
    host: str
    vendor: str
    transport: str


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NDCB - Network Device Config Backup")
        self.geometry("1050x680")

        self._inventory_path = tk.StringVar(value=str(Path("inventory.yml").resolve()))
        self._output_dir = tk.StringVar(value=str(Path("backups").resolve()))
        self._timeout = tk.IntVar(value=60)
        self._workers = tk.IntVar(value=6)
        self._filter = tk.StringVar(value="")

        self._devices_raw: List[Dict] = []
        self._ui_devices: List[UiDevice] = []

        self._running = False
        self._stop_event = threading.Event()
        self._msg_q: queue.Queue[Tuple[str, str]] = queue.Queue()

        self._build_ui()
        self._bind_events()

        # attempt initial load
        self.after(50, self.load_inventory)
        self.after(100, self._drain_messages)

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 6}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Inventory").grid(row=0, column=0, sticky="w")
        inv_entry = ttk.Entry(top, textvariable=self._inventory_path)
        inv_entry.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(top, text="Browse...", command=self.browse_inventory).grid(row=0, column=2)
        ttk.Button(top, text="Load", command=self.load_inventory).grid(row=0, column=3, padx=(6, 0))

        ttk.Label(top, text="Output dir").grid(row=1, column=0, sticky="w")
        out_entry = ttk.Entry(top, textvariable=self._output_dir)
        out_entry.grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(top, text="Browse...", command=self.browse_output).grid(row=1, column=2)

        ttk.Label(top, text="Timeout (s)").grid(row=0, column=4, sticky="e", padx=(18, 0))
        ttk.Spinbox(top, from_=5, to=600, textvariable=self._timeout, width=7).grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(top, text="Workers").grid(row=1, column=4, sticky="e", padx=(18, 0))
        ttk.Spinbox(top, from_=1, to=64, textvariable=self._workers, width=7).grid(row=1, column=5, sticky="w", padx=6)

        top.columnconfigure(1, weight=1)

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, **pad)

        toolbar = ttk.Frame(mid)
        toolbar.pack(fill="x")

        ttk.Label(toolbar, text="Filter (regex)").pack(side="left")
        filt = ttk.Entry(toolbar, textvariable=self._filter)
        filt.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(toolbar, text="Apply", command=self.apply_filter).pack(side="left")
        ttk.Button(toolbar, text="Clear", command=self.clear_filter).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Select all", command=self.select_all).pack(side="right")
        ttk.Button(toolbar, text="Select none", command=self.select_none).pack(side="right", padx=(0, 6))

        table_frame = ttk.Frame(mid)
        table_frame.pack(fill="both", expand=True, pady=(8, 8))

        self.tree = ttk.Treeview(
            table_frame,
            columns=("name", "host", "vendor", "transport"),
            show="headings",
            selectmode="extended",
        )
        for col, w in [("name", 220), ("host", 160), ("vendor", 180), ("transport", 120)]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", **pad)

        self.run_btn = ttk.Button(bottom, text="Run backup", command=self.run_backup)
        self.run_btn.pack(side="left")

        self.stop_btn = ttk.Button(bottom, text="Stop", command=self.stop_backup, state="disabled")
        self.stop_btn.pack(side="left", padx=(6, 0))

        self.status = tk.StringVar(value="Ready")
        ttk.Label(bottom, textvariable=self.status).pack(side="left", padx=(12, 0))

        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=False, padx=8, pady=(0, 10))
        ttk.Label(log_frame, text="Log").pack(anchor="w")

        self.log = tk.Text(log_frame, height=10, wrap="none")
        self.log.pack(fill="both", expand=True)

    def _bind_events(self) -> None:
        self.bind("<Control-o>", lambda _e: self.browse_inventory())
        self.bind("<Control-r>", lambda _e: self.run_backup())
        self.bind("<Escape>", lambda _e: self.stop_backup())
        self._filter.trace_add("write", lambda *_: None)

    def log_line(self, msg: str) -> None:
        self.log.insert("end", msg.rstrip("\n") + "\n")
        self.log.see("end")

    def browse_inventory(self) -> None:
        path = filedialog.askopenfilename(
            title="Select inventory.yml",
            filetypes=[("YAML", "*.yml *.yaml"), ("All files", "*")],
        )
        if path:
            self._inventory_path.set(path)
            self.load_inventory()

    def browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self._output_dir.set(path)

    def load_inventory(self) -> None:
        try:
            p = Path(self._inventory_path.get()).expanduser()
            self._devices_raw = load_inventory_raw(p)
            self.status.set(f"Loaded {len(self._devices_raw)} devices")
            self.log_line(f"Loaded inventory: {p} ({len(self._devices_raw)} devices)")
            self.apply_filter()
        except Exception as e:
            messagebox.showerror("Inventory error", str(e))
            self.status.set("Inventory error")

    def _compute_ui_devices(self, rx: Optional[re.Pattern[str]]) -> List[UiDevice]:
        out: List[UiDevice] = []
        for i, d in enumerate(self._devices_raw):
            name = str(d.get("name", ""))
            host = str(d.get("host", ""))
            vendor = str(d.get("vendor", ""))
            transport = str(d.get("transport", "ssh"))
            if rx is not None:
                if not (rx.search(name) or rx.search(host) or rx.search(vendor) or rx.search(transport)):
                    continue
            out.append(UiDevice(idx=i, raw=d, name=name, host=host, vendor=vendor, transport=transport))
        return out

    def apply_filter(self) -> None:
        expr = self._filter.get().strip()
        rx: Optional[re.Pattern[str]]
        if not expr:
            rx = None
        else:
            try:
                rx = re.compile(expr)
            except re.error as e:
                messagebox.showerror("Invalid regex", str(e))
                return

        self._ui_devices = self._compute_ui_devices(rx)
        self._refresh_tree()
        self.status.set(f"Showing {len(self._ui_devices)} / {len(self._devices_raw)}")

    def clear_filter(self) -> None:
        self._filter.set("")
        self.apply_filter()

    def _refresh_tree(self) -> None:
        for item in self.tree.get_children(""):
            self.tree.delete(item)

        for ud in self._ui_devices:
            # Use the raw index as stable iid
            self.tree.insert("", "end", iid=str(ud.idx), values=(ud.name, ud.host, ud.vendor, ud.transport))

    def select_all(self) -> None:
        self.tree.selection_set(self.tree.get_children(""))

    def select_none(self) -> None:
        self.tree.selection_remove(self.tree.get_children(""))

    def _selected_raw_devices(self) -> List[Dict]:
        sel = self.tree.selection()
        if not sel:
            return []
        idxs = [int(i) for i in sel]
        return [self._devices_raw[i] for i in idxs]

    def run_backup(self) -> None:
        if self._running:
            return

        selected_raw = self._selected_raw_devices()
        if not selected_raw:
            messagebox.showwarning("No selection", "Select one or more devices.")
            return

        out_dir = Path(self._output_dir.get()).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        timeout = int(self._timeout.get())
        workers = max(1, int(self._workers.get()))

        # materialize only selected (expands env)
        devices: List[Device] = []
        try:
            for i, raw in enumerate(selected_raw):
                devices.append(materialize_device(raw, idx=i))
        except InventoryError as e:
            messagebox.showerror("Inventory error", str(e))
            return

        self._running = True
        self._stop_event.clear()
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.set(f"Running backups: {len(devices)} devices")
        self.log_line(f"Starting backup: {len(devices)} devices -> {out_dir}")

        threading.Thread(
            target=self._backup_worker,
            args=(devices, out_dir, timeout, workers),
            daemon=True,
        ).start()

    def stop_backup(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        self.log_line("Stop requested: waiting for running tasks to finish...")

    def _backup_worker(self, devices: List[Device], out_dir: Path, timeout: int, workers: int) -> None:
        ok = 0
        fail = 0
        total = len(devices)

        def emit(level: str, msg: str) -> None:
            self._msg_q.put((level, msg))

        emit("info", f"Workers={workers} Timeout={timeout}s")

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futures: List[concurrent.futures.Future] = []
            for d in devices:
                if self._stop_event.is_set():
                    break
                futures.append(ex.submit(backup_one, d, out_dir, timeout))

            for fut in concurrent.futures.as_completed(futures):
                dev, path, err = fut.result()
                if err:
                    fail += 1
                    emit("error", f"FAIL {dev.name} ({dev.host}) [{dev.vendor}/{dev.transport}]: {err}")
                else:
                    ok += 1
                    emit("ok", f"OK   {dev.name} ({dev.host}) -> {path}")
                emit("status", f"Progress: {ok + fail}/{total} OK={ok} FAIL={fail}")

        emit("done", f"Done. OK={ok} FAIL={fail}")

    def _drain_messages(self) -> None:
        try:
            while True:
                level, msg = self._msg_q.get_nowait()
                if level in {"ok", "info", "error", "done"}:
                    self.log_line(msg)
                if level in {"status", "done"}:
                    self.status.set(msg)
                if level == "done":
                    self._running = False
                    self.run_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
        except queue.Empty:
            pass
        finally:
            self.after(120, self._drain_messages)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
