# API CONTRACT (backend ↔ frontend) – v1

Base URL: `http://<laptop-A-IP>:8000`. CORS allows all origins. All JSON. Money is INR as a number. Missing values are `null` (never NaN).

## GET /health
`{"status":"ok","policy_versions":["v1","v2"],"model":"<model name>"}`

## GET /customers?q=<text>&limit=20
Searches customer_id / name / email.
`[{"customer_id","first_name","last_name","email","city","loyalty_tier","customer_segment","account_status"}]`

## GET /customers/{customer_id}/orders
`[{"order_id","order_date","total_amount","order_status","delivery_status","payment_status","refund_status"}]` newest first.

## GET /demo-scenarios
About 10 scenarios built from REAL data:
`[{"id","title","category","customer_id","message","expected_decision"}]`

## POST /chat
Request: `{"customer_id":"CUST-00615","message":"...","session_id":"<uuid>"}`
Response:
```json
{
  "reply": "string",
  "decision": "ANSWER | ASK | ACT | ESCALATE",
  "intents": [{"type":"refund","order_id":"ORD-000001","decision":"ACT","reason":"..."}],
  "tool_calls": [{"name":"get_order","params":{},"ok":true,"result_summary":"..."}],
  "refund_amount": 2499,
  "escalate": false,
  "ticket_id": null,
  "policy_version": "v1",
  "flags": ["injection"],
  "reasoning": ["step 1 ...", "step 2 ..."],
  "tokens": {"input": 0, "output": 0, "llm_calls": 2},
  "latency_ms": 850
}
```

## POST /reset
Request `{"session_id":"..."}` → `{"ok":true}`
