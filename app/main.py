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
        out.append({k: p.get(k) for k in ("product_id", "product_name", "brand", "category", "subcategory", "price", "mrp",
                                           "discount_percent", "rating", "review_count", "warranty_months", "returnable",
                                           "status", "color")})
    out.sort(key=lambda p: (p["status"] != "active", -(p["review_count"] or 0)))
    return out[:limit]


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
    return {"ok": True}


@app.get("/tools")
def tools() -> list[dict]:
    return TOOL_SPECS


if config.LLM_MODE == "off":
    logging.getLogger("novamart").info("LLM_MODE=off: running fully deterministic")
