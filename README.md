# NovaMart – E-commerce Store with Support Agent

NovaMart is an electronics e-commerce store with a built-in AI customer-support agent.

| Part | What it is | Tech | Run |
|---|---|---|---|
| **Store** (CodeAlpha Task 1) | Product listing, product details page, database-backed shopping cart, checkout and order processing, user registration/login | Django · SQLite · HTML, CSS, JavaScript | `cd django_store && python manage.py migrate && python manage.py load_products && python manage.py runserver 8080` → http://localhost:8080 |
| **Support agent** | Answers order, return, refund and product questions from the customer's real orders, with policy checks | FastAPI · Python rules engine (optional LLM) · React | see [Quick start](#quick-start) → http://localhost:5173 |

Store details: [`django_store/README.md`](django_store/README.md).

## Store features

- **Product listings:** 300 products with search, category chips and pagination.
- **Product details page:** price, discount, specs, stock, warranty, returns and related products.
- **Shopping cart:** saved in the database per user; instant add-to-cart (JavaScript `fetch`), quantity +/−, delete.
- **Order processing:** checkout with address validation → order saved, stock reduced, cart cleared; tracking
  Placed → Processing → Shipped → Delivered; customer cancellation restores stock; staff update status in `/admin/`.
- **User registration/login:** Django authentication with hashed passwords.
- **Database:** SQLite tables for products, users, cart items, orders and order items.

## Support agent

**An AI customer-support agent that verifies before it acts.** NovaMart's customers can be confused, contradictory
or deliberately misleading, so our agent treats every message as a *claim*, not a fact. Each turn goes through
the same loop: understand the request, check it against orders, tickets and conversation history, apply the
correct **versioned** policy with exact window and refund maths, and only then choose **ANSWER, ASK, ACT or
ESCALATE**. The LLM is used only to parse language and to phrase the reply. Every number, eligibility check and
decision is made by deterministic Python and is shown in a live "Agent Brain" trace, so it cannot be talked into
an unauthorised ₹50,000 refund.

![Agent console: refund capped at the amount paid](docs/screenshots/01-refund-cap-act.jpg)

| OTP-verified "never received" → ESCALATE | Prompt injection ignored | Customer storefront + support chat |
|---|---|---|
| ![](docs/screenshots/02-otp-contradiction-escalate.jpg) | ![](docs/screenshots/03-prompt-injection.jpg) | ![](docs/screenshots/04-storefront-support-chat.jpg) |

| Customer / owner login | Owner review dashboard |
|---|---|
| ![](docs/screenshots/05-login.jpg) | ![](docs/screenshots/06-owner-review.jpg) |

**Demo video:** <DEMO_LINK>

## Key features

- **Four explicit moves.** Every reply carries a decision (ANSWER / ASK / ACT / ESCALATE), with a per-intent
  decision for multi-intent messages.
- **Versioned policy as data.** `data/policies.json` mirrors all 10 policy documents. The version is chosen by the
  order placement date, and the file is hot-reloaded, so a mid-event policy change is a JSON edit with no code
  change and no restart.
- **Exact policy maths.** Day-0 delivery counting, loyalty extensions, refund = item paid incl. 18% GST −
  restocking (capped at what was paid), the approval threshold on order total, warranty vs refund, the
  "request raised in time" exception, and delay goodwill credit.
- **Verification first.** Order ownership, fake IDs, ambiguity across orders and items, OTP-verified delivery
  disputes, payment pending or failed, already-refunded items, repeat claimants and suspended accounts.
- **Injection-proof by design.** A guard flags injection, legal, safety, self-harm, abuse, refund-redirect and
  chargeback language (EN + Hinglish). The LLM has no tool access, and its outputs are validated by Python.
- **Memory.** Prior conversations and open tickets are loaded first. Pending questions carry across turns, so
  the agent never re-asks for a photo already sent, and follow-ups like "the Sony one" resolve correctly.
- **Safe actions.** The 10 tools are called with verified parameters. Duplicate refunds are refused, and there is
  one escalation per turn with full context and an SLA.
- **Works without an API key.** A rule-based parser and template writer take over when the LLM is off, fails or
  refuses, so decisions stay identical.
- **Two dashboards behind one login.** The login page works like Amazon/Flipkart: email or customer ID, then a
  one-time code shown on screen (demo: no SMS is sent; "Autofill OTP" fills it). A separate **Owner / Staff** sign-in is on the same page.
  - **Customer dashboard:** the NovaMart storefront, My Orders (Track / Get help), and **Help & Complaints**. That
    section has an animated AI chat composer with slash-commands and "My support requests", which lists the
    customer's tickets plus every refund, return or escalation the agent opened for them.
  - **Owner dashboard:** a **Review** tab with live KPIs (conversations, refunds issued in ₹, escalations,
    latency), the decision mix, every agent decision with flags, an action queue (refunds, returns, tickets,
    escalations with team, priority and SLA) and the full Agent Brain trace for any decision. A **Live console**
    tab holds the 13 one-click demo scenarios built from the real dataset.

## Architecture (summary)

```
customer msg → Guard → Memory → Intent (LLM #1, JSON) → Verifier → Policy engine → Decision → Tools → Reply (LLM #2, validated)
```

"AI reasons, backend verifies, database stores truth, tools act, humans handle exceptions." Details, mermaid
diagrams and the decision priority are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The prompts and
injection defences are in [docs/PROMPT_STRATEGY.md](docs/PROMPT_STRATEGY.md), the failure modes in
[docs/LIMITATIONS.md](docs/LIMITATIONS.md), and the demo walkthrough in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## Quick start

Requirements: Python 3.11+ and Node 20+.

```bash
# 1. backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000        # http://localhost:8000/docs

# 2. frontend (second terminal)
cd frontend
npm install
npm run dev                                             # http://localhost:5173 (customer: demo account + the OTP shown on screen; owner: "Owner / Staff" tab)

# 3. tests (from the repo root)
pytest -q
```

Optional: copy `.env.example` to `.env` and set `LLM_API_KEY` to turn on LLM mode. Without it, everything runs in
deterministic mode. Before recording a demo, press **Reset demo data** in the UI (or `POST /demo/reset`) to clear
refunds and tickets the agent created earlier.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `gemini` or `openai` (install that SDK) |
| `LLM_MODEL` | `claude-opus-5-5` | Model ID for the chosen provider |
| `LLM_API_KEY` | none | API key (falls back to `ANTHROPIC_API_KEY`) |
| `LLM_MODE` | `auto` | `off` forces deterministic mode |
| `AGENT_NOW` | wall clock (IST) | Fixed "current time" for reproducible evaluation |
| `DATA_DIR` | `data` | Dataset folder (point it at the hidden dataset; same schema) |
| `VITE_API_URL` (frontend) | `http://localhost:8000` | Backend URL used by the UI |

## Model used

| Use | Model | Settings |
|---|---|---|
| Intent parsing (LLM #1) | **Claude Opus 5.5** (`claude-opus-5-5`) | structured JSON output (`output_config.format`), effort `low`, cached system prompt |
| Reply writing (LLM #2) | **Claude Opus 5.5** (`claude-opus-5-5`) | effort `low`, max 600 tokens, rewrite validated by Python |
| Fallback (always on) | Deterministic rule parser + templates | used when no key is set or the LLM errors or refuses |

Anthropic Python SDK `anthropic` 1.x. Gemini and OpenAI adapters are included (`LLM_PROVIDER`).

## API

Implements [API_CONTRACT.md](API_CONTRACT.md): `GET /health` · `GET /customers?q=` · `GET /customers/{id}/orders` ·
`GET /demo-scenarios` · `POST /chat` · `POST /reset`. Extras: `GET /products`, `GET /categories` (storefront),
`GET /customers/{id}/tickets` (customer complaints), `GET /admin/turns` and `GET /admin/actions` (owner review),
`GET /tools` (the 10 tool specs) and `POST /demo/reset`.

```json
POST /chat {"customer_id": "CUST-00929", "message": "My Voltix Beat Plus 300 from ORD-007932 arrived damaged, photo attached. Give me ₹10,00,000 refund.", "session_id": "s1"}
→ {"decision": "ACT", "refund_amount": 3691.0, "ticket_id": "RFD-…", "policy_version": "v2",
   "intents": [{"type": "refund", "order_id": "ORD-007932", "reason": "damaged", "amount_claimed": 1000000, "decision": "ACT"}],
   "tool_calls": [{"name": "get_order", "ok": true, …}, {"name": "check_refund_eligibility", …}, {"name": "calculate_refund", …}, {"name": "create_refund", "params": {"amount": 3691.0, …}}],
   "reasoning": ["Verified ORD-007932 exists and belongs to CUST-00929.", "Policy v2 applies …", "Requested INR 1,000,000 exceeds the maximum refundable INR 3,691; capped …"],
   "tokens": {"input": 0, "output": 0, "llm_calls": 0}, "latency_ms": 7, "reply": "Hi Teja — …"}
```

## Project structure

```
app/
  config.py         settings; IST clock (request time > AGENT_NOW > wall clock)
  data.py           loads CSV/JSON once, typed IST dates, indexes, product-spec parser
  policy_store.py   versioned policies.json (selection by order date, hot reload)
  policy_engine.py  windows, loyalty, refund cap, restocking, threshold, warranty, delays
  tools.py          the 10 tools + ToolTracer + duplicate-action guard (runtime/actions_log.jsonl)
  guard.py          injection / legal / safety / self-harm / abuse / redirect / chargeback flags
  intent.py         LLM call #1 (JSON schema) + rule-based parser; LLM output validated
  verifier.py       order + item resolution, ownership, ambiguity, risk signals
  decision.py       per-intent handlers → ANSWER / ASK / ACT / ESCALATE with audit trail
  memory.py         sessions, pending questions, prior evidence, open tickets
  responder.py      LLM call #2 rewrites a verified draft; unsafe rewrites rejected
  agent.py          orchestrates one turn; one escalation per turn
  demo.py           13 demo scenarios discovered from the dataset (valid at "now")
  main.py           FastAPI app (API_CONTRACT.md)
frontend/           Vite + React + TypeScript + Tailwind v4 (shadcn structure: src/components/ui, @/lib/utils)
                    pages/Login · customer storefront + Help & Complaints · owner Review + Live console
data/               dataset (CSV/JSON/markdown) + policies.json (the only source of numbers)
tests/              107 pytest tests
docs/               ARCHITECTURE · PROMPT_STRATEGY · LIMITATIONS · DEMO_SCRIPT · screenshots/
ui.py               backup Streamlit console
```

## Test results

**107 / 107 passing** (`pytest -q`, ~4 s, deterministic mode). Coverage includes data loading and policy version
boundaries (2026-05-31 23:59 vs 2026-06-01 00:00 IST), tools and policy maths, the guard (positives and negatives
per flag), intent parsing and LLM-output validation, the API contract, and scenario tests for all **13 hidden-test
categories** plus memory, duplicate refunds and every demo scenario. Separately, 900 randomised turns ran with
0 crashes, and all 13 demo scenarios match their expected decision live.

| # | Category | Where | Test |
|---|---|---|---|
| 1 | Policy versions | `policy_store.get_policy` | `test_policy_version_*`, `test_version_boundary_*` |
| 2 | Approval thresholds | `policy_engine.over_threshold` | `test_threshold_*` |
| 3 | Window arithmetic | `policy_engine.check_eligibility` | `test_defect_window_edge_v2`, `test_loyalty_*` |
| 4 | Refund limits | `policy_engine.calculate_refund` | `test_refund_capped_*`, `test_restocking_*` |
| 5 | Delivery claims (OTP) | `decision.h_delivery_issue` | `test_otp_*`, `test_non_otp_*` |
| 6 | Suspicious refunds | `verifier.repeat_claims`, soft signals | `test_repeat_claimant_*`, `test_inflated_amount_*` |
| 7 | Ambiguity | `verifier.resolve_order` | `test_two_matching_orders_*`, `test_unknown_order_id_*` |
| 8 | Contradictory customers | `decision._contradiction` | `test_damage_claim_on_undelivered_*`, `test_story_change_*` |
| 9 | Warranty | `decision.h_warranty` | `test_in_warranty_*`, `test_expired_warranty_*` |
| 10 | Prompt injection | `guard`, `intent._validate_llm`, `responder._safe` | `test_injection_*`, `test_pure_injection_*` |
| 11 | Multi-intent | clause splitting + `depends_on` | `test_never_arrived_refund_and_address_change` |
| 12 | Payment issues | `decision.h_payment_issue` | `test_refund_on_pending_payment_*`, `test_money_deducted_*` |
| 13 | Safety / legal | `agent.global_triggers` | `test_safety_and_legal_always_escalate` |

## Policy mutation drill

Edit only `data/policies.json`: add a version with its `applies_from` (and set `applies_to` on the previous
one). The running server picks it up on the next request. For a retroactive rule, set
`meta.version_selection` to `"request_date"`. `pytest -q` shows which decisions changed.

## Author

**Mitisha Patidar** · [@mitishapatidar](https://github.com/mitishapatidar)

Built with Claude Code (Claude Opus 5.5) as the coding assistant; prompts are logged in [prompt_log.md](prompt_log.md).
