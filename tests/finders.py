"""Query helpers that pick real rows from the dataset for tests (no hardcoded IDs in the agent)."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.config import IST, now_ist
from app.data import get_store


def NOW() -> datetime:
    return now_ist()


def find_order(pred, store=None):
    store = store or get_store()
    for o in store.orders.values():
        items = store.items(o["order_id"])
        if pred(o, items, store.customer(o["customer_id"])):
            return o, items, store.customer(o["customer_id"])
    raise LookupError("no matching order in dataset")


def delivered(o):
    return o["order_status"] == "delivered" and o["delivery_status"] == "delivered" and o["payment_status"] == "paid"


def no_claims(cid, store=None):
    """Customer without recent claim tickets, active account, so repeat-claim escalation doesn't interfere."""
    from app.tools import recent_claims
    store = store or get_store()
    c = store.customer(cid)
    return c["account_status"] == "active" and len(recent_claims(cid, NOW())) == 0


def clean_items(items):
    return all(i["return_status"] == "none" and not i["refund_amount"] for i in items)


def at_now(delivery_days_ago: int):
    return (NOW() - timedelta(days=delivery_days_ago)).date()
