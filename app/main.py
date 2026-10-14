"""FastAPI entry point. Implements API_CONTRACT.md (backend <-> frontend) exactly; extra fields are additive.

Run: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import config
from app.agent import run_turn
from app.data import get_store
from app.llm import get_llm
from app.memory import SESSIONS
from app.policy_store import load_policies
from app.schemas import ChatRequest, ChatResponse
from app.tools import TOOL_SPECS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_store()  # warm the dataset + policies once at startup
    load_policies()
    yield


app = FastAPI(title="NovaMart Support Agent", version="1.0.0", lifespan=lifespan,
              description="Agentic customer support: understand -> verify -> reason over policy -> decide -> act.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ResetRequest(BaseModel):
    session_id: str


# ------------------------------------------------------------ contract endpoints
@app.get("/health")
def health() -> dict:
    llm = get_llm()
    return {"status": "ok",
            "policy_versions": [v["version"] for v in load_policies()["refund_policies"]],
            "model": llm.model if llm.available else f"deterministic (LLM off; configured {llm.model})",
            "llm_enabled": llm.available, "data": get_store().stats()}


@app.get("/customers")
def customers(q: str = "", limit: int = 20) -> list[dict]:
    q = q.lower().strip()
    out = []
    for c in get_store().customers.values():
        hay = f"{c['customer_id']} {c['first_name']} {c['last_name']} {c['email']}".lower()
        if not q or q in hay:
            out.append({k: c.get(k) for k in ("customer_id", "first_name", "last_name", "email", "city",
                                               "loyalty_tier", "customer_segment", "account_status")})
            if len(out) >= limit:
                break
    return out


@app.get("/customers/{customer_id}/orders")
def customer_orders(customer_id: str, limit: int = 50) -> list[dict]:
    store = get_store()
    res = []
    for oid in store.orders_by_customer.get(customer_id, [])[:limit]:  # newest first
        o = store.order(oid)
        res.append({"order_id": oid, "order_date": o["order_date"].strftime("%Y-%m-%d %H:%M"),
                    "total_amount": o["total_amount"], "order_status": o["order_status"],
                    "delivery_status": o["delivery_status"], "payment_status": o["payment_status"],
                    "refund_status": o["refund_status"], "items": [i["product_name"] for i in store.items(oid)]})
    return res


@app.get("/demo-scenarios")
def demo_scenarios() -> list[dict]:
    from app.demo import scenarios
    return scenarios()


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=422, detail="message is empty")
    return run_turn(req)


@app.post("/reset")
def reset(req: ResetRequest) -> dict:
    SESSIONS.reset(req.session_id)
    return {"ok": True}


# ---------------------------------------------------------------- extras
CARD_FIELDS = ("product_id", "product_name", "brand", "category", "subcategory", "price", "mrp",
               "discount_percent", "rating", "review_count", "warranty_months", "returnable",
               "status", "color", "image_url")


class OrderLine(BaseModel):
    product_id: str
    quantity: int


class ShippingInfo(BaseModel):
    name: str
    phone: str
    address: str
    city: str
    state: str
    pincode: str


class PlaceOrder(BaseModel):
    customer_id: str
    items: list[OrderLine]
    shipping: ShippingInfo
    payment_method: str  # UPI | credit_card | cash_on_delivery
    payment_ref: str | None = None


PAY_METHODS = {"UPI", "credit_card", "debit_card", "cash_on_delivery"}


@app.get("/customers/{customer_id}/address")
def customer_address(customer_id: str) -> dict:
    """Saved delivery address, used to prefill checkout."""
    c = get_store().customer(customer_id)
    if not c:
        raise HTTPException(404, "Unknown customer")
    return {k: (str(c[k]) if c.get(k) is not None else "") for k in ("phone", "address", "city", "state", "pincode")}


@app.post("/orders")
def place_order(req: PlaceOrder) -> dict:
    """Storefront checkout: validates the cart against live stock and saves the order like any other order,
    so My Orders, tracking and the support agent all see it."""
    from datetime import timedelta
    store = get_store()
    if not store.customer(req.customer_id):
        raise HTTPException(404, "Unknown customer")
    if req.payment_method not in PAY_METHODS:
        raise HTTPException(422, "Unsupported payment method")
    s = req.shipping
    if not (s.phone.isdigit() and len(s.phone) == 10 and s.pincode.isdigit() and len(s.pincode) == 6 and s.address.strip()):
        raise HTTPException(422, "Enter a valid 10-digit phone, 6-digit PIN code and address")
    lines: dict[str, int] = {}
    for ln in req.items:
        lines[ln.product_id] = lines.get(ln.product_id, 0) + ln.quantity
    if not lines:
        raise HTTPException(422, "Cart is empty")
    for pid, q in lines.items():
        p = store.products.get(pid)
        if not p or p["status"] != "active":
            raise HTTPException(409, f"{pid} is no longer available")
        if not 1 <= q <= 10 or q > int(p["stock_quantity"] or 0):
            raise HTTPException(409, f"Only {p['stock_quantity']} of {p['product_name']} in stock")

    now = config.now_ist()
    oid_n, item_n = store.next_ids()
    order_id = f"ORD-{oid_n:06d}"
    items = []
    for k, (pid, q) in enumerate(lines.items()):
        price = int(store.products[pid]["price"])
        items.append({"order_item_id": f"OI-{item_n + k:06d}", "order_id": order_id, "product_id": pid, "quantity": q,
                      "unit_price": price, "discount": 0, "final_price": price * q, "item_status": "ordered",
                      "return_status": "none", "refund_amount": 0})
    subtotal = sum(i["final_price"] for i in items)
    shipping = 0 if subtotal >= 1000 else 79
    tax = round(subtotal * 0.18)
    prepaid = req.payment_method != "cash_on_delivery"
    order = {"order_id": order_id, "customer_id": req.customer_id, "order_date": now.isoformat(),
             "order_status": "confirmed" if prepaid else "placed", "payment_method": req.payment_method,
             "payment_status": "paid" if prepaid else "pending", "subtotal": subtotal, "discount": 0,
             "shipping_fee": shipping, "tax": tax, "total_amount": subtotal + shipping + tax,
             "shipping_address": f"{s.name}, {s.address}, {s.city}, {s.state} - {s.pincode} (ph {s.phone})",
             "city": s.city, "state": s.state, "estimated_delivery_date": (now + timedelta(days=4)).date().isoformat(),
             "actual_delivery_date": None, "tracking_number": None, "courier": None, "delivery_status": "not_dispatched",
             "delivery_otp_verified": False, "cancellation_status": "none", "refund_status": "none",
             "payment_ref": req.payment_ref}
    store.add_order(order, items)
    return {"order_id": order_id, "total_amount": order["total_amount"], "payment_status": order["payment_status"],
            "order_status": order["order_status"], "estimated_delivery_date": order["estimated_delivery_date"]}


@app.get("/products/{product_id}")
def product_detail(product_id: str) -> dict:
    """Full product page: catalogue row, spec sheet and related products."""
    store = get_store()
    p = store.products.get(product_id)
    if not p:
        raise HTTPException(404, f"Unknown product {product_id}")
    card = lambda r: {k: r.get(k) for k in CARD_FIELDS}
    related = [r for r in store.products.values() if r["category"] == p["category"] and r["product_id"] != product_id
               and r["status"] == "active"]
    related.sort(key=lambda r: (r["subcategory"] != p["subcategory"], -(r["review_count"] or 0)))
    spec = store.specs.get(product_id, {})
    return {**card(p), "description": p.get("description", ""), "stock_quantity": p.get("stock_quantity"),
            "replacement_available": p.get("replacement_available"), "specs": spec.get("specs", {}),
            "related": [card(r) for r in related[:4]]}


@app.get("/products")
def products(q: str = "", category: str = "", limit: int = 24) -> list[dict]:
    """Catalog for the storefront view (customer-facing UI)."""
    q, category = q.lower().strip(), category.lower().strip()
    out = []
    for p in get_store().products.values():
        if category and p["category"].lower() != category:
            continue
        if q and q not in f"{p['product_name']} {p['brand']} {p['category']} {p['subcategory']}".lower():
            continue
        out.append({k: p.get(k) for k in CARD_FIELDS})
    out.sort(key=lambda p: (p["status"] != "active", -(p["review_count"] or 0)))
    if not q and not category:
        out = featured_order(out)
    return out[:limit]


FEATURED = ["Smartphones", "Earbuds", "Headphones", "Smartwatches", "Laptops", "Tablets", "Speakers", "Cameras"]


def featured_order(products: list[dict]) -> list[dict]:
    """Home page: phones, earbuds, headphones... first, one of each in turn (best-reviewed first), then the rest."""
    by_cat: dict[str, list[dict]] = {}
    for p in products:
        if p["status"] == "active":
            by_cat.setdefault(p["category"], []).append(p)
    lead = []
    while any(by_cat.get(c) for c in FEATURED):
        lead += [by_cat[c].pop(0) for c in FEATURED if by_cat.get(c)]
    seen = {p["product_id"] for p in lead}
    return lead + [p for p in products if p["product_id"] not in seen]


@app.get("/customers/{customer_id}/tickets")
def customer_tickets(customer_id: str, limit: int = 20) -> list[dict]:
    """Customer complaint history: requests the agent opened this session + recent tickets from the dataset."""
    from app import tools as t
    out = []
    for recs in t._actions_index().values():
        for r in recs:
            if r.get("customer_id") == customer_id:
                out.append({"id": r["id"], "source": "agent", "type": r["type"], "order_id": r.get("order_id"),
                            "category": (f"Escalated to {r.get('team')}" if r["type"] == "escalation"
                                         else r.get("category") or r.get("reason") or r["type"]),
                            "summary": r.get("summary") or r.get("reason") or "", "status": r.get("status"),
                            "team": r.get("team") or r.get("assigned_team"), "amount": r.get("amount"),
                            "created_at": r.get("created_at")})
    for tk in reversed(get_store().tickets_by_customer.get(customer_id, [])):
        out.append({"id": tk["ticket_id"], "source": "history", "type": "ticket", "order_id": tk.get("order_id"),
                    "category": tk["category"], "summary": tk["issue_summary"], "status": tk["status"],
                    "team": tk["assigned_team"], "amount": None,
                    "created_at": tk["created_at"].isoformat() if tk.get("created_at") else None})
    out.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return out[:limit]


@app.get("/admin/turns")
def admin_turns(limit: int = 100) -> list[dict]:
    """Owner review: the agent's most recent decisions with full trace."""
    from app.agent import TURN_LOG
    return list(TURN_LOG)[:limit]


@app.get("/admin/actions")
def admin_actions(limit: int = 200) -> list[dict]:
    """Owner review: every refund / return / ticket / escalation the agent created."""
    from app import tools as t
    recs = [r for rs in t._actions_index().values() for r in rs]
    recs.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return recs[:limit]


@app.get("/categories")
def categories() -> list[dict]:
    counts: dict[str, int] = {}
    for p in get_store().products.values():
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    return [{"category": c, "count": n} for c, n in sorted(counts.items(), key=lambda x: -x[1])]


@app.post("/demo/reset")
def demo_reset() -> dict:
    """Clear actions the agent created (runtime log) and all sessions - for repeatable demos."""
    from app import tools as t
    if t.ACTIONS_LOG.exists():
        t.ACTIONS_LOG.unlink()
    t.reset_actions_index()
    SESSIONS._s.clear()
    from app.agent import TURN_LOG
    TURN_LOG.clear()
    return {"ok": True}


@app.get("/tools")
def tools() -> list[dict]:
    return TOOL_SPECS


if config.LLM_MODE == "off":
    logging.getLogger("novamart").info("LLM_MODE=off: running fully deterministic")
