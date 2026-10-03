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

## Specific failure modes we know about
- **Delivered-but-damaged without the word "photo"**: a defect claim with no evidence → ASK for photos even if the
  customer insists. This follows Return Policy §4, but a harness that expects ACT on a bare claim would mark it ASK.
- **Held dependent intents show as ANSWER**: in "never arrived, refund it", the refund intent is *held* behind the
  delivery investigation; the per-intent label is ANSWER (with "Held" in the reasoning). The turn decision is
  ESCALATE.
- **One escalation per turn**: several triggers (e.g. legal + safety) are merged into one ticket routed to the
  most severe team; the other teams are listed in the reason text only.
- **Keyword guard false positives/negatives**: product names can collide with risk words (we fixed "Spark"), and
  creative phrasing ("I'll see you in court-ish") can slip through. The LLM path widens intent coverage but the
  guard itself stays regex-based.
- **Latest-order fallback**: "where is my order?" with nothing in transit answers about the most recent order.
- **Demo scenarios depend on the clock**: `/demo-scenarios` picks rows valid *today*; on a different date it picks
  different orders (by design), and the refund scenario needs `POST /demo/reset` before it can ACT again.
- **UI**: the console shows tokens = 0 in deterministic mode; the storefront cart and product pages are visual only
  (no checkout); sign-in is a demo account picker, not authentication.
