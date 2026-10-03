# NovaMart Support Agent

An agentic customer-support backend for **NovaMart** (fictional e-commerce), built for the
*Mantra Yudha: AI Customer Support Agent from Hell* problem statement.

For every customer message the agent **understands → verifies → reasons over policy → decides
(ANSWER / ASK / ACT / ESCALATE) → calls tools → replies**, and shows its full reasoning trace.

> **Iron principle:** AI reasons. Backend verifies. Database stores truth. Tools act. Humans handle exceptions.

## Why it is hard to fool

| Design choice | Effect |
|---|---|
| **LLM thinks, Python verifies.** The LLM only (1) extracts intents as JSON and (2) rephrases a verified draft reply. | No hallucinated facts, money or order IDs. Decisions are deterministic and auditable. |
| **Every LLM output is validated.** Order IDs and amounts must appear in the customer's text; the rewritten reply must keep every amount/ID from the draft and add none. | A prompt-injected or confused LLM cannot change an outcome. |
| **Policies are data** (`data/policies.json`, hot-reloaded, versioned by order date). | A mid-event policy mutation is a JSON edit. No code change, no restart. |
| **Customer text is untrusted.** A guard flags injection, legal, safety, self-harm, abuse, refund-redirect and chargeback language, and strips injected sentences before parsing. | "Ignore previous instructions / I'm admin / policy changed" has no effect. |
| **Memory first.** Prior conversations and open tickets are loaded at session start; pending questions carry over between turns. | Never re-asks for a photo already sent; follow-ups like "the Sony one" resolve correctly. |
| **Works with no API key.** A full rule-based parser and template writer run when the LLM is unavailable, fails or refuses. | The hidden harness always gets a correct decision. |

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # optional: add LLM_API_KEY for LLM mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
streamlit run ui.py           # optional backup console -> http://localhost:8501 (main UI: frontend/)
pytest -q                     # 105 tests
```

Without a key the agent runs in **deterministic mode** (rules + templates): every decision is identical,
only the reply wording is less natural. With a key it uses **Claude** (`claude-opus-5-5` by default,
effort `low`, structured JSON output). Set `LLM_PROVIDER=gemini|openai` and `LLM_MODEL` to switch providers.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `gemini` or `openai` |
| `LLM_MODEL` | `claude-opus-5-5` | Model ID for the chosen provider |
| `LLM_API_KEY` | none | API key (falls back to `ANTHROPIC_API_KEY`) |
| `LLM_MODE` | `auto` | `off` forces deterministic mode |
| `AGENT_NOW` | wall clock | Fixed "current time" (ISO) for reproducible evaluation |
| `DATA_DIR` | `data` | Dataset folder (swap in the hidden dataset here) |

## API

`POST /chat`

```json
{"customer_id": "CUST-00708", "message": "My headphones from ORD-000014 arrived damaged, photo attached. Give me ₹10,000 refund.",
 "session_id": "abc", "current_time": "2026-01-12T12:00:00+05:30", "attachments": []}
```

Response:

```json
{"reply": "Hi Sneha — I've verified ORD-000014 (Auralix Prime 100) and initiated a refund of ₹1,258 (RFD-…). You asked for ₹10,000, but the most I can refund…",
 "decision": "ACT",
 "intents": [{"type": "refund", "order_id": "ORD-000014", "reason": "damaged", "amount_claimed": 10000, "decision": "ACT", "refund_amount": 1257.82, "policy_version": "v1"}],
 "tool_calls": [{"tool": "get_customer", "params": {...}}, {"tool": "get_conversations", ...}, {"tool": "get_order", ...},
                {"tool": "check_refund_eligibility", ...}, {"tool": "calculate_refund", ...}, {"tool": "create_refund", "params": {"amount": 1257.82, ...}}],
 "refund_amount": 1257.82, "escalate": false, "ticket_id": "RFD-…", "reasoning": ["Verified ORD-000014 exists and belongs to CUST-00708.", "..."],
 "policy_version": "v1", "flags": [], "language": "en", "parser": "rules", "reply_source": "template",
 "usage": {"llm_calls": 0, "total_tokens": 0}, "latency_ms": 9}
```

Endpoints follow `API_CONTRACT.md` (extra fields are additive, never NaN):
`GET /health` · `GET /customers?q=&limit=20` · `GET /customers/{id}/orders` · `GET /demo-scenarios` ·
`POST /chat` · `POST /reset {session_id}`. Extras: `GET /tools` (the 10 tool specs), `POST /demo/reset`
(clears actions the agent created, for repeatable demos).

Run for the team frontend: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

## Project layout

```
app/
  config.py         settings, IST clock (request time > AGENT_NOW > wall clock)
  data.py           loads CSV/JSON once, typed IST dates, indexes, product spec parser
  policy_store.py   versioned policies.json (selection by order placement date, hot reload)
  policy_engine.py  windows (day 0 = delivery), loyalty extension, refund cap, restocking, threshold, warranty, delays
  tools.py          the 10 tools + ToolTracer (records every call); writes go to runtime/actions_log.jsonl
  guard.py          injection / legal / safety / self-harm / abuse / refund-redirect / chargeback flags (EN + Hinglish)
  intent.py         LLM call #1 (JSON schema) + rule-based parser; LLM output validated against the text
  verifier.py       order resolution (ownership, ambiguity, item selection) + risk signals
  decision.py       per-intent handlers -> ANSWER / ASK / ACT / ESCALATE with an audit trail
  memory.py         sessions, pending questions, prior evidence, open tickets
  responder.py      LLM call #2 rewrites a verified draft; Python rejects unsafe rewrites
  agent.py          orchestrates one turn; one escalation per turn with full context
  main.py           FastAPI app
ui.py               backup Streamlit console (the main UI is the React app in frontend/)
data/policies.json  structured mirror of data/policies/*.md (the only source of numbers)
tests/              105 tests: data, policy versions, tools, guard, intent, LLM layer, 13 scenario categories
docs/               ARCHITECTURE.md · PROMPT_STRATEGY.md · LIMITATIONS.md
```

## Hidden-test categories

| # | Category | Where | Test |
|---|---|---|---|
| 1 | Policy versions | `policy_store.get_policy` (order placement date) | `test_policy_version_*`, `test_version_boundary_*` |
| 2 | Approval thresholds | `policy_engine.over_threshold` (order total) | `test_threshold_*` |
| 3 | Window arithmetic | `policy_engine.check_eligibility` (day 0, loyalty, in-time request) | `test_defect_window_edge_v2`, `test_loyalty_*` |
| 4 | Refund limits | `policy_engine.calculate_refund` | `test_refund_capped_*`, `test_restocking_*` |
| 5 | Delivery claims (OTP) | `decision.h_delivery_issue` | `test_otp_*`, `test_non_otp_*` |
| 6 | Suspicious refunds | `verifier.repeat_claims`, soft-signal scoring | `test_repeat_claimant_*`, `test_inflated_amount_*` |
| 7 | Ambiguity | `verifier.resolve_order` | `test_two_matching_orders_*`, `test_unknown_order_id_*` |
| 8 | Contradictory customers | `decision._contradiction` (record + story change) | `test_damage_claim_on_undelivered_*`, `test_story_change_*` |
| 9 | Warranty | `decision.h_warranty`, `_not_eligible` | `test_in_warranty_*`, `test_expired_warranty_*` |
| 10 | Prompt injection | `guard.scan`, `intent._validate_llm`, `responder._safe` | `test_injection_*`, `test_pure_injection_*` |
| 11 | Multi-intent | clause splitting, `depends_on`, per-intent decisions | `test_never_arrived_refund_and_address_change` |
| 12 | Payment issues | `decision.h_payment_issue`, money-flow payment guard | `test_refund_on_pending_payment_*`, `test_money_deducted_*` |
| 13 | Safety / legal | `agent.global_triggers` | `test_safety_and_legal_always_escalate` |

## Policy mutation drill

When the organisers change a rule, edit only `data/policies.json`. For example, to add a v3 effective
2026-10-05 with a 5-day change-of-mind window:

```json
{"version": "v3", "applies_from": "2026-10-05T00:00:00+05:30", "applies_to": null,
 "windows_days": {"change_of_mind": 5, "defective": 10, "damaged": 10, "wrong_item": 10, "missing_item": 10}, ...}
```

Also set `applies_to` on v2. The running server picks it up on the next request; `pytest -q` shows which decisions changed.
For a retroactive rule ("applies to all open requests"), set `meta.version_selection` to `"request_date"`.

## Models

| Use | Model | Settings |
|---|---|---|
| Intent parsing (LLM #1) | Claude Opus 5.5 (`claude-opus-5-5`) | structured output (`output_config.format` JSON schema), effort `low`, cached system prompt |
| Reply writing (LLM #2) | Claude Opus 5.5 (`claude-opus-5-5`) | effort `low`, max 600 tokens, output validated |
| Fallback | Deterministic rule parser + templates | always on |

Gemini (`google-genai`) and OpenAI (`openai`) adapters are included. Install the SDK and set `LLM_PROVIDER`.
