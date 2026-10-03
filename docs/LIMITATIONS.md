# Known Limitations & Failure Modes

We would rather document a boundary than hide it.

## Understanding
- **Rule-parser coverage.** Without an API key, intents come from regex/keyword rules (English + common Hinglish).
  Unusual phrasing, other Indian languages or heavy typos may be parsed as `other` → the agent ASKs to clarify
  (safe, but an extra turn). With the LLM enabled, coverage is much wider and still validated.
- **Product matching** is keyword-based (category synonyms, brand, name words). Vague references ("the thing I got
  last month") lead to ASK, not a guess.
- **Dates in free text** ("delivered yesterday") are not parsed as claims, so contradictions about *dates* are not
  detected. Delivery-status contradictions are.

## Policy interpretation choices
- **Approval threshold** is judged on the **order total**, as the policy text states ("a ₹600 return from a ₹90,000
  order needs approval"), not on the refund amount.
- **Evidence**: defect/damage/wrong/missing claims need photos before any action (Return Policy §4). Evidence counts
  as provided if the customer says so, attaches a file (`attachments`), or a prior conversation shows it. We cannot
  inspect images.
- **Amount above order value** alone is capped and processed (handbook example 02). It escalates only together with
  a second risk signal or a legal threat.
- **Abuse**: mild abuse gets one calm warning (policy: "after one calm warning"). Threats escalate immediately.
- **Overall decision for mixed turns** uses ESCALATE > ACT > ASK > ANSWER. A turn that both acts on one order and
  asks about another reports ACT; the per-intent decisions are in `intents[]`.
- **Lost orders**: the agent offers refund or replacement (ASK) unless the customer already asked for a refund.
- **Refund to another account** always escalates to Payments (refund policy §9), with a security explanation.

## Actions
- Write tools append to `runtime/actions_log.jsonl`; they do not mutate the dataset. The agent indexes that log, so a
  second refund/return/cancellation for the same order item is refused ("already in progress") across turns and
  sessions. Production would write to the order system instead.
- There is no dedicated `cancel_order` / `update_address` tool in the 10-tool spec, so these are executed as
  `create_support_ticket` (+ `create_refund` for prepaid cancellations).
- Goodwill delay credit is computed and offered, not issued (no wallet tool in the spec).

## Memory
- Sessions are in-process memory (lost on restart, single instance). Production would use Redis.
- "I already sent it yesterday" in a new session is resolved from open tickets / the latest prior conversation
  with an order. If the history is ambiguous, the agent asks.

## LLM
- The live LLM path was verified with a fake client and request-shape tests, but not against the real API during
  the build (no key in the build environment). Any LLM error, refusal or timeout falls back to the deterministic path.
- Server-side refusal fallbacks (`fallbacks: "default"`) are not enabled; the local deterministic fallback covers
  refusals instead.

## Data
- Policy markdown → `policies.json` was transcribed by hand. A new policy file needs a matching JSON edit.
- Timezone: all dates are treated as IST (`+05:30`); delivery dates have no time, so "48 hours" uses day granularity.
