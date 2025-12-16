from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .rules import Rule, categorize


@dataclass(frozen=True)
class ParsedTransaction:
    date: str
    description: str
    amount: float
    currency: str | None
    account: str | None
    category: str | None
    subcategory: str | None
    merchant: str | None
    raw: dict[str, Any]

    def unique_hash(self) -> str:
        payload = {
            "date": self.date,
            "description": self.description,
            "amount": self.amount,
            "currency": self.currency,
            "account": self.account,
        }
        b = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(b).hexdigest()[:32]


def _parse_date(value: str) -> str:
    v = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    # last resort: keep as-is if already iso-ish
    if len(v) >= 10 and v[4] == "-" and v[7] == "-":
        return v[:10]
    raise ValueError(f"Unrecognized date: {value!r}")


def _parse_amount(value: str) -> float:
    v = (value or "").strip().replace(" ", "")
    # Support Italian decimals: 1.234,56 or 1234,56
    if v.count(",") == 1 and (v.count(".") >= 1):
        v = v.replace(".", "").replace(",", ".")
    elif v.count(",") == 1 and v.count(".") == 0:
        v = v.replace(",", ".")
    return float(v)


def _detect_delimiter(sample: str) -> str:
    return ";" if sample.count(";") >= sample.count(",") else ","


def import_csv(
    csv_path: Path,
    *,
    rules: list[Rule],
    date_col: str | None = None,
    desc_col: str | None = None,
    amount_col: str | None = None,
    currency_col: str | None = None,
    account: str | None = None,
) -> list[ParsedTransaction]:
    text = csv_path.read_text(encoding="utf-8", errors="replace")
    sample = "\n".join(text.splitlines()[:5])
    delim = _detect_delimiter(sample)

    reader = csv.DictReader(text.splitlines(), delimiter=delim)
    headers = [h.strip() for h in (reader.fieldnames or [])]

    def pick(candidates: list[str]) -> str | None:
        lower = {h.lower(): h for h in headers}
        for cand in candidates:
            if cand.lower() in lower:
                return lower[cand.lower()]
        return None

    date_col = date_col or pick(["date", "data", "booking date", "valuta", "data operazione", "data contabile"]) or ""
    desc_col = desc_col or pick(["description", "descrizione", "causale", "merchant", "dettagli"]) or ""
    amount_col = amount_col or pick(["amount", "importo", "value", "ammontare"]) or ""
    currency_col = currency_col or pick(["currency", "valuta", "ccy"])  # optional

    if not (date_col and desc_col and amount_col):
        raise ValueError(
            "CSV columns not detected. Provide --date-col/--desc-col/--amount-col. "
            f"Found headers: {headers}"
        )

    txs: list[ParsedTransaction] = []
    for row in reader:
        if not row:
            continue
        date = _parse_date(row.get(date_col, ""))
        desc = (row.get(desc_col, "") or "").strip()
        if not desc:
            continue
        amount = _parse_amount(row.get(amount_col, ""))
        currency = (row.get(currency_col, "") or "").strip() if currency_col else None
        if currency == "":
            currency = None

        cat = categorize(desc, amount, rules)
        txs.append(
            ParsedTransaction(
                date=date,
                description=desc,
                amount=amount,
                currency=currency,
                account=account,
                category=cat.get("category"),
                subcategory=cat.get("subcategory"),
                merchant=cat.get("merchant"),
                raw=row,
            )
        )

    return txs
