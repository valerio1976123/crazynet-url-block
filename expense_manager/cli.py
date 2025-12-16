from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from . import __version__
from .db import connect, init_db
from .import_csv import import_csv
from .paths import default_db_path, default_rules_path
from .report import month_budget, month_summary, set_budget
from .rules import load_rules, write_default_rules


def _ensure_init(conn: sqlite3.Connection) -> None:
    init_db(conn)


def cmd_init(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    rules_path = Path(args.rules)
    conn = connect(db_path)
    _ensure_init(conn)
    write_default_rules(rules_path)
    print(f"OK: db={db_path} rules={rules_path}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    rules_path = Path(args.rules)
    rules = load_rules(rules_path)

    conn = connect(db_path)
    _ensure_init(conn)

    inserted = 0
    skipped = 0

    for csv_file in args.csv:
        csv_path = Path(csv_file)
        txs = import_csv(
            csv_path,
            rules=rules,
            date_col=args.date_col,
            desc_col=args.desc_col,
            amount_col=args.amount_col,
            currency_col=args.currency_col,
            account=args.account,
        )

        for i, tx in enumerate(txs, start=1):
            h = tx.unique_hash()
            try:
                conn.execute(
                    """
                    INSERT INTO transactions(
                      date, description, amount, currency, account,
                      category, subcategory, merchant,
                      source_file, source_row, unique_hash, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tx.date,
                        tx.description,
                        tx.amount,
                        tx.currency,
                        tx.account,
                        tx.category,
                        tx.subcategory,
                        tx.merchant,
                        str(csv_path),
                        i,
                        h,
                        __import__("json").dumps(tx.raw, ensure_ascii=False),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1

        conn.commit()

    print(f"OK: inserted={inserted} skipped_duplicates={skipped}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    conn = connect(db_path)
    _ensure_init(conn)

    month = args.month
    totals = month_summary(conn, month)
    budgets = month_budget(conn, month)

    print(f"Report {month}")
    print("=" * (7 + len(month)))

    for row in totals:
        b = budgets.get(row.category)
        if b is None:
            print(f"{row.category:20} {row.total:10.2f}")
        else:
            diff = b + row.total  # expenses are negative
            print(f"{row.category:20} {row.total:10.2f}   budget {b:10.2f}   residuo {diff:10.2f}")

    total = sum(r.total for r in totals)
    print("-" * 50)
    print(f"Totale (somma movimenti): {total:.2f}")
    return 0


def cmd_budget_set(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    conn = connect(db_path)
    _ensure_init(conn)
    set_budget(conn, args.month, args.category, float(args.amount))
    print(f"OK: budget {args.month} {args.category}={float(args.amount):.2f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=str(default_db_path()), help="Path DB SQLite (default: data/expenses.sqlite)")
    common.add_argument("--rules", default=str(default_rules_path()), help="Path rules JSON (default: data/rules.json)")

    p = argparse.ArgumentParser(prog="expense-manager", description="Gestore spese automatico", parents=[common])
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="cmd", required=True)

    # Allow --db/--rules either before or after the subcommand by attaching them to each parser.
    s_init = sub.add_parser("init", help="Crea DB e rules.json", parents=[common])
    s_init.set_defaults(func=cmd_init)

    s_imp = sub.add_parser("import", help="Importa uno o più CSV", parents=[common])
    s_imp.add_argument("csv", nargs="+", help="Percorsi CSV")
    s_imp.add_argument("--account", default=None, help="Nome conto (opzionale)")
    s_imp.add_argument("--date-col", default=None, help="Nome colonna data")
    s_imp.add_argument("--desc-col", default=None, help="Nome colonna descrizione")
    s_imp.add_argument("--amount-col", default=None, help="Nome colonna importo")
    s_imp.add_argument("--currency-col", default=None, help="Nome colonna valuta")
    s_imp.set_defaults(func=cmd_import)

    s_rep = sub.add_parser("report", help="Report mensile per categoria", parents=[common])
    s_rep.add_argument("month", help="Mese in formato YYYY-MM")
    s_rep.set_defaults(func=cmd_report)

    s_b = sub.add_parser("budget", help="Gestione budget", parents=[common])
    sub_b = s_b.add_subparsers(dest="budget_cmd", required=True)
    s_bs = sub_b.add_parser("set", help="Imposta budget categoria", parents=[common])
    s_bs.add_argument("month", help="YYYY-MM")
    s_bs.add_argument("category", help="Categoria")
    s_bs.add_argument("amount", help="Importo budget (es. 500)")
    s_bs.set_defaults(func=cmd_budget_set)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
