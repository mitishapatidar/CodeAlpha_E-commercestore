"""The 10 agent tools (handbook p.7) as pure Python functions over the dataset.

Read tools return {"found": bool, ...}. Write tools never touch the source CSVs;
they append an auditable record to runtime/actions_log.jsonl and return an ID.
Every tool call made during a turn is recorded by `ToolTracer` so the API can
show exactly which tools ran with which (verified) parameters.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable

from app import policy_engine as pe
from app.config import ACTIONS_LOG, IST, RUNTIME_DIR, now_ist
from app.data import as_date, get_store
from app.policy_store import section

_log_lock = threading.Lock()

# Fields that must never leave the backend (handbook p.10: no driver, route, OTP)
INTERNAL_ORDER_FIELDS = {"delivery_otp_verified"}


# ----------------------------------------------------------------- read tools
def get_customer(customer_id: str | None = None, email: str | None = None) -> dict:
    store = get_store()
    cid = customer_id or (store.customers_by_email.get(email.lower()) if email else None)
    c = store.customer(cid) if cid else None
    if not c:
        return {"found": False}
    return {"found": True, "customer": {k: c[k] for k in (
        "customer_id", "first_name", "last_name", "email", "city", "customer_since", "customer_segment",
        "account_status", "preferred_language", "total_orders", "total_spend", "loyalty_tier")}}


def get_order(order_id: str, customer_id: str) -> dict:
    """Fetch an order + items. Ownership is enforced: another customer's order returns owned=False and no details."""
    store = get_store()
    o = store.order(order_id)
    if not o:
        return {"found": False, "order_id": order_id}
    if o["customer_id"] != customer_id:
        return {"found": True, "owned": False, "order_id": order_id}
    return {"found": True, "owned": True, "order": dict(o), "items": store.items(order_id)}


def get_product(product_id: str | None = None, query: str | None = None) -> dict:
    store = get_store()
    p = store.products.get(product_id) if product_id else None
    if not p and query:
        q = query.lower()
        hits = [x for x in store.products.values() if q in x["product_name"].lower()]
        p = hits[0] if len(hits) == 1 else None
        if not p and hits:
            return {"found": False, "ambiguous": True, "matches": [h["product_name"] for h in hits[:5]]}
    if not p:
        return {"found": False}
    spec = store.specs.get(p["product_id"], {})
    return {"found": True, "product": {k: p[k] for k in (
        "product_id", "product_name", "category", "subcategory", "brand", "price", "mrp", "warranty_months",
        "returnable", "replacement_available", "rating", "status", "color", "stock_quantity")},
        "specs": spec.get("specs", {}), "summary": spec.get("summary", "")}


def get_conversations(customer_id: str, limit: int = 5) -> dict:
    """Prior conversations + open/recent tickets: always loaded first (handbook p.14)."""
    store = get_store()
    convs = store.convs_by_customer.get(customer_id, [])[-limit:]
    tickets = store.tickets_by_customer.get(customer_id, [])
    open_t = [t for t in tickets if t["status"] in ("open", "in_progress", "escalated")]
    return {"found": bool(convs or tickets),
            "conversations": [{"conversation_id": c["conversation_id"], "order_id": c.get("order_id"),
                               "ticket_id": c.get("ticket_id"), "status": c["status"], "started_at": c["started_at"],
                               "messages": c["messages"][-6:]} for c in convs],
            "open_tickets": [_ticket_view(t) for t in open_t],
            "recent_tickets": [_ticket_view(t) for t in tickets[-10:]]}


def _ticket_view(t: dict) -> dict:
    return {"ticket_id": t["ticket_id"], "order_id": t.get("order_id"), "category": t["category"],
            "subcategory": t["subcategory"], "status": t["status"], "priority": t["priority"],
            "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
            "issue_summary": t["issue_summary"], "assigned_team": t["assigned_team"]}


# ------------------------------------------------------------ policy tools
def check_refund_eligibility(order_id: str, customer_id: str, reason: str, item_ids: list[str] | None = None,
                             request_date: str | None = None, earlier_request: str | None = None) -> dict:
    res = get_order(order_id, customer_id)
    if not res.get("owned"):
        return {"found": res["found"], "eligible": False, "reasons": ["Order not found on this account."]}
    items = _select_items(res["items"], item_ids)
    customer = get_store().customer(customer_id)
    now = now_ist(request_date)
    early = datetime.fromisoformat(earlier_request) if earlier_request else None
    return {"found": True, **pe.check_eligibility(res["order"], items, reason, customer, now, early)}


def calculate_refund(order_id: str, customer_id: str, reason: str, item_ids: list[str] | None = None,
                     requested_amount: float | None = None, request_date: str | None = None) -> dict:
    res = get_order(order_id, customer_id)
    if not res.get("owned"):
        return {"found": res["found"], "refund_amount": 0, "reasons": ["Order not found on this account."]}
    items = _select_items(res["items"], item_ids)
    whole = len(items) == len(res["items"])
    return {"found": True, **pe.calculate_refund(res["order"], items, reason, requested_amount, whole,
                                                 now_ist(request_date))}


def _select_items(items: list[dict], item_ids: list[str] | None) -> list[dict]:
    if not item_ids:
        return items
    chosen = [i for i in items if i["order_item_id"] in item_ids or i["product_id"] in item_ids]
    return chosen or items


# ------------------------------------------------------------- write tools
_ACTIONS: dict[str, list[dict]] | None = None  # order_id -> actions already taken (from actions_log.jsonl)


def _actions_index() -> dict[str, list[dict]]:
    global _ACTIONS
    if _ACTIONS is None:
        _ACTIONS = {}
        if ACTIONS_LOG.exists():
            for line in ACTIONS_LOG.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("order_id"):
                    _ACTIONS.setdefault(rec["order_id"], []).append(rec)
    return _ACTIONS


def prior_actions(order_id: str, types: set[str], item_ids: list[str] | None = None) -> list[dict]:
    """Refunds/returns/tickets this agent already created for an order (prevents duplicates across turns)."""
    out = []
    for rec in _actions_index().get(order_id, []):
        if rec["type"] in types and (not item_ids or not rec.get("item_ids") or set(item_ids) & set(rec["item_ids"])):
            out.append(rec)
    return out


def reset_actions_index() -> None:
    global _ACTIONS
    _ACTIONS = None


def _write(kind: str, prefix: str, payload: dict) -> dict:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    action_id = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
    record = {"id": action_id, "type": kind, "created_at": now_ist().isoformat(), **payload}
    with _log_lock, ACTIONS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    if payload.get("order_id"):
        _actions_index().setdefault(payload["order_id"], []).append(record)
    return {"success": True, "id": action_id, **payload}


def create_return(order_id: str, customer_id: str, item_ids: list[str], reason: str,
                  resolution: str = "refund", refund_estimate: float | None = None) -> dict:
    return _write("return", "RET", {"order_id": order_id, "customer_id": customer_id, "item_ids": item_ids,
                                     "reason": reason, "resolution": resolution, "refund_estimate": refund_estimate,
                                     "pickup": "within 24-48 hours", "status": "pickup_scheduled"})


def create_refund(order_id: str, customer_id: str, amount: float, reason: str, item_ids: list[str] | None = None,
                  destination: str = "original_payment_method", return_pickup: bool = False) -> dict:
    if amount <= 0:
        return {"success": False, "error": "Refund amount must be positive."}
    o = get_store().order(order_id)
    if not o or o["customer_id"] != customer_id:
        return {"success": False, "error": "Order not found on this account."}
    if amount > float(o["total_amount"]):  # last line of defence: never refund more than was paid
        return {"success": False, "error": "Refund exceeds order total."}
    return _write("refund", "RFD", {"order_id": order_id, "customer_id": customer_id, "amount": round(amount, 2),
                                     "reason": reason, "item_ids": item_ids or [], "destination": destination,
                                     "return_pickup": return_pickup,
                                     "status": "pending_qc" if return_pickup else "initiated"})


def create_support_ticket(customer_id: str, category: str, summary: str, order_id: str | None = None,
                          priority: str = "medium", team: str | None = None) -> dict:
    return _write("ticket", "TCK", {"customer_id": customer_id, "order_id": order_id, "category": category,
                                     "summary": summary, "priority": priority, "assigned_team": team,
                                     "status": "open"})


def escalate_to_human(customer_id: str, reason: str, team: str, priority: str = "high",
                      order_id: str | None = None, context: dict | None = None) -> dict:
    sla = section("escalation")["sla"].get(priority, "")
    return _write("escalation", "ESC", {"customer_id": customer_id, "order_id": order_id, "reason": reason,
                                         "team": team, "priority": priority, "sla": sla, "context": context or {},
                                         "status": "queued"})


# ------------------------------------------------------------------ registry
TOOLS: dict[str, Callable[..., dict]] = {
    "get_customer": get_customer, "get_order": get_order, "get_product": get_product,
    "get_conversations": get_conversations, "check_refund_eligibility": check_refund_eligibility,
    "calculate_refund": calculate_refund, "create_return": create_return, "create_refund": create_refund,
    "create_support_ticket": create_support_ticket, "escalate_to_human": escalate_to_human,
}
WRITE_TOOLS = {"create_return", "create_refund", "create_support_ticket", "escalate_to_human"}

_s, _n, _a = {"type": "string"}, {"type": "number"}, {"type": "array", "items": {"type": "string"}}
TOOL_SPECS = [
    {"name": "get_customer", "description": "Fetch customer profile by ID or email.",
     "input_schema": {"type": "object", "properties": {"customer_id": _s, "email": _s}}},
    {"name": "get_order", "description": "Order + items + delivery state; enforces ownership.",
     "input_schema": {"type": "object", "properties": {"order_id": _s, "customer_id": _s},
                      "required": ["order_id", "customer_id"]}},
    {"name": "get_product", "description": "Product + specs + warranty info.",
     "input_schema": {"type": "object", "properties": {"product_id": _s, "query": _s}}},
    {"name": "get_conversations", "description": "Prior conversations and open tickets for a customer.",
     "input_schema": {"type": "object", "properties": {"customer_id": _s, "limit": {"type": "integer"}},
                      "required": ["customer_id"]}},
    {"name": "check_refund_eligibility", "description": "Apply policy version + window arithmetic.",
     "input_schema": {"type": "object", "properties": {"order_id": _s, "customer_id": _s, "reason": _s,
                      "item_ids": _a, "request_date": _s}, "required": ["order_id", "customer_id", "reason"]}},
    {"name": "calculate_refund", "description": "Valid refund = min(requested, paid incl. GST - restocking).",
     "input_schema": {"type": "object", "properties": {"order_id": _s, "customer_id": _s, "reason": _s,
                      "item_ids": _a, "requested_amount": _n}, "required": ["order_id", "customer_id", "reason"]}},
    {"name": "create_return", "description": "Open a return/replacement request on an eligible order.",
     "input_schema": {"type": "object", "properties": {"order_id": _s, "customer_id": _s, "item_ids": _a,
                      "reason": _s, "resolution": _s}, "required": ["order_id", "customer_id", "item_ids", "reason"]}},
    {"name": "create_refund", "description": "Issue a verified refund within the approval threshold.",
     "input_schema": {"type": "object", "properties": {"order_id": _s, "customer_id": _s, "amount": _n,
                      "reason": _s, "item_ids": _a}, "required": ["order_id", "customer_id", "amount", "reason"]}},
    {"name": "create_support_ticket", "description": "Open a ticket for follow-up.",
     "input_schema": {"type": "object", "properties": {"customer_id": _s, "category": _s, "summary": _s,
                      "order_id": _s, "priority": _s}, "required": ["customer_id", "category", "summary"]}},
    {"name": "escalate_to_human", "description": "Hand off to a human team with full context.",
     "input_schema": {"type": "object", "properties": {"customer_id": _s, "reason": _s, "team": _s,
                      "priority": _s, "order_id": _s}, "required": ["customer_id", "reason", "team"]}},
]


class ToolTracer:
    """Runs tools and records every call (name, params, compact result) for the response trace."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._cache: dict[str, dict] = {}

    def __call__(self, name: str, **params: Any) -> dict:
        key = f"{name}:{json.dumps(params, sort_keys=True, default=str)}"
        if name not in WRITE_TOOLS and key in self._cache:  # don't repeat identical reads in one turn
            return self._cache[key]
        result = TOOLS[name](**params)
        self._cache[key] = result
        self.calls.append({"tool": name, "params": params, "result": _summarise(name, result)})
        return result

    @property
    def actions(self) -> list[dict]:
        return [c for c in self.calls if c["tool"] in WRITE_TOOLS]


def _summarise(name: str, r: dict) -> dict:
    """Compact, customer-safe view of a tool result for the trace."""
    if name == "get_order":
        if not r.get("owned"):
            return {"found": r.get("found"), "owned": r.get("owned", False)}
        o = r["order"]
        return {"found": True, "owned": True, "order_status": o["order_status"],
                "payment_status": o["payment_status"], "delivery_status": o["delivery_status"],
                "total_amount": o["total_amount"], "items": [i["product_name"] for i in r["items"]]}
    if name == "get_conversations":
        return {"conversations": len(r["conversations"]), "open_tickets": [t["ticket_id"] for t in r["open_tickets"]]}
    if name == "get_customer":
        c = r.get("customer") or {}
        return {"found": r["found"], "loyalty_tier": c.get("loyalty_tier"), "account_status": c.get("account_status")}
    if name == "get_product":
        return {"found": r["found"], "product": (r.get("product") or {}).get("product_name")}
    if name == "check_refund_eligibility":
        return {k: r.get(k) for k in ("eligible", "policy_version", "day_n", "window_days") if k in r}
    if name == "calculate_refund":
        return {k: r.get(k) for k in ("refund_amount", "max_refundable", "restocking_fee", "capped") if k in r}
    return {k: v for k, v in r.items() if k in ("success", "id", "amount", "team", "priority", "category", "error")}


def recent_claims(customer_id: str, now: datetime, exclude_order: str | None = None) -> list[dict]:
    """Support tickets that count as non-delivery/refund/return claims within the configured look-back."""
    cfg = section("escalation")["repeat_claims"]
    since = now - timedelta(days=cfg["days"])
    out = []
    for t in get_store().tickets_by_customer.get(customer_id, []):
        if not t.get("created_at") or not (since <= t["created_at"] <= now):
            continue
        for rule in cfg["ticket_rules"]:
            if t["category"] == rule["category"] and ("*" in rule["subcategories"] or t["subcategory"] in rule["subcategories"]):
                out.append(_ticket_view(t))
                break
    return out


def earliest_request(order_id: str, categories: set[str]) -> datetime | None:
    """Earliest earlier ticket on this order in the given categories (request-raised-in-time exception)."""
    ts = [t["created_at"] for t in get_store().tickets_by_order.get(order_id, [])
          if t["category"] in categories and t.get("created_at")]
    return min(ts) if ts else None


def order_age_hours(order: dict, now: datetime) -> float:
    return (now - order["order_date"]).total_seconds() / 3600


__all__ = list(TOOLS) + ["TOOLS", "TOOL_SPECS", "ToolTracer", "recent_claims", "earliest_request", "as_date", "IST"]
