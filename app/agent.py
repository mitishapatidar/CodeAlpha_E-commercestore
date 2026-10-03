"""Agent orchestrator: one customer turn end to end.

  0 guard -> 1 memory -> 2 intent (LLM #1) -> 3 verify -> 4 policy -> 5 decide -> 6 tools -> 7 reply (LLM #2)

"AI reasons, backend verifies, database stores truth, tools act, humans handle exceptions."
"""
from __future__ import annotations

import re
import time
import uuid

from app import decision as dec
from app.config import now_ist
from app.decision import Ctx, Outcome, inr
from app.guard import scan
from app.intent import Intent, ParseResult, _reason, extract_order_ids, parse, product_hint, to_jsonable
from app.llm import Usage
from app.memory import SESSIONS, Session, agent_asked_for_photo
from app.policy_store import section
from app.responder import template_reply, write_reply
from app.schemas import ChatRequest, ChatResponse, ToolCall
from app.tools import ToolTracer

YES = re.compile(r"\b(yes|yeah|yep|yup|sure|ok|okay|go ahead|please do|do it|haan|han|ha|ji|theek|thik|confirm|proceed)\b", re.I)
NO = re.compile(r"^\s*(no|nope|nah|nahi|not now|no thanks|don'?t)\b", re.I)
ORDINALS = {"first": 0, "1st": 0, "pehla": 0, "second": 1, "2nd": 1, "doosra": 1, "dusra": 1, "third": 2, "3rd": 2, "last": -1}
SEVERITY = {"critical": 3, "high": 2, "medium": 1, "low": 0}


# ---------------------------------------------------------------- triggers
def global_triggers(g, session: Session) -> tuple[list[dict], list[str]]:
    """Message-level escalation triggers that override normal handling. Returns (triggers, lines for the reply)."""
    teams = section("escalation")["teams"]
    trig, lines = [], []
    if g.has("self_harm"):
        trig.append({"team": teams["self_harm"], "priority": "critical", "reason": "self-harm language"})
        lines.append("I'm really sorry you're going through this, and I want to make sure you're safe. Please reach out "
                     "to Tele-MANAS on 14416 (free, 24x7) or someone you trust right now. I'm also connecting you with a "
                     "member of our team.")
    if g.has("safety"):
        trig.append({"team": teams["safety"], "priority": "critical", "reason": "product safety incident: " + ", ".join(g.flags["safety"])})
        lines.append("For your safety, please stop using and charging the device immediately, unplug it and keep it "
                     "away from anything flammable. I'm escalating this as a critical safety incident.")
    if g.has("legal_threat"):
        trig.append({"team": teams["legal"], "priority": "high", "reason": "legal / regulatory threat"})
        lines.append("I understand how frustrating this is. I've escalated your case to our Customer Experience team, "
                     "who handle formal concerns like this.")
    if g.has("threat") or (g.has("abuse") and session.warned_abuse):
        trig.append({"team": teams["harassment"], "priority": "high", "reason": "abusive/threatening language toward staff"})
        lines.append("I want to help, but I can't continue the conversation in this tone, so I've handed it to our "
                     "Customer Experience team.")
    if g.has("chargeback"):
        trig.append({"team": teams["chargeback"], "priority": "high", "reason": "chargeback/bank dispute already raised"})
        lines.append("Since a dispute is already open with your bank, a second refund can't be issued here; our Refunds & "
                     "Payments team will coordinate with the bank.")
    if g.has("refund_to_other_account"):
        trig.append({"team": teams["refund_destination"], "priority": "high",
                     "reason": "refund requested to a different account/instrument"
                               + (" (original instrument unavailable)" if g.has("original_instrument_unavailable") else "")})
        lines.append("For your security, refunds can only go to the original payment method used for the order - we "
                     "can't send them to another account, card or UPI ID. Please don't share account details in chat; our "
                     "Payments team will contact you through a verified process.")
    if g.has("human_request"):
        trig.append({"team": teams["human_request"], "priority": "medium", "reason": "customer asked for a human agent"})
    return trig, lines


# ------------------------------------------------------------------ memory
def merge_pending(session: Session, new: list[Intent], text: str, attachments: bool) -> tuple[list[Intent], list[str]]:
    """Attach follow-up answers ('NM-1101, the Sony one', 'yes', 'I already sent it') to the intent we asked about."""
    notes: list[str] = []
    if attachments:
        for i in new:
            i.evidence_mentioned = True
    if not session.pending:
        return new, notes
    generic = all(i.type in ("other", "greeting") for i in new)
    pending_types = {p["intent"]["type"] for p in session.pending}
    # a bare detail ("it's defective", "the Sony one") answers the question we asked; it isn't a new request
    if not generic and all(not i.order_id for i in new) and             all(i.type in ("other", "product_issue") or i.type in pending_types for i in new):
        generic = True
    info = new[0]
    merged: list[Intent] = []
    for p in session.pending:
        it = Intent(**p["intent"])
        miss, opts = p["missing"], p.get("options") or []
        if generic or miss in ("order", "item", "reason", "evidence", "address", "clarify"):
            if info.order_id and miss in ("order", "clarify"):
                it.order_id = info.order_id
            elif miss in ("order", "item") and opts:
                pick = _pick_option(text, opts, it.order_id)
                if pick and miss == "order":
                    it.order_id = pick
                elif pick and miss == "item":
                    it.product_hint = _item_name(it.order_id, pick) or it.product_hint
                elif info.product_hint:
                    it.product_hint = info.product_hint
            if miss == "reason" and info.reason:
                it.reason = info.reason
            if info.evidence_mentioned or attachments:
                it.evidence_mentioned = True
            if miss == "address" and generic:
                it.new_address = text.strip()
            it.amount_claimed = it.amount_claimed or info.amount_claimed
            it.reason = it.reason or info.reason
        if miss in ("confirm", "remedy"):
            low = text.lower()
            if miss == "remedy" and re.search(r"refund|paisa|money", low):
                it = Intent(**{**it.model_dump(), "type": "refund"})
            elif miss == "remedy" and re.search(r"replac|exchange|new one|badal", low):
                it = Intent(**{**it.model_dump(), "type": "replacement"})
            elif NO.search(text) and generic:
                notes.append("declined")
                continue
            elif not (YES.search(text) or not generic):
                continue
        merged.append(it)
        notes.append(f"Continued pending {it.type} (was waiting for {miss}).")
    if generic:
        return (merged, notes) if merged else (new, notes)
    # customer also said something new: keep new intents, enrich any of the same type
    for i in new:
        for m in merged:
            if m.type == i.type or (i.type in ("refund", "replacement", "return") and not i.order_id):
                for f in ("order_id", "reason", "product_hint", "amount_claimed"):
                    if getattr(i, f) is None and getattr(m, f) is not None:
                        setattr(i, f, getattr(m, f))
                i.evidence_mentioned |= m.evidence_mentioned
    return new, notes


def _pick_option(text: str, opts: list[str], order_id: str | None = None) -> str | None:
    """Pick one of the options we listed: by ID, ordinal ('the second one') or product words ('the Sony one')."""
    from app.data import get_store
    for i in extract_order_ids(text):
        if i in opts:
            return i
    low = text.lower()
    for w, idx in ORDINALS.items():
        if re.search(rf"{w}", low) and opts:
            return opts[idx] if -len(opts) <= idx < len(opts) else None
    store = get_store()
    words = [w for w in re.findall(r"[a-z0-9]{3,}", low) if w not in {"the", "one", "order", "this", "that", "wala", "vala"}]
    hits = []
    for o in opts:
        if o.startswith("ORD-"):
            items = store.items(o)
        else:
            items = [i for i in store.items(order_id or "") if i["order_item_id"] == o]
        hay = " ".join(f"{i['product_name']} {i['brand']} {i['category']}" for i in items).lower()
        if words and any(w in hay for w in words):
            hits.append(o)
    return hits[0] if len(hits) == 1 else None


def _item_name(order_id: str | None, order_item_id: str) -> str | None:
    from app.data import get_store
    if not order_id:
        return None
    for it in get_store().items(order_id):
        if it["order_item_id"] == order_item_id:
            return it["product_name"]
    return None


def recall_from_history(session: Session, intents: list[Intent], cid: str) -> tuple[list[Intent], list[str]]:
    """'I already sent it yesterday' in a fresh session: resolve 'it' from prior conversations / open tickets."""
    if not (len(intents) == 1 and intents[0].type == "other" and intents[0].evidence_mentioned and not intents[0].order_id):
        return intents, []
    prior = session.prior or {}
    for t in reversed(prior.get("open_tickets", [])):
        if t.get("order_id") and t["category"] in ("damaged_product", "return", "replacement", "refund", "wrong_product",
                                                  "missing_product", "warranty", "technical"):
            reason = _reason(t["issue_summary"]) or {"damaged_product": "damaged", "wrong_product": "wrong_item",
                                                      "missing_product": "missing_item"}.get(t["category"], "defective")
            return ([Intent(type="product_issue", order_id=t["order_id"], reason=reason, evidence_mentioned=True,
                            source="memory")],
                    [f"Resolved 'it' from open ticket {t['ticket_id']} ({t['issue_summary']}); evidence already provided - not re-asking."])
    for c in reversed(prior.get("conversations", [])):
        if c.get("order_id"):
            text = " ".join(m["message"] for m in c["messages"] if m["role"] == "customer")
            reason = _reason(text)
            if reason or agent_asked_for_photo(cid):
                return ([Intent(type="product_issue", order_id=c["order_id"], reason=reason or "defective",
                                evidence_mentioned=True, source="memory")],
                        [f"Resolved 'it' from prior conversation {c['conversation_id']} on {c['order_id']}; not re-asking for the photo."])
    return intents, []


def _tool_call(c: dict) -> ToolCall:
    """Trace entry in the API_CONTRACT shape: {name, params, ok, result_summary} (+ structured result)."""
    r = c["result"]
    ok = r.get("success", True) is not False and "error" not in r
    summary = ", ".join(f"{k}={v}" for k, v in r.items() if v not in (None, [], {}))[:240]
    return ToolCall(name=c["tool"], params=c["params"], ok=ok, result_summary=summary, result=r)


# -------------------------------------------------------------------- turn
def run_turn(req: ChatRequest) -> ChatResponse:
    t0 = time.perf_counter()
    now = now_ist(req.current_time)
    usage, tracer = Usage(), ToolTracer()
    session_id = req.session_id or f"sess-{uuid.uuid4().hex[:10]}"
    session = SESSIONS.get(session_id, req.customer_id)
    reasoning: list[str] = []
    g = scan(req.message)
    flags = sorted(g.flags)

    def respond(reply, decision, outcomes=(), pr: ParseResult | None = None, esc_id=None, refund=None, version=None,
                reply_source="template"):
        session.history.append({"role": "customer", "text": req.message})
        session.history.append({"role": "agent", "text": reply})
        if outcomes:
            parsed = to_jsonable(pr) if pr else []
            intents_out = [{"order_id": None, "reason": None,
                            **(parsed[o.index] if o.index < len(parsed) and parsed[o.index]["type"] == o.type else {"type": o.type}),
                            **o.view(), "explanation": next((r for r in reversed(o.reasons) if r), "")}
                           for o in outcomes]
        else:
            intents_out = [{"order_id": None, "reason": None, "decision": decision, **i} for i in (to_jsonable(pr) if pr else [])]
        return ChatResponse(
            reply=reply, decision=decision, intents=intents_out,
            tool_calls=[_tool_call(c) for c in tracer.calls], refund_amount=refund, escalate=decision == "ESCALATE",
            ticket_id=esc_id or next((c["result"].get("id") for c in reversed(tracer.actions) if c["result"].get("id")), None),
            reasoning=reasoning, policy_version=version, flags=flags, language=pr.language if pr else "en",
            session_id=session_id, parser=pr.parser if pr else "rules", reply_source=reply_source,
            tokens={"input": sum(c["input_tokens"] for c in usage.calls),
                    "output": sum(c["output_tokens"] for c in usage.calls), "llm_calls": len(usage.calls)},
            usage={"llm_calls": len(usage.calls), "total_tokens": usage.total_tokens, "calls": usage.calls},
            latency_ms=int((time.perf_counter() - t0) * 1000))

    # identity -------------------------------------------------------------
    if not req.customer_id:
        reasoning.append("No authenticated customer on the conversation; cannot verify ownership of any order.")
        return respond("Hi! To help with your orders I need to verify your account. Please log in, or share the email "
                       "address registered with NovaMart.", "ASK")
    cust = tracer("get_customer", customer_id=req.customer_id)
    if not cust["found"]:
        reasoning.append(f"Customer {req.customer_id} not found.")
        return respond("I couldn't find your account. Could you share the email address registered with NovaMart?", "ASK")
    customer = cust["customer"]

    # memory: prior conversations + open tickets, once per session ----------
    if session.prior is None:
        session.prior = tracer("get_conversations", customer_id=customer["customer_id"])
        if session.prior["open_tickets"]:
            reasoning.append("Open tickets on file: " + ", ".join(f"{t['ticket_id']} ({t['category']}, {t.get('order_id') or '-'})"
                                                                  for t in session.prior["open_tickets"][:5]) + ".")

    # guard ------------------------------------------------------------------
    if g.has("injection"):
        reasoning.append(f"Prompt-injection text ignored (treated as data): {g.removed[:2]}.")
    text_for_parse = g.clean_text
    pr = parse(text_for_parse, customer["customer_id"], session.history, usage) if text_for_parse else \
        ParseResult(language="en", intents=[], parser="rules")
    reasoning.append(f"Parsed {len(pr.intents)} intent(s) via {pr.parser}: "
                     + ", ".join(f"{i.type}{'(' + i.order_id + ')' if i.order_id else ''}" for i in pr.intents) + ".")
    intents, notes = merge_pending(session, list(pr.intents), req.message, bool(req.attachments))
    intents, recall = recall_from_history(session, intents, customer["customer_id"])
    reasoning += notes + recall
    if any(i.evidence_mentioned for i in intents):
        session.evidence = True
    if g.has("human_request") and not any(i.type == "human_agent" for i in intents):
        intents = [i for i in intents if i.type not in ("other",)]

    triggers, trig_lines = global_triggers(g, session)
    warning = None
    if g.has("abuse") and not session.warned_abuse and not g.has("threat"):
        session.warned_abuse = True
        warning = "I understand you're frustrated and I do want to help - please keep the conversation respectful."
        reasoning.append("Abusive language: one calm warning given (escalates if repeated).")

    # declined offer / nothing actionable -----------------------------------
    if "declined" in notes and not intents:
        session.pending = []
        return respond(template_reply(customer["first_name"], ["No problem."]), "ANSWER", pr=pr)
    if not intents and not triggers:
        session.pending = []
        msg = ("I can't change or bypass NovaMart's policies or share internal information, but I'm happy to help with "
               "your orders, returns, refunds or products. What can I do for you?")
        return respond(template_reply(customer["first_name"], [msg], closing=False), "ANSWER", pr=pr)

    # decide per intent --------------------------------------------------------
    ctx = Ctx(customer=customer, session=session, tracer=tracer, now=now, guard=g, dry_run=bool(triggers), intents=intents)
    for idx, it in enumerate(intents):
        out = dec.handle(it, idx, ctx)
        if ctx.dry_run and out.decision == "ASK" and out.type in ("other", "greeting"):
            out.message = ""  # the escalation is the answer; don't ask generic questions on top of it
        elif ctx.dry_run and out.decision == "ASK" and out.order_id and out.type in ("refund", "return", "replacement"):
            from app.data import get_store
            o = get_store().order(out.order_id)
            if not o or o["customer_id"] != customer["customer_id"]:
                ctx.outcomes.append(out)
                reasoning.append(f"#{idx} {it.type} -> {out.decision}: " + " ".join(r for r in out.reasons if r))
                continue
            out.decision = "ANSWER"
            out.message = (f"I've verified {out.order_id}: the order value is {inr(o['total_amount'])}"
                           + (f", so {inr(it.amount_claimed)} isn't possible" if it.amount_claimed and it.amount_claimed > o["total_amount"] else "")
                           + ". The specialist will review it.")
        if ctx.dry_run and out.decision == "ACT":  # global escalation in progress: inform, don't act
            out.decision = "ANSWER"
            amt = out.facts.get("max_refundable") or out.refund_amount
            out.message = (f"I've verified {out.order_id}" + (f": the maximum refundable amount is {inr(amt)}" if amt else "")
                           + (f", so {inr(it.amount_claimed)} isn't possible" if it.amount_claimed and amt and it.amount_claimed > amt else "")
                           + ". The specialist will take it from here.")
            out.reasons.append("Action withheld: case is being escalated.")
        ctx.outcomes.append(out)
        reasoning.append(f"#{idx} {it.type} -> {out.decision}: " + " ".join(r for r in out.reasons if r))

    # one escalation per turn, carrying full context -------------------------------
    escalations = triggers + [o.escalation for o in ctx.outcomes if o.escalation]
    esc_id = None
    if escalations:
        top = max(escalations, key=lambda e: SEVERITY.get(e["priority"], 0))
        order_ids = [o.order_id for o in ctx.outcomes if o.order_id]
        r = tracer("escalate_to_human", customer_id=customer["customer_id"], team=top["team"], priority=top["priority"],
                   order_id=order_ids[0] if order_ids else None, reason="; ".join(e["reason"] for e in escalations),
                   context={"message": req.message[:1000], "intents": [o.view() for o in ctx.outcomes],
                            "flags": flags, "facts": [o.reasons[-3:] for o in ctx.outcomes]})
        esc_id = r["id"]
        reasoning.append(f"Escalated to {top['team']} ({top['priority']}): {r['reason']}")

    decision = "ESCALATE" if escalations else dec.overall(ctx.outcomes)
    session.pending = [o.pending for o in ctx.outcomes if o.pending and o.decision == "ASK"]

    # reply ----------------------------------------------------------------------
    messages = list(trig_lines)
    if g.has("injection"):
        messages.append("I can't change or bypass NovaMart's policies, but I can help with your actual request.")
    messages += [o.message for o in ctx.outcomes if o.message]
    if esc_id:
        top = max(escalations, key=lambda e: SEVERITY.get(e["priority"], 0))
        sla = section("escalation")["sla"].get(top["priority"], "")
        messages.append(f"Your reference number is {esc_id}; our {top['team']} team will respond ({sla}).")
    draft = template_reply(customer["first_name"], messages, warning, closing=decision in ("ANSWER", "ACT"))
    reply, source = write_reply(draft, req.message, pr.language, usage)

    refunds = [o.refund_amount for o in ctx.outcomes if o.refund_amount is not None]
    versions = [o.policy_version for o in ctx.outcomes if o.policy_version]
    return respond(reply, decision, ctx.outcomes, pr, esc_id, refunds[0] if len(refunds) == 1 else (sum(refunds) or None),
                   versions[0] if versions else None, source)
