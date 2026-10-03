# NovaMart Support Agent – Team Plan (Mantra Yudha)

## What we are building
An agentic customer-support backend for NovaMart (fictional e-commerce). For every customer message it must
**understand → verify → reason over policy → decide (ANSWER / ASK / ACT / ESCALATE) → call tools → reply.**
It gets scored by a hidden test harness (normal + edge + adversarial cases), not just by a demo.

## Core idea that wins: "LLM thinks, Python verifies"
The LLM never decides money or facts. It only:
1. turns the message into structured intents (JSON), and
2. writes the final reply from verified facts.

All verification, policy maths, and the decision itself happen in deterministic Python code over the dataset.
That gives no hallucination, injection resistance, correct numbers, and only 2 LLM calls per turn (efficiency points).

## Pipeline (one turn)
```
customer msg
  │
  ├─ 0. Guard: regex + flags → injection / legal threat / safety / harassment
  ├─ 1. Memory: get_customer, get_conversations, open tickets (always first)
  ├─ 2. LLM #1 Intent parser → {intents:[{type, order_id?, product_hint?, amount_claimed?, ...}]}
  ├─ 3. Verifier (Python): order exists? belongs to customer? multiple matches? OTP delivered? payment pending?
  ├─ 4. Policy engine (Python): ACTIVE policy version from data, window = order/delivery date + days
  │       (+ loyalty extension), restocking %, warranty, approval threshold, refund history
  │       refund = min(requested, order_value − restocking)
  ├─ 5. Decision engine (per intent, priority): SAFETY/LEGAL→ESCALATE > contradiction/fraud→ESCALATE
  │       > missing/ambiguous→ASK > eligible & under threshold→ACT > info→ANSWER
  ├─ 6. Tools: create_refund / create_return / create_support_ticket / escalate_to_human (verified params only)
  └─ 7. LLM #2 Response writer (gets only verified facts + decision; no internal fields like OTP/driver)
→ output: reply text + JSON {intent, decision, order_id, amount, action, tool_calls, escalate, reason}
```

## Hidden test categories → where we handle them
| Category | Handled in |
|---|---|
| Policy versions / mid-event mutation | policy loaded from data file, never hardcoded |
| Approval thresholds, refund limits | policy engine |
| Window arithmetic (+timezone, loyalty) | policy engine |
| Delivery claims (OTP-verified) | verifier → ESCALATE |
| Suspicious refunds (amount > value, many refunds) | verifier + decision |
| Ambiguity (2 matching orders, no ID) | verifier → ASK with list |
| Contradictory customers | verifier → ESCALATE |
| Warranty vs refund | policy engine |
| Prompt injection | guard + customer text wrapped as data; LLM can't trigger tools |
| Multi-intent | intent parser returns list; dependencies (refund waits on delivery) |
| Payment issues (pending payment) | verifier → no action |
| Safety / legal / self-harm | guard → ESCALATE, empathetic, no arguing |
| Memory ("already sent yesterday") | conversations + tickets loaded first |

## Stack (fast to build)
- Python + FastAPI (`/chat` endpoint) + pandas/SQLite over the dataset
- LLM: Gemini / GPT / Claude with JSON output (whichever API key we have)
- UI: Streamlit chat showing decision badge + tool-call trace + reasoning (good for demo)

## Team split
1. **Lead**: decision engine + integration + architecture doc
2. **Data/Policy**: data loader, tools, policy engine, verifier
3. **AI/Prompts**: intent-parser and response prompts, injection guard, prompt strategy doc
4. **UI/Test/Pitch**: Streamlit UI, test cases for all 13 categories, README, demo video

## Submission checklist
Public GitHub repo · README (setup/run) · requirements.txt · architecture diagram · models + versions ·
prompt/agent strategy doc · known limitations · 3–5 min demo video · prompt log.
