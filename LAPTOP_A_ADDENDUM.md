# Laptop A (Claude) – send this right after Prompt 1 finishes (before Prompt 2)

```
Important constraints for the rest of the build:
1. Always read files with encoding="utf-8". conversations.json crashes with the Windows default encoding.
2. The frontend is built separately (React, on another laptop). Do NOT build the Streamlit UI. Skip Prompt 10.
3. The FastAPI app (app/main.py) must expose EXACTLY this contract, with CORS allowing all origins:
GET  /health → {status:"ok", policy_versions:[...], model:"<model name>"}
GET  /customers?q=&limit=20 → [{customer_id, first_name, last_name, email, city, loyalty_tier, customer_segment, account_status}]
GET  /customers/{customer_id}/orders → [{order_id, order_date, total_amount, order_status, delivery_status, payment_status, refund_status}]
GET  /demo-scenarios → [{id, title, category, customer_id, message, expected_decision}]  (about 10, picked from REAL data at startup via queries: status, refund cap, ambiguity, OTP contradiction, fake order, injection, multi-intent, legal threat, window expired, payment pending)
POST /chat {customer_id, message, session_id} → {reply, decision:"ANSWER"|"ASK"|"ACT"|"ESCALATE", intents:[{type, order_id, decision, reason}], tool_calls:[{name, params, ok, result_summary}], refund_amount, escalate, ticket_id, policy_version, flags:[...], reasoning:[...], tokens:{input, output, llm_calls}, latency_ms}
POST /reset {session_id} → {ok:true}
Never return NaN; convert it to null. Run with: uvicorn app.main:app --host 0.0.0.0 --port 8000
Acknowledge, then wait for Step 2.
```
