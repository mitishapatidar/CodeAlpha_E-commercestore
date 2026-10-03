"""Read-only data layer: loads the NovaMart dataset once and builds lookup indexes.

The dataset is the single source of truth. Nothing in the agent writes to it;
actions go to runtime/actions_log.jsonl (see app/tools.py).
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import DATA_DIR, IST

DATETIME_COLS = {
    "orders": ["order_date"],
    "support_tickets": ["created_at", "resolved_at"],
}
DATE_COLS = {
    "customers": ["customer_since", "date_of_birth"],
    "orders": ["estimated_delivery_date", "actual_delivery_date"],
    "reviews": ["review_date"],
}


def _clean(value: Any) -> Any:
    """Convert pandas/numpy scalars to plain Python, NaN/NaT to None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):  # numpy scalar
        return value.item()
    return value


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _clean(v) for k, v in row.items()} for row in df.to_dict("records")]


def _parse_specs(products_dir: Path) -> dict[str, dict]:
    """Parse data/products/*.md into {product_id: {"specs": {...}, "summary": str}}."""
    specs: dict[str, dict] = {}
    if not products_dir.exists():
        return specs
    header = re.compile(r"^## (.+?) \((PROD-\d+)\)\s*$")
    for md in sorted(products_dir.glob("*.md")):
        current: dict | None = None
        for line in md.read_text(encoding="utf-8").splitlines():
            m = header.match(line)
            if m:
                current = {"name": m.group(1), "specs": {}, "summary": ""}
                specs[m.group(2)] = current
                continue
            if current is None:
                continue
            if line.startswith("|") and not line.startswith("|---") and "Specification" not in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) == 2:
                    current["specs"][cells[0]] = cells[1]
            elif line and not line.startswith(("|", "-", "#")):
                current["summary"] = line.strip()
    return specs


class DataStore:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.frames: dict[str, pd.DataFrame] = {}
        self._load()
        self._index()

    # ------------------------------------------------------------------ load
    def _load(self) -> None:
        for name in ["customers", "orders", "order_items", "products", "reviews", "support_tickets"]:
            df = pd.read_csv(self.data_dir / f"{name}.csv")
            for col in DATETIME_COLS.get(name, []):
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.tz_localize(IST)
            for col in DATE_COLS.get(name, []):
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            self.frames[name] = df

        conv_path = self.data_dir / "conversations.json"
        self.conversations: list[dict] = (
            json.loads(conv_path.read_text(encoding="utf-8")) if conv_path.exists() else []
        )
        for conv in self.conversations:
            conv["started_at_dt"] = _to_dt(conv.get("started_at"))
        self.specs = _parse_specs(self.data_dir / "products")

    # ----------------------------------------------------------------- index
    def _index(self) -> None:
        f = self.frames
        self.customers = {r["customer_id"]: r for r in _records(f["customers"])}
        self.customers_by_email = {
            str(r["email"]).lower(): r["customer_id"] for r in self.customers.values() if r.get("email")
        }
        self.products = {r["product_id"]: r for r in _records(f["products"])}
        self.orders = {r["order_id"]: r for r in _records(f["orders"])}

        self.orders_by_customer: dict[str, list[str]] = defaultdict(list)
        for o in sorted(self.orders.values(), key=lambda o: o["order_date"], reverse=True):
            self.orders_by_customer[o["customer_id"]].append(o["order_id"])

        self.items_by_order: dict[str, list[dict]] = defaultdict(list)
        for it in _records(f["order_items"]):
            self.items_by_order[it["order_id"]].append(it)

        self.tickets_by_customer: dict[str, list[dict]] = defaultdict(list)
        self.tickets_by_order: dict[str, list[dict]] = defaultdict(list)
        for t in sorted(_records(f["support_tickets"]), key=lambda t: t["created_at"] or datetime.min.replace(tzinfo=IST)):
            self.tickets_by_customer[t["customer_id"]].append(t)
            if t.get("order_id"):
                self.tickets_by_order[t["order_id"]].append(t)

        self.convs_by_customer: dict[str, list[dict]] = defaultdict(list)
        for c in sorted(self.conversations, key=lambda c: c["started_at_dt"] or datetime.min.replace(tzinfo=IST)):
            self.convs_by_customer[c["customer_id"]].append(c)

    # --------------------------------------------------------------- helpers
    def customer(self, customer_id: str) -> dict | None:
        return self.customers.get(customer_id)

    def order(self, order_id: str) -> dict | None:
        return self.orders.get(order_id)

    def items(self, order_id: str) -> list[dict]:
        out = []
        for it in self.items_by_order.get(order_id, []):
            p = self.products.get(it["product_id"], {})
            out.append({**it, "product_name": p.get("product_name"), "category": p.get("category"),
                        "subcategory": p.get("subcategory"), "brand": p.get("brand"),
                        "returnable": p.get("returnable"), "replacement_available": p.get("replacement_available"),
                        "warranty_months": p.get("warranty_months"), "product_status": p.get("status")})
        return out

    def stats(self) -> dict[str, int]:
        return {name: len(df) for name, df in self.frames.items()} | {
            "conversations": len(self.conversations), "product_specs": len(self.specs)}


def _to_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        return dt if dt.tzinfo else dt.replace(tzinfo=IST)
    except ValueError:
        return None


def as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(IST).date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    return DataStore()
