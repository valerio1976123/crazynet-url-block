from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RULES: list[dict[str, Any]] = [
    {"pattern": "amazon", "category": "Shopping", "subcategory": "Online", "merchant": "Amazon", "priority": 100},
    {"pattern": "spotify", "category": "Abbonamenti", "subcategory": "Musica", "merchant": "Spotify", "priority": 100},
    {"pattern": "netflix", "category": "Abbonamenti", "subcategory": "Video", "merchant": "Netflix", "priority": 100},
    {"pattern": "uber|bolt", "category": "Trasporti", "subcategory": "Ride-hailing", "merchant": "Uber/Bolt", "priority": 90},
    {"pattern": "trenitalia|italo", "category": "Trasporti", "subcategory": "Treno", "merchant": "Treno", "priority": 90},
    {"pattern": "esselunga|conad|coop|carrefour|lidl", "category": "Spesa", "subcategory": "Supermercato", "merchant": "Supermercato", "priority": 80},
    {"pattern": "enel|eni|a2a|acea", "category": "Utenze", "subcategory": "Energia", "merchant": "Utenze", "priority": 80},
]


@dataclass(frozen=True)
class Rule:
    pattern: str
    category: str
    subcategory: str | None = None
    merchant: str | None = None
    priority: int = 0

    def matches(self, text: str) -> bool:
        return re.search(self.pattern, text, flags=re.IGNORECASE) is not None


def load_rules(path: Path) -> list[Rule]:
    if not path.exists():
        return [Rule(**r) for r in DEFAULT_RULES]
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("rules.json must be a JSON array")
    rules: list[Rule] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rules.append(
            Rule(
                pattern=str(item.get("pattern", "")),
                category=str(item.get("category", "Altro")),
                subcategory=item.get("subcategory"),
                merchant=item.get("merchant"),
                priority=int(item.get("priority", 0)),
            )
        )
    rules.sort(key=lambda r: r.priority, reverse=True)
    return rules


def write_default_rules(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(json.dumps(DEFAULT_RULES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def categorize(description: str, amount: float, rules: Iterable[Rule]) -> dict[str, str | None]:
    # Income heuristic first
    if amount > 0:
        return {"category": "Entrate", "subcategory": None, "merchant": None}

    for rule in rules:
        if rule.pattern and rule.matches(description):
            return {"category": rule.category, "subcategory": rule.subcategory, "merchant": rule.merchant}

    return {"category": "Altro", "subcategory": None, "merchant": None}
