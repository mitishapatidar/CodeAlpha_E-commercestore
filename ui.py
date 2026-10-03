"""NovaMart Support Agent - Streamlit console.

Run:  streamlit run ui.py
Talks to the FastAPI backend (API_URL); falls back to running the agent in-process
if the API isn't reachable, so the demo never breaks.
"""
from __future__ import annotations

import json
import os
import uuid

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").split(" #")[0].strip()
BADGE = {"ANSWER": ("#16a34a", "ANSWER"), "ASK": ("#2563eb", "ASK"), "ACT": ("#ea580c", "ACT"), "ESCALATE": ("#dc2626", "ESCALATE")}

st.set_page_config(page_title="NovaMart Support Agent", page_icon="🛒", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1100px;}
.badge {display:inline-block;padding:2px 10px;border-radius:999px;font-weight:700;font-size:0.78rem;color:white;letter-spacing:.04em;margin-right:6px}
.chip {display:inline-block;padding:2px 9px;border-radius:999px;font-size:0.74rem;background:#1f2633;color:#b9c0cf;margin:2px 4px 2px 0;border:1px solid #2a3242}
.pipeline {color:#8b93a7;font-size:0.82rem;margin-bottom:0.6rem}
.cust {background:#161b26;border:1px solid #2a3242;border-radius:10px;padding:10px 12px;font-size:0.86rem}
.small {font-size:0.8rem;color:#8b93a7}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ backend
@st.cache_resource
def backend_mode() -> str:
    try:
        httpx.get(f"{API_URL}/health", timeout=2).raise_for_status()
        return "api"
    except Exception:
        return "local"


def api_get(path: str, **params):
    if backend_mode() == "api":
        return httpx.get(f"{API_URL}{path}", params=params, timeout=30).json()
    from app import main
    route = {"/health": main.health, "/demo-scenarios": main.demo_scenarios,
             "/customers": main.customers}.get(path)
    if route:
        return route(**params)
    if path.startswith("/customers/") and path.endswith("/orders"):
        return main.customer_orders(path.split("/")[2])
    raise ValueError(path)


def send(customer_id: str, message: str, current_time: str | None) -> dict:
    payload = {"customer_id": customer_id, "message": message, "session_id": st.session_state.session_id,
               "current_time": current_time or None, "attachments": st.session_state.pop("attach", [])}
    if backend_mode() == "api":
        r = httpx.post(f"{API_URL}/chat", json=payload, timeout=90)
        r.raise_for_status()
        return r.json()
    from app.agent import run_turn
    from app.schemas import ChatRequest
    return run_turn(ChatRequest(**payload)).model_dump()


# ------------------------------------------------------------------- state
ss = st.session_state
ss.setdefault("session_id", uuid.uuid4().hex[:12])
ss.setdefault("chat", [])
ss.setdefault("customer_id", None)
ss.setdefault("now", "")


def reset_chat():
    ss.chat = []
    ss.session_id = uuid.uuid4().hex[:12]


# ----------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### 🛒 NovaMart Agent")
    health = api_get("/health")
    st.markdown(f"<span class='chip'>{'API' if backend_mode() == 'api' else 'in-process'}</span>"
                f"<span class='chip'>policies {', '.join(health['policy_versions'])}</span>", unsafe_allow_html=True)
    st.caption(f"Model: {health['model']}")

    st.markdown("#### Customer")
    q = st.text_input("Search by ID, email or name", value=ss.customer_id or "CUST-0", label_visibility="collapsed")
    results = api_get("/customers", q=q, limit=15) if q else []
    if results:
        labels = [f"{r['customer_id']} · {r['first_name']} {r['last_name']}" for r in results]
        ids = [r["customer_id"] for r in results]
        idx = ids.index(ss.customer_id) if ss.customer_id in ids else 0
        choice = st.selectbox("Customer", labels, index=idx, label_visibility="collapsed")
        new_id = ids[labels.index(choice)]
        if new_id != ss.customer_id:
            ss.customer_id = new_id
            reset_chat()
        cur = results[labels.index(choice)]
        st.markdown(f"<div class='cust'><b>{cur['first_name']} {cur['last_name']}</b><br>{cur['email']} · {cur['city']}<br>"
                    f"tier <b>{cur['loyalty_tier']}</b> · account <b>{cur['account_status']}</b></div>", unsafe_allow_html=True)
        with st.expander("Recent orders"):
            for o in api_get(f"/customers/{ss.customer_id}/orders"):
                st.markdown(f"<span class='small'><b>{o['order_id']}</b> · {o['order_date'][:10]} · {o['order_status']} · ₹{o['total_amount']:,}<br>"
                            f"{', '.join(o['items'])[:70]}</span>", unsafe_allow_html=True)
    else:
        st.info("No customer found.")

    st.markdown("#### Conversation time")
    ss.now = st.text_input("ISO time (blank = now, IST)", value=ss.now, placeholder="2026-10-03T12:00:00+05:30",
                           label_visibility="collapsed")
    c1, c2 = st.columns(2)
    if c1.button("📎 Attach photo", use_container_width=True):
        ss.attach = ["photo.jpg"]
        st.toast("Photo will be attached to your next message")
    if c2.button("↺ New chat", use_container_width=True):
        reset_chat()
        st.rerun()

    st.markdown("#### Demo scenarios")
    if st.button("🧹 Reset demo actions", use_container_width=True, help="Clears refunds/returns/tickets the agent created"):
        if backend_mode() == "api":
            httpx.post(f"{API_URL}/demo/reset", timeout=10)
        else:
            from app import main
            main.demo_reset()
        reset_chat()
        st.toast("Agent actions cleared")
    for i, sc in enumerate(api_get("/demo-scenarios")):
        if st.button(f"{sc['title']} → {sc['expected_decision']}", key=f"sc{i}", use_container_width=True, help=sc["category"]):
            reset_chat()
            ss.customer_id = sc["customer_id"]
            ss.now = sc.get("current_time") or ""
            ss.queued = sc["message"]
            st.rerun()


# -------------------------------------------------------------------- main
st.markdown("## NovaMart Support Agent")
st.markdown("<div class='pipeline'>guard → memory → intent (LLM #1) → verify → policy → decide → tools → reply (LLM #2)"
            " &nbsp;·&nbsp; <i>AI reasons, backend verifies, database stores truth.</i></div>", unsafe_allow_html=True)


def render_agent(r: dict):
    color, label = BADGE[r["decision"]]
    chips = [f"<span class='badge' style='background:{color}'>{label}</span>"]
    if r.get("refund_amount"):
        chips.append(f"<span class='chip'>refund ₹{r['refund_amount']:,.0f}</span>")
    if r.get("ticket_id"):
        chips.append(f"<span class='chip'>ref {r['ticket_id']}</span>")
    if r.get("policy_version"):
        chips.append(f"<span class='chip'>policy {r['policy_version']}</span>")
    for f in r.get("flags", []):
        chips.append(f"<span class='chip' style='border-color:#7f1d1d'>⚑ {f}</span>")
    chips.append(f"<span class='chip'>{r.get('parser')} · {r.get('reply_source')}</span>")
    tok = r.get("tokens", {})
    chips.append(f"<span class='chip'>{tok.get('llm_calls', 0)} LLM calls · {tok.get('input', 0) + tok.get('output', 0)} tok · "
                 f"{r.get('latency_ms', 0)} ms</span>")
    st.markdown(" ".join(chips), unsafe_allow_html=True)
    st.markdown(r["reply"])
    with st.expander("Agent trace"):
        t1, t2, t3, t4 = st.tabs(["Intents", f"Tools ({len(r['tool_calls'])})", "Reasoning", "Raw JSON"])
        with t1:
            for it in r["intents"]:
                c, _ = BADGE.get(it.get("decision", "ANSWER"), ("#555", ""))
                st.markdown(f"<span class='badge' style='background:{c}'>{it.get('decision', '-')}</span> "
                            f"**{it['type']}** {it.get('order_id') or ''} "
                            f"<span class='small'>{json.dumps({k: v for k, v in it.items() if k not in ('type', 'decision', 'order_id', 'index', 'source')})}</span>",
                            unsafe_allow_html=True)
        with t2:
            for c in r["tool_calls"]:
                write = c["name"].startswith(("create_", "escalate_"))
                st.markdown(f"{'🟠' if write else '🔹'} `{c['name']}` {'✓' if c.get('ok', True) else '✗'}")
                st.json({"params": c["params"], "result": c.get("result") or c.get("result_summary")}, expanded=False)
        with t3:
            for line in r["reasoning"]:
                st.markdown(f"- {line}")
        with t4:
            st.json(r, expanded=False)


for m in ss.chat:
    with st.chat_message("user" if m["role"] == "user" else "assistant", avatar="🧑" if m["role"] == "user" else "🛒"):
        if m["role"] == "user":
            st.markdown(m["text"])
        else:
            render_agent(m["data"])

prompt = st.chat_input("Message as the customer…") or ss.pop("queued", None)
if prompt and ss.customer_id:
    ss.chat.append({"role": "user", "text": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="🛒"):
        with st.spinner("Verifying…"):
            try:
                data = send(ss.customer_id, prompt, ss.now.strip() or None)
            except Exception as e:  # keep the console alive
                st.error(f"Backend error: {e}")
                st.stop()
        render_agent(data)
    ss.chat.append({"role": "agent", "data": data})
elif prompt:
    st.warning("Select a customer first.")
