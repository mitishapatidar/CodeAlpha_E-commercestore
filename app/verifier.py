"""Verifier: turns customer claims into verified facts. Deterministic, no LLM.

- resolve which order (and which items) an intent refers to, or report why it can't
- compute risk signals (OTP contradiction, payment state, repeat claims, fraud hints)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.data import as_date, get_store
from app.intent import Intent
from app.policy_store import section
from app.tools import ToolTracer, recent_claims

ITEM_SPECIFIC_REASONS = {"change_of_mind", "defective", "damaged", "wrong_item", "missing_item", "physical_damage"}
UNSHIPPED = {"placed", "confirmed", "processing"}
IN_TRANSIT = {"shipped", "out_for_delivery"}

# Which orders can an intent sensibly refer to? (used only when no order ID was given)
CANDIDATE_FILTERS = {
    "refund": lambda o: o["delivery_status"] in ("delivered", "lost") or o["order_status"] in IN_TRANSIT,
    "return": lambda o: o["delivery_status"] == "delivered",
    "replacement": lambda o: o["delivery_status"] == "delivered",
    "product_issue": lambda o: o["delivery_status"] == "delivered",
    "warranty": lambda o: o["delivery_status"] == "delivered",
    "delivery_issue": lambda o: o["delivery_status"] in ("delivered", "in_transit", "out_for_delivery", "lost"),
    "cancel": lambda o: o["order_status"] in UNSHIPPED | IN_TRANSIT,
    "address_change": lambda o: o["order_status"] in UNSHIPPED | IN_TRANSIT,
    "order_status": lambda o: o["order_status"] in UNSHIPPED | IN_TRANSIT or o["delivery_status"] == "lost",
    "payment_issue": lambda o: o["payment_status"] in ("pending", "failed"),
    "refund_status": lambda o: o["refund_status"] != "none" or o["payment_status"] in ("refunded", "partially_refunded"),
}


@dataclass
class Resolution:
    status: str                      # ok | missing | not_found | not_owned | ambiguous | ambiguous_item | no_match
    order: dict | None = None
    items: list[dict] = field(default_factory=list)
    all_items: list[dict] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _hint_words(hint: str | None) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]{3,}", (hint or "").lower())]


CATEGORY_WORDS = {"smartphones", "laptops", "headphones", "earbuds", "smartwatches", "tablets", "cameras", "monitors",
                  "keyboards", "mice", "speakers", "networking", "gaming", "accessories"}


def _item_matches(item: dict, words: list[str]) -> bool:
    """A named category must match exactly ('laptop' is not a 'Laptop Bag'); other words match name/brand."""
    cats = [w for w in words if w in CATEGORY_WORDS]
    if cats:
        return item["category"].lower() in cats
    hay = f"{item['product_name']} {item['brand']} {item['subcategory']}".lower()
    return any(w in hay or (w.endswith("s") and w[:-1] in hay) for w in words)


def option_view(o: dict, items: list[dict]) -> dict:
    when = as_date(o.get("actual_delivery_date")) or as_date(o["order_date"])
    label = "delivered" if o["delivery_status"] == "delivered" else o["order_status"].replace("_", " ")
    return {"order_id": o["order_id"], "items": [i["product_name"] for i in items], "status": label,
            "date": str(when), "total_amount": o["total_amount"]}


def resolve_order(intent: Intent, customer_id: str, tracer: ToolTracer, now: datetime) -> Resolution:
    store = get_store()
    words = _hint_words(intent.product_hint)

    if intent.order_id:
        r = tracer("get_order", order_id=intent.order_id, customer_id=customer_id)
        if not r["found"]:
            return Resolution("not_found", reasons=[f"{intent.order_id} does not exist in NovaMart's records."])
        if not r["owned"]:
            return Resolution("not_owned", reasons=[f"{intent.order_id} is not on this customer's account "
                                                    "(details withheld - another customer's order)."])
        order, items = r["order"], r["items"]
        reasons = [f"Verified {order['order_id']} exists and belongs to {customer_id}."]
    else:
        oids = store.orders_by_customer.get(customer_id, [])
        if not oids:
            return Resolution("missing", reasons=["Customer has no orders on record."])
        flt = CANDIDATE_FILTERS.get(intent.type, lambda o: True)
        cands = [store.order(x) for x in oids if store.order(x)["order_date"] <= now]
        scoped = [o for o in cands if flt(o)]
        if words:
            matched = [o for o in (scoped or cands) if any(_item_matches(i, words) for i in store.items(o["order_id"]))]
            if not matched and scoped:
                matched = [o for o in cands if any(_item_matches(i, words) for i in store.items(o["order_id"]))]
            if not matched:
                return Resolution("no_match", reasons=[f"No order on the account matches '{intent.product_hint}'."])
            scoped = matched
        if not scoped and intent.type == "order_status" and cands and not words:
            scoped = cands[:1]  # nothing in transit: the latest order is what they mean
        if len(scoped) != 1:
            if not scoped:
                return Resolution("missing", reasons=["No order matches this request; order ID needed."])
            opts = [option_view(o, store.items(o["order_id"])) for o in scoped[:5]]
            status = "ambiguous" if words or len(scoped) <= 5 else "missing"
            return Resolution(status, options=opts if status == "ambiguous" else opts[:3],
                              reasons=[f"{len(scoped)} orders could match; not guessing."])
        order = scoped[0]
        r = tracer("get_order", order_id=order["order_id"], customer_id=customer_id)
        order, items = r["order"], r["items"]
        reasons = [f"Only one order matches ({order['order_id']}); verified it belongs to {customer_id}."]

    # which items?
    chosen = items
    if words:
        sub = [i for i in items if _item_matches(i, words)]
        if sub:
            chosen = sub
    if len(chosen) > 1 and len({i["product_id"] for i in chosen}) > 1 and intent.reason in ITEM_SPECIFIC_REASONS \
            and intent.type in ("refund", "return", "replacement", "product_issue", "warranty"):
        return Resolution("ambiguous_item", order=order, all_items=items,
                          options=[{"order_item_id": i["order_item_id"], "product_name": i["product_name"]} for i in chosen],
                          reasons=reasons + ["Order has several items; which one is affected?"])
    return Resolution("ok", order=order, items=chosen, all_items=items, reasons=reasons)


# ------------------------------------------------------------------- signals
def repeat_claims(customer_id: str, now: datetime) -> dict:
    cfg = section("escalation")["repeat_claims"]
    claims = recent_claims(customer_id, now)
    return {"count": len(claims), "min": cfg["min_claims"], "days": cfg["days"],
            "hit": len(claims) >= cfg["min_claims"], "tickets": [c["ticket_id"] for c in claims]}


def fraud_suspicion_ticket(customer_id: str, now: datetime) -> bool:
    since = now - timedelta(days=90)
    return any(t["category"] == "fraud_suspicion" and t.get("created_at") and t["created_at"] >= since
               for t in get_store().tickets_by_customer.get(customer_id, []))


def cancellations_recent(customer_id: str, now: datetime) -> int:
    cfg = section("cancellation")["abuse_limit"]
    since = now - timedelta(days=cfg["days"])
    store = get_store()
    return sum(1 for oid in store.orders_by_customer.get(customer_id, [])
               if store.order(oid)["cancellation_status"] == "approved" and store.order(oid)["order_date"] >= since)


def delivered_days_ago(order: dict, now: datetime) -> int | None:
    d = as_date(order.get("actual_delivery_date"))
    return None if not d else (now.date() - d).days
