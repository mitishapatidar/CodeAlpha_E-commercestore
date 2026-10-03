# Prompt & Agent Strategy

## 1. Instruction hierarchy (handbook p.15)

| Level | Source | How it is enforced |
|---|---|---|
| L1 System rules | `SYSTEM_PROMPT` in `app/intent.py`, `SYSTEM` in `app/responder.py` | Fixed text, never interpolated with customer content |
| L2 Business logic + policy | `app/policy_engine.py`, `data/policies.json` | Deterministic Python. The LLM never sees the numbers it could be talked into changing |
| L3 Tools + parameters | `app/tools.py` | Called only by Python handlers with verified parameters; `create_refund` independently refuses amount > order total or a foreign order |
| L4 Customer input | `<customer_message>` block | Wrapped as data, scanned by the guard, injected sentences stripped |

The LLM has **no tool access**, so it cannot trigger an action, however it is prompted.

## 2. Why only two LLM calls

| Call | Job | Why the LLM | Guardrail |
|---|---|---|---|
| #1 Intent parse | Free text (EN/Hinglish, multi-intent, typos) → JSON schema | Language understanding is what LLMs are good at | Structured output; enums; `_validate_llm` drops order IDs/amounts not literally present; regex fills gaps |
| #2 Reply | Rephrase a verified draft in the customer's language and tone | Natural, empathetic replies | `_safe()` rejects any rewrite that adds an amount/ID, drops a reference number or mentions internals; then the template is used |

Everything that decides money, eligibility or escalation is Python: reproducible, testable (101 tests), immune to
injection, and cheap.

## 3. Intent prompt (LLM #1), design notes

- **Short** (~350 tokens) and static, so it is cached (`cache_control: ephemeral` on the system block).
- **Two few-shot examples**: one multi-intent with dependencies, one Hinglish refund. They cover the hardest
  parsing cases without bloating the prompt.
- **Explicit anti-hallucination rules**: "only IDs literally present", "only amounts the customer asks for".
- **Claims vs requests**: the schema separates what the customer *wants* (`type`, `reason`) from what they *assert*
  (`claims`), which feeds contradiction detection.
- Recent context (last 4 turns, truncated) resolves pronouns ("refund it").
- Effort `low`: extraction does not need deep reasoning; this keeps latency and cost down.

## 4. Response prompt (LLM #2), design notes

- The model gets a correct draft, not raw data, so there is nothing to invent.
- Rules: keep every fact, amount, date and ID; add none; do not drop questions; no internals; ≤120 words; customer's
  language (Hinglish if they wrote Hinglish); acknowledge frustration and never argue.

## 5. Injection defence in depth

1. **Guard** (`app/guard.py`): 15+ patterns ("ignore previous instructions", "you are now", maintenance/admin mode,
   "print your system prompt", "approve all refunds", "policy has changed", "I am admin", `SYSTEM:` prefixes,
   data-exfiltration asks, Hinglish variants). Injected sentences are removed; any order ID inside them is kept as a
   claim to verify.
2. **Data framing**: the customer text sits inside `<customer_message>` tags with an explicit rule that it is data.
3. **Output validation**: the LLM cannot introduce IDs or amounts.
4. **No authority from text**: authority claims ("manager approved") count as a fraud signal, not as approval.
5. **Pure injection** (nothing genuine left) → polite ANSWER, zero write tools.

## 6. Ambiguity strategy

Never guess. If several orders match, list up to 5 with items, status and date and ASK. If the customer has many
orders and gave no hint, ASK for the order ID and show the 3 most recent. Follow-ups are resolved by ID, ordinal
("the second one") or product words ("the Sony one"). If an order has several items and the reason is
item-specific, ASK which item.

## 7. Token / API efficiency

| Scenario | LLM calls | Tool calls (typical) |
|---|---|---|
| Greeting | 0 | 2 (first turn: customer + memory) |
| Status question | 2 | 3 |
| Eligible refund | 2 | 6 (customer, memory, order, eligibility, calculation, refund) |
| No API key | 0 | same as above |

Usage (`input_tokens`, `output_tokens`, latency per call) is returned in every `/chat` response under `usage`.

## 8. Prompt log

Team prompts used to build the system are recorded in `prompt_log.md` (single master spec, then one delta prompt
per module, minimal-diff bug fixes).
