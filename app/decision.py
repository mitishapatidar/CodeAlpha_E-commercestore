"""Decision engine: per intent, choose ANSWER / ASK / ACT / ESCALATE from verified facts.

Priority (handbook p.5 + escalation policy):
  safety / self-harm / legal / threats / human request  -> ESCALATE
  injection                                             -> ignore it, continue the genuine request safely
  OTP contradiction / repeat claims / suspended / over threshold / fraud signals -> ESCALATE
  missing or ambiguous information                      -> ASK
  eligible and within authority                         -> ACT (write tool with verified params)
  informational                                         -> ANSWER
Each outcome carries a customer-facing `message` (deterministic) and `reasons` (audit trail).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app import policy_engine as pe
from app.data import as_date
from app.guard import GuardResult
from app.intent import Intent
from app.memory import Session, open_ticket_for, prior_evidence
from app.policy_store import get_policy, section
from app.tools import ToolTracer, earliest_request, order_age_hours, prior_actions
from app.verifier import (IN_TRANSIT, UNSHIPPED, Resolution, cancellations_recent, delivered_days_ago,
                          fraud_suspicion_ticket, repeat_claims, resolve_order)

PRIORITY = {"ESCALATE": 3, "ACT": 2, "ASK": 1, "ANSWER": 0}
DEFECT = {"defective", "damaged", "wrong_item", "missing_item"}
CLAIM_TICKET_CATS = {"refund", "return", "damaged_product", "missing_product", "wrong_product", "replacement"}


def inr(x: float) -> str:
    """Indian digit grouping: 1000000 -> ₹10,00,000."""
    n = int(round(float(x)))
    sign, n = ("-" if n < 0 else ""), abs(n)
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join(([head] if head else []) + groups) + "," + tail
    return f"{sign}₹{s}"


@dataclass
class Outcome:
    index: int
    type: str
    decision: str = "ANSWER"
    message: str = ""
    order_id: str | None = None
    reasons: list[str] = field(default_factory=list)
    refund_amount: float | None = None
    policy_version: str | None = None
    escalation: dict | None = None      # {"team", "priority", "reason"} - executed once per turn by the agent
    pending: dict | None = None         # what we're waiting for (stored in session)
    blocks_dependents: bool = False
    facts: dict = field(default_factory=dict)

    def view(self) -> dict:
        d = {"index": self.index, "type": self.type, "decision": self.decision, "order_id": self.order_id,
             "refund_amount": self.refund_amount, "policy_version": self.policy_version}
        if self.escalation:
            d["escalation_team"] = self.escalation["team"]
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class Ctx:
    customer: dict
    session: Session
    tracer: ToolTracer
    now: datetime
    guard: GuardResult
    dry_run: bool = False           # a global escalation is in progress: verify + inform, but take no actions
    intents: list = field(default_factory=list)
    outcomes: list[Outcome] = field(default_factory=list)

    @property
    def cid(self) -> str:
        return self.customer["customer_id"]

    def act(self, tool: str, **params) -> dict | None:
        if self.dry_run:
            return None
        return self.tracer(tool, **params)


# ====================================================================== helpers
def _ask_for_order(out: Outcome, res: Resolution, intent: Intent, ctx: Ctx, what: str) -> Outcome:
    out.decision = "ASK"
    out.reasons += res.reasons
    if res.status == "not_found":
        out.message = (f"I couldn't find {intent.order_id} in our records. Could you double-check the order ID? "
                       "You'll find it in your order confirmation email or under My Orders.")
    elif res.status == "not_owned":
        out.message = (f"I couldn't find {intent.order_id} on your account. Could you double-check the order ID? "
                       "For privacy I can only discuss orders placed from your own account.")
    elif res.status in ("ambiguous", "missing") and res.options:
        lines = "; ".join(f"{o['order_id']} ({', '.join(o['items'][:2])}, {o['status']} {o['date']})" for o in res.options)
        lead = "I see more than one order that could match" if res.status == "ambiguous" else "Your recent orders are"
        out.message = f"{lead}: {lines}. Which one would you like me to {what}?"
        out.facts["options"] = res.options
    elif res.status == "ambiguous_item":
        names = ", ".join(o["product_name"] for o in res.options)
        out.order_id = res.order["order_id"]
        out.message = f"Order {res.order['order_id']} has several items ({names}). Which item is this about?"
        out.facts["options"] = res.options
    elif res.status == "no_match":
        out.message = "I couldn't find a matching order for that product on your account. Could you share the order ID?"
    else:
        out.message = f"Could you share the order ID you'd like me to {what}?"
    out.pending = {"intent": intent.model_dump(), "missing": "item" if res.status == "ambiguous_item" else "order",
                   "options": [o.get("order_id") or o.get("order_item_id") for o in res.options]}
    return out


def _escalate(out: Outcome, team_key: str, reason: str, priority: str = "high", message: str = "") -> Outcome:
    team = section("escalation")["teams"].get(team_key, "Support Lead")
    out.decision = "ESCALATE"
    out.escalation = {"team": team, "priority": priority, "reason": reason}
    out.reasons.append(f"Escalation trigger: {reason} -> {team} ({priority}).")
    out.message = message or out.message
    return out


def _has_evidence(intent: Intent, ctx: Ctx, order_id: str) -> tuple[bool, str]:
    if intent.evidence_mentioned or ctx.session.evidence:
        return True, "Customer says photos/evidence were provided."
    pe_ = prior_evidence(ctx.cid, order_id)
    if pe_["found"]:
        return True, f"Evidence already shared in earlier conversation {pe_['conversation_id']} - not re-asking."
    return False, ""


def _soft_fraud_signals(intent: Intent, ctx: Ctx, order: dict, max_refund: float | None) -> list[str]:
    s = []
    if intent.amount_claimed and intent.amount_claimed > float(order["total_amount"]):
        s.append(f"requested {inr(intent.amount_claimed)} > order total {inr(order['total_amount'])}")
    if ctx.guard.has("injection"):
        s.append("prompt-injection attempt in the same message")
    if ctx.guard.has("authority_claim"):
        s.append("unverifiable authority claim ('manager approved')")
    rc = repeat_claims(ctx.cid, ctx.now)
    if rc["count"] == rc["min"] - 1:
        s.append(f"{rc['count']} recent claims in {rc['days']} days")
    if fraud_suspicion_ticket(ctx.cid, ctx.now):
        s.append("fraud-suspicion ticket on the account in the last 90 days")
    return s


def _refund_destination(order: dict) -> tuple[str, str]:
    method = order["payment_method"]
    timeline = section("payment")["refund_timelines"].get(method, "")
    if method == "cash_on_delivery":
        return "cod_wallet_or_verified_bank", ("Since this was a cash-on-delivery order, the refund can go to your "
                                              "NovaMart wallet (instant) or to a bank account verified by our Payments "
                                              "team - just tell me which you prefer.")
    return "original_payment_method", f"It will go back to your original payment method ({method.replace('_', ' ')}; {timeline})."


def _contradiction(intent: Intent, ctx: Ctx, order: dict, out: Outcome) -> Outcome | None:
    """Claims vs record and vs earlier statements in this session."""
    oid = order["order_id"]
    earlier = ctx.session.claims.get(oid, set())
    now_claims = set(intent.claims)
    if ("not_received" in earlier and "received_item" in now_claims) or ("received_item" in earlier and "not_received" in now_claims):
        return _escalate(out, "contradiction", "customer's account of events changed during the conversation",
                         message=(f"I've noted some conflicting details about {oid}. To make sure this is handled "
                                  "correctly, I'm passing it to a specialist who will review the full history."))
    if "received_item" in now_claims and order["delivery_status"] != "delivered":
        key = f"{oid}:not_delivered"
        if key in ctx.session.clarify_asked:
            return _escalate(out, "contradiction", "claim of receiving the item conflicts with the order record after clarification",
                             message=(f"Our records still show {oid} as {order['delivery_status'].replace('_', ' ')}, "
                                      "which doesn't match what you've described, so I'm asking a specialist to look into it."))
        ctx.session.clarify_asked.add(key)
        out.decision = "ASK"
        out.reasons.append("Claim conflicts with record (item reported received, order not delivered); clarifying first.")
        out.message = (f"Our records show {oid} hasn't been delivered yet (status: {order['delivery_status'].replace('_', ' ')}). "
                       "Could you confirm the order ID, or let me know if you received the item some other way?")
        out.pending = {"intent": intent.model_dump(), "missing": "clarify", "options": []}
        return out
    return None


# ===================================================================== handlers
def handle(intent: Intent, idx: int, ctx: Ctx) -> Outcome:
    out = Outcome(index=idx, type=intent.type, order_id=intent.order_id)
    # dependency: e.g. refund waits for an unresolved delivery claim
    if intent.depends_on is not None and intent.depends_on < len(ctx.outcomes):
        dep = ctx.outcomes[intent.depends_on]
        if dep.blocks_dependents:
            out.order_id = dep.order_id
            out.decision = "ANSWER"
            out.reasons.append(f"Held: depends on intent #{dep.index} ({dep.type}) which is still being resolved.")
            if intent.type == "refund":
                out.message = ("" if dep.decision == "ESCALATE" else
                               "I can't process the refund until the delivery question above is resolved; it will be decided as part of that review.")
            elif intent.type == "address_change":
                return h_address_change(intent, ctx, out, dep)
            else:
                out.message = f"Your {intent.type.replace('_', ' ')} request will be handled once the delivery issue is resolved."
            return out
        if not intent.order_id and dep.order_id:
            intent.order_id = dep.order_id
    fn = HANDLERS.get(intent.type, h_other)
    return fn(intent, ctx, out)


def h_greeting(intent, ctx, out):
    out.message = "How can I help you today? You can ask about an order, a return, a refund or a product."
    return out


def h_other(intent, ctx, out):
    out.decision = "ASK"
    out.message = ("Could you tell me a bit more about what you need help with? If it's about an order, "
                   "please share the order ID.")
    out.pending = {"intent": intent.model_dump(), "missing": "intent", "options": []}
    return out


def h_order_status(intent, ctx, out):
    res = resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
    if not res.ok:
        return _ask_for_order(out, res, intent, ctx, "check")
    o = res.order
    out.order_id, out.reasons = o["order_id"], res.reasons
    eta, dlv = as_date(o.get("estimated_delivery_date")), as_date(o.get("actual_delivery_date"))
    items = ", ".join(i["product_name"] for i in res.all_items[:3])
    status = o["order_status"]
    out.facts = {"order_status": status, "eta": str(eta) if eta else None, "delivered_on": str(dlv) if dlv else None,
                 "courier": o.get("courier"), "tracking_number": o.get("tracking_number")}
    track = f" via {o['courier']} (tracking {o['tracking_number']})" if o.get("tracking_number") else ""
    if o["delivery_status"] == "delivered":
        out.message = f"Order {o['order_id']} ({items}) was delivered on {dlv:%d %b %Y}."
    elif o["delivery_status"] == "lost":
        out.message = (f"Order {o['order_id']} ({items}) has been reported lost in transit by the courier. "
                       "You're entitled to a refund or replacement for a lost order - would you like me to start a refund?")
    elif status == "cancelled":
        out.message = f"Order {o['order_id']} ({items}) was cancelled. Refund status: {o['refund_status'].replace('_', ' ')}."
    elif status in IN_TRANSIT:
        d = pe.delay_info(o, ctx.now)
        out.message = f"Order {o['order_id']} ({items}) is {status.replace('_', ' ')}{track}. Expected delivery: {eta:%d %b %Y}."
        if d["days_late"] > 0:
            out.message += f" It's running {d['days_late']} day(s) late - sorry about that."
            out.reasons.append(f"{d['days_late']} days past ETA.")
            if d.get("suspected_lost"):
                return _suspected_lost(intent, ctx, out, o)
            if d.get("goodwill_credit"):
                out.message += f" You qualify for a goodwill wallet credit of {inr(d['goodwill_credit'])} for the delay."
    else:
        out.message = (f"Order {o['order_id']} ({items}) is {status.replace('_', ' ')} and hasn't shipped yet. "
                       f"Expected delivery: {eta:%d %b %Y}." if eta else f"Order {o['order_id']} is {status}.")
        if o["payment_status"] == "pending":
            out.message += " Payment is still pending confirmation from your bank."
    out.reasons.append(f"Live status from orders table: {status} / {o['delivery_status']}.")
    return out


def _suspected_lost(intent, ctx, out, o):
    existing = open_ticket_for(ctx.session.prior, o["order_id"], {"delivery", "order_tracking"})
    if existing:
        out.message += f" There's already an open logistics ticket ({existing['ticket_id']}) investigating this."
        out.reasons.append(f"Open ticket {existing['ticket_id']} already covers it - not duplicating.")
        out.blocks_dependents = True
        return out
    r = ctx.act("create_support_ticket", customer_id=ctx.cid, order_id=o["order_id"], category="delivery",
                summary=f"Suspected lost in transit: no delivery >{section('shipping')['suspected_lost_after_days']} days after ETA",
                priority="high", team="Logistics Desk")
    out.decision = "ACT"
    out.blocks_dependents = True
    out.message += (" Since it's more than a week past the expected date, I've opened a logistics investigation"
                    f"{' (ticket ' + r['id'] + ')' if r else ''}. The courier has up to 72 hours to respond; a refund or "
                    "replacement is decided after that.")
    out.reasons.append("More than 7 days past ETA -> suspected lost -> logistics ticket (no immediate refund).")
    return out


def h_delivery_issue(intent, ctx, out):
    res = resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
    if not res.ok:
        return _ask_for_order(out, res, intent, ctx, "look into")
    o = res.order
    out.order_id, out.reasons = o["order_id"], res.reasons
    out.blocks_dependents = True
    ctx.session.claims.setdefault(o["order_id"], set()).add("not_received")
    rc = repeat_claims(ctx.cid, ctx.now)
    if rc["hit"]:
        return _escalate(out, "repeat_claims", f"{rc['count']} non-delivery/refund/return claims in {rc['days']} days "
                         f"({', '.join(rc['tickets'][:5])})",
                         message=(f"I've passed your report about {o['order_id']} to our specialist team, who will review "
                                  "it together with your recent requests and get back to you."))
    if o["delivery_status"] == "delivered":
        dlv = as_date(o["actual_delivery_date"])
        if o.get("delivery_otp_verified"):
            return _escalate(out, "otp_dispute", f"customer reports non-delivery but {o['order_id']} was delivered with OTP "
                             f"verification on {dlv}",
                             message=(f"Our records show {o['order_id']} was delivered and OTP-verified on {dlv:%d %b %Y}. "
                                      "Since that conflicts with what you're seeing, I'm escalating it to our logistics "
                                      "investigations team. They'll check the courier's proof of delivery and contact you "
                                      "within 3 business days. I can't issue a refund before that review."))
        days = delivered_days_ago(o, ctx.now)
        hours = section("shipping")["no_otp_investigation_hours"]
        if days is not None and days * 24 <= hours:
            existing = open_ticket_for(ctx.session.prior, o["order_id"], {"delivery"})
            if existing:
                out.message = f"There's already an open delivery investigation for {o['order_id']} ({existing['ticket_id']})."
                return out
            r = ctx.act("create_support_ticket", customer_id=ctx.cid, order_id=o["order_id"], category="delivery",
                        summary="Delivered without OTP, customer reports not received (within 48h): courier investigation",
                        priority="high", team="Logistics Desk")
            out.decision = "ACT"
            out.message = (f"{o['order_id']} is marked delivered on {dlv:%d %b %Y} without OTP verification. I've opened a "
                           f"delivery investigation with the courier{' (ticket ' + r['id'] + ')' if r else ''}. If the parcel "
                           "isn't traced within 5 business days, we'll arrange a refund or replacement.")
            out.reasons.append("Delivered without OTP, reported within 48h -> courier investigation ticket.")
            return out
        return _escalate(out, "otp_dispute", f"non-delivery reported more than {hours}h after a non-OTP delivery",
                         message=(f"{o['order_id']} was marked delivered on {dlv:%d %b %Y}. Because it's been more than 48 "
                                  "hours, I've opened an investigation and a specialist will decide on a refund or "
                                  "replacement after checking with the courier."))
    if o["delivery_status"] == "lost":
        elig = pe.check_eligibility(o, res.items, "lost", ctx.customer, ctx.now)
        out.reasons += elig["reasons"]
        out.policy_version = elig["policy_version"]
        if elig["eligible"]:
            out.blocks_dependents = False
            out.facts["lost_refundable"] = True
            out.message = f"I'm sorry - the courier has confirmed {o['order_id']} was lost in transit."
            if not any(i.type == "refund" for i in ctx.intents):
                out.decision = "ASK"
                out.message += " You're entitled to a full refund (including shipping) or a replacement. Which would you prefer?"
                out.pending = {"intent": Intent(type="refund", order_id=o["order_id"], reason="lost").model_dump(),
                               "missing": "confirm", "options": []}
            return out
        return _suspected_lost(intent, ctx, out, o)
    if o["order_status"] == "cancelled":
        out.message = f"{o['order_id']} was cancelled, so it won't be delivered. Refund status: {o['refund_status']}."
        return out
    # not delivered yet -> it's a delay question
    out.blocks_dependents = True
    return h_order_status(intent, ctx, out)


def h_refund(intent, ctx, out):
    return _money_flow(intent, ctx, out, kind="refund")


def h_return(intent, ctx, out):
    return _money_flow(intent, ctx, out, kind="return")


def _money_flow(intent: Intent, ctx: Ctx, out: Outcome, kind: str) -> Outcome:
    res = resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
    if not res.ok:
        return _ask_for_order(out, res, intent, ctx, kind)
    o, items = res.order, res.items
    oid = o["order_id"]
    out.order_id, out.reasons = oid, list(res.reasons)
    out.policy_version = get_policy(o["order_date"], ctx.now)["version"]
    names = ", ".join(i["product_name"] for i in items)

    if ctx.customer.get("account_status") == "suspended":
        return _escalate(out, "suspended_account", "account is suspended",
                         message="Requests on this account need a review by our Trust & Safety team, so I've passed this on.")
    if o["payment_status"] in ("pending", "failed"):
        out.reasons.append(f"Payment status is {o['payment_status']} - nothing has been collected to refund.")
        out.message = (f"The payment for {oid} is {o['payment_status']}, so there's nothing to refund yet. "
                       f"If money left your account, an unconfirmed payment is auto-reversed within "
                       f"{section('payment')['auto_reversal_business_days']} business days.")
        return out
    already = [i for i in items if i["return_status"] != "none" or (i.get("refund_amount") or 0) > 0]
    if already and len(already) == len(items):
        i = already[0]
        out.message = (f"{i['product_name']} on {oid} already has a {kind} in progress or completed "
                       f"(status: {i['return_status'].replace('_', ' ')}"
                       f"{', refunded ' + inr(i['refund_amount']) if i.get('refund_amount') else ''}).")
        out.reasons.append("Duplicate request: item already returned/refunded.")
        return out
    if o["order_status"] == "cancelled":
        out.message = f"{oid} was cancelled; refund status: {o['refund_status']} (payment {o['payment_status']})."
        return out
    done = prior_actions(oid, {"refund", "return"}, [i["order_item_id"] for i in items])
    if done:
        d = done[-1]
        amt = d.get("amount") or d.get("refund_estimate")
        out.message = (f"A {d['type']} for {oid} is already in progress ({d['id']}{', ' + inr(amt) if amt else ''}), "
                       "so I won't create a duplicate.")
        out.reasons.append(f"Duplicate prevented: {d['id']} already created for this order.")
        return out

    reason = intent.reason
    if reason in (None, "late") and o["delivery_status"] == "lost":
        reason = "lost"
    if reason == "not_delivered":
        if o["delivery_status"] == "delivered":
            return h_delivery_issue(Intent(**{**intent.model_dump(), "type": "delivery_issue"}), ctx, out)
        reason = "lost" if o["delivery_status"] == "lost" else "not_delivered"
    if not reason:
        out.decision = "ASK"
        out.message = (f"I can help with a {kind} for {oid} ({names}). Could you tell me the reason - for example "
                       "damaged, defective, wrong item, missing item, or you've changed your mind?")
        out.pending = {"intent": {**intent.model_dump(), "order_id": oid}, "missing": "reason", "options": []}
        return out
    if reason == "late":
        d = pe.delay_info(o, ctx.now)
        out.message = ("A late delivery on its own isn't eligible for a refund while the parcel is moving"
                       + (f", but you qualify for a goodwill wallet credit of {inr(d['goodwill_credit'])}." if d.get("goodwill_credit") else "."))
        return out
    if reason == "physical_damage":
        out.message = ("I'm sorry about the damage. Accidental damage (drops, liquid) isn't covered by a refund or the "
                       "warranty, but I can help you book a paid repair at an authorised service centre.")
        out.reasons.append("Customer-caused physical/liquid damage: not refundable, not covered by warranty.")
        return out
    if reason in DEFECT | {"change_of_mind"}:
        ctx.session.claims.setdefault(oid, set()).add("received_item")
        c = _contradiction(intent, ctx, o, out)
        if c:
            return c

    # policy: window
    earlier = earliest_request(oid, CLAIM_TICKET_CATS | {"delivery"}) if reason != "change_of_mind" else earliest_request(oid, {"return", "refund"})
    item_ids = [i["order_item_id"] for i in items]
    elig = ctx.tracer("check_refund_eligibility", order_id=oid, customer_id=ctx.cid, reason=reason, item_ids=item_ids,
                      request_date=ctx.now.isoformat(), earlier_request=earlier.isoformat() if earlier else None)
    out.reasons += elig["reasons"]
    if not elig["eligible"]:
        return _not_eligible(intent, ctx, out, o, items, reason, elig)

    # evidence for defect claims
    pol = get_policy(o["order_date"], ctx.now)
    if reason in pol.get("evidence_required_reasons", []):
        ok, why = _has_evidence(intent, ctx, oid)
        if not ok:
            out.decision = "ASK"
            out.message = (f"I'm sorry about the problem with {names}. You're within the {elig['window_days']}-day window. "
                           "To process this, please share photos of the product, its label/serial number and the outer "
                           "packaging (a short video if it doesn't power on).")
            out.pending = {"intent": {**intent.model_dump(), "order_id": oid, "reason": reason}, "missing": "evidence", "options": []}
            out.reasons.append("Defect/damage claims need photo evidence before any action (return policy section 4).")
            return out
        out.reasons.append(why)

    # open ticket for the same issue -> reference it, don't duplicate
    existing = open_ticket_for(ctx.session.prior, oid, CLAIM_TICKET_CATS)
    if existing:
        out.message = (f"There's already an open request for {oid} ({existing['ticket_id']}: {existing['issue_summary']}). "
                       f"It's with our {existing['assigned_team']} team, so I won't open a duplicate.")
        out.reasons.append(f"Open ticket {existing['ticket_id']} covers this issue.")
        return out

    calc = ctx.tracer("calculate_refund", order_id=oid, customer_id=ctx.cid, reason=reason, item_ids=item_ids,
                      requested_amount=intent.amount_claimed, request_date=ctx.now.isoformat())
    out.reasons += calc["reasons"]
    amount = calc["refund_amount"]
    out.refund_amount = amount
    out.facts.update(max_refundable=calc["max_refundable"], restocking_fee=calc["restocking_fee"])

    th = pe.over_threshold(o, ctx.now)
    out.reasons.append(th["reason"])
    if th["over"]:
        return _escalate(out, "over_threshold", f"order total {inr(o['total_amount'])} above {th['policy_version']} "
                         f"approval threshold {inr(th['threshold'])}; computed refund {inr(amount)}",
                         message=(f"Your {kind} for {oid} is eligible (refund value {inr(amount)}), but orders above "
                                  f"{inr(th['threshold'])} need sign-off from our Refund Approver. I've sent it for approval."))
    signals = _soft_fraud_signals(intent, ctx, o, calc["max_refundable"])
    if len(signals) >= section("escalation")["soft_fraud_signals_to_escalate"]:
        return _escalate(out, "suspicious", "multiple risk signals: " + "; ".join(signals),
                         message=(f"I've reviewed {oid}. The maximum refundable amount is {inr(calc['max_refundable'])}"
                                  + (f", so {inr(intent.amount_claimed)} isn't possible" if calc["capped"] else "")
                                  + ". I've passed this to a specialist for review before anything is processed."))
    if signals:
        out.reasons.append("Risk signal noted (below escalation level): " + "; ".join(signals))

    dest, dest_txt = _refund_destination(o)
    cap_txt = (f" You asked for {inr(intent.amount_claimed)}, but the most I can refund for this is {inr(amount)} "
               "(the amount you paid for the item)." if calc["capped"] else "")
    fee_txt = (f" A restocking fee of {inr(calc['restocking_fee'])} applies to change-of-mind returns in this category."
               if calc["restocking_fee"] else "")
    needs_pickup = reason not in ("missing_item", "lost", "not_delivered")
    if kind == "return":
        resolution = "refund"
        r = ctx.act("create_return", order_id=oid, customer_id=ctx.cid, item_ids=item_ids, reason=reason,
                    resolution=resolution, refund_estimate=amount)
        out.decision = "ACT"
        out.message = (f"I've raised a return for {names} on {oid}{' (' + r['id'] + ')' if r else ''}. Pickup will be "
                       f"scheduled within 24-48 hours; once it passes the quality check, {inr(amount)} will be refunded "
                       f"within 3 business days.{fee_txt}{cap_txt} {dest_txt}")
    else:
        r = ctx.act("create_refund", order_id=oid, customer_id=ctx.cid, amount=amount, reason=reason, item_ids=item_ids,
                    destination=dest, return_pickup=needs_pickup)
        out.decision = "ACT"
        when = ("once the pickup passes our quality check (within 3 business days of QC)" if needs_pickup else "now")
        out.message = (f"I've verified {oid} ({names}) and initiated a refund of {inr(amount)}"
                       f"{' (' + r['id'] + ')' if r else ''}.{cap_txt}{fee_txt} "
                       + (f"We'll pick up the item within 24-48 hours, and the refund is released {when}. " if needs_pickup else "")
                       + dest_txt)
    out.reasons.append(f"ACT: {kind} within policy {out.policy_version} and approval threshold.")
    return out


def _not_eligible(intent, ctx, out, o, items, reason, elig):
    oid = o["order_id"]
    if elig.get("not_delivered"):
        out.blocks_dependents = True
        out.message = f"{oid} hasn't been delivered yet (status: {o['order_status'].replace('_', ' ')}), so a {intent.type} can't be started."
        if o["order_status"] in UNSHIPPED:
            out.message += " It hasn't shipped, so I can cancel it instead if you like."
        return out
    if elig.get("too_early"):
        out.message = (f"{oid} hasn't arrived yet. A not-delivered claim can be raised from {elig['window_start']} "
                       "(7 days after the expected date). I'll be happy to help then.")
        return out
    if elig.get("non_returnable"):
        out.message = (f"{', '.join(elig['non_returnable'])} can't be returned for a change of mind (non-returnable item). "
                       "If it's faulty, I can help with a defect claim instead.")
        return out
    w = pe.warranty_status(items[0], o, ctx.now)
    if reason in DEFECT and w.get("in_warranty"):
        out.message = (f"{oid} is outside the {elig.get('base_window_days')}-day {reason.replace('_', ' ')} refund window "
                       f"(delivered {elig.get('delivered_on')}), so a refund isn't possible. It's still under warranty until "
                       f"{w['warranty_end']}, so I can register a warranty repair claim - would you like that?")
        out.reasons.append(w["reason"])
        out.pending = {"intent": Intent(type="warranty", order_id=oid, reason=reason).model_dump(), "missing": "confirm", "options": []}
        return out
    if reason in DEFECT:
        out.message = (f"{oid} is outside the refund window and the warranty ended on {w.get('warranty_end')}. "
                       "I can help you book a paid repair at an authorised service centre.")
        return out
    extra = ""
    pol = get_policy(o["order_date"], ctx.now)
    if reason == "change_of_mind" and elig.get("day_n") is not None and elig["day_n"] <= pol["windows_days"]["defective"]:
        extra = f" If the item is faulty, it's still inside the {pol['windows_days']['defective']}-day defect window."
    out.message = (f"I'm sorry, {oid} was delivered on {elig.get('delivered_on')} and today is day {elig.get('day_n')}, "
                   f"outside the {elig.get('window_days')}-day {reason.replace('_', ' ')} window under our "
                   f"{elig['policy_version']} policy, so I can't process it.{extra}")
    return out


def h_replacement(intent, ctx, out):
    res = resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
    if not res.ok:
        return _ask_for_order(out, res, intent, ctx, "replace")
    o, items = res.order, res.items
    oid, names = o["order_id"], ", ".join(i["product_name"] for i in items)
    out.order_id, out.reasons = oid, res.reasons
    out.policy_version = get_policy(o["order_date"], ctx.now)["version"]
    reason = intent.reason
    if reason == "change_of_mind":
        out.message = "Replacements are only for defective, damaged or wrong items. For a change of mind I can start a return instead."
        return out
    if reason == "physical_damage":
        return _money_flow(intent, ctx, out, "refund")
    if reason not in DEFECT:
        out.decision = "ASK"
        out.message = f"Could you tell me what's wrong with {names} - is it defective, damaged on arrival, or the wrong item?"
        out.pending = {"intent": {**intent.model_dump(), "order_id": oid}, "missing": "reason", "options": []}
        return out
    ctx.session.claims.setdefault(oid, set()).add("received_item")
    c = _contradiction(intent, ctx, o, out)
    if c:
        return c
    elig = ctx.tracer("check_refund_eligibility", order_id=oid, customer_id=ctx.cid, reason=reason,
                      item_ids=[i["order_item_id"] for i in items], request_date=ctx.now.isoformat())
    out.reasons += elig["reasons"]
    if not elig["eligible"]:
        return _not_eligible(intent, ctx, out, o, items, reason, elig)
    ok, why = _has_evidence(intent, ctx, oid)
    if not ok:
        out.decision = "ASK"
        out.message = (f"I can help replace {names}. Please share photos of the product, its label/serial number and the "
                       "outer packaging so I can raise the replacement.")
        out.pending = {"intent": {**intent.model_dump(), "order_id": oid, "reason": reason}, "missing": "evidence", "options": []}
        return out
    out.reasons.append(why)
    prior_repl = [t for t in ctx.session.prior.get("recent_tickets", []) if t.get("order_id") == oid and t["category"] == "replacement"] if ctx.session.prior else []
    if prior_repl:
        return _escalate(out, "replacement_limit", f"order already had a replacement request ({prior_repl[0]['ticket_id']}); one replacement per item",
                         message=f"{oid} has already had a replacement, so I've asked our Returns & Warranty team to review this one.")
    item = items[0]
    if not item.get("replacement_available"):
        out.decision = "ASK"
        out.message = f"A replacement isn't available for {item['product_name']}, but I can process a refund instead. Shall I go ahead?"
        out.pending = {"intent": Intent(type="refund", order_id=oid, reason=reason, evidence_mentioned=True).model_dump(), "missing": "confirm", "options": []}
        return out
    if item.get("product_status") in ("out_of_stock", "discontinued"):
        out.decision = "ASK"
        out.message = f"{item['product_name']} is currently {item['product_status'].replace('_', ' ')}. Would you prefer a refund, or to wait for restock?"
        return out
    th = pe.over_threshold(o, ctx.now)
    out.reasons.append(th["reason"])
    if th["over"]:
        return _escalate(out, "over_threshold", f"replacement on order above {inr(th['threshold'])} needs human approval",
                         message=f"Your replacement for {oid} is eligible, but orders above {inr(th['threshold'])} need approval, so I've sent it to our approver.")
    r = ctx.act("create_return", order_id=oid, customer_id=ctx.cid, item_ids=[i["order_item_id"] for i in items],
                reason=reason, resolution="replacement")
    out.decision = "ACT"
    out.message = (f"I've raised a replacement for {names} on {oid}{' (' + r['id'] + ')' if r else ''}. The faulty unit will be "
                   "collected when the new one is delivered (pickup within 48 hours), and the replacement ships within 2 "
                   "business days of the quality check, free of charge.")
    return out


def h_product_issue(intent, ctx, out):
    if intent.reason == "physical_damage":
        out.message = ("I'm sorry to hear that. Accidental damage (drops, liquid) isn't covered by warranty or refunds, "
                       "but I can help you book a paid repair at an authorised service centre.")
        out.reasons.append("Customer-caused damage: warranty exclusion.")
        return out
    res = resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
    if not res.ok:
        return _ask_for_order(out, res, intent, ctx, "help with")
    o, items = res.order, res.items
    out.order_id, out.reasons = o["order_id"], res.reasons
    w = pe.warranty_status(items[0], o, ctx.now)
    out.reasons.append(w.get("reason", ""))
    out.policy_version = w.get("policy_version")
    if w.get("in_defect_window"):
        ok, why = _has_evidence(intent, ctx, o["order_id"])
        if not ok:
            return _ask_evidence(intent, ctx, out, o, items)
        out.reasons.append(why)
        out.decision = "ASK"
        repl = items[0].get("replacement_available")
        out.message = (f"Thanks - {items[0]['product_name']} on {o['order_id']} is within the {w['defect_window_days']}-day "
                       f"defect window. Would you like a {'replacement or a ' if repl else ''}refund?")
        out.pending = {"intent": {**intent.model_dump(), "order_id": o["order_id"], "evidence_mentioned": True},
                       "missing": "remedy", "options": ["replacement", "refund"] if repl else ["refund"]}
        return out
    return h_warranty(intent, ctx, out, res)


def _ask_evidence(intent, ctx, out, o, items):
    out.decision = "ASK"
    out.message = (f"I'm sorry to hear about the problem with {items[0]['product_name']}. Could you share a photo (or a short "
                   "video if it won't power on) of the product, its label/serial number and the packaging?")
    out.pending = {"intent": {**intent.model_dump(), "order_id": o["order_id"]}, "missing": "evidence", "options": []}
    return out


def h_warranty(intent, ctx, out, res: Resolution | None = None):
    res = res or resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
    if not res.ok:
        return _ask_for_order(out, res, intent, ctx, "check the warranty for")
    o, item = res.order, res.items[0]
    out.order_id = o["order_id"]
    out.reasons = list(dict.fromkeys(out.reasons + res.reasons))
    w = pe.warranty_status(item, o, ctx.now)
    out.reasons.append(w.get("reason", ""))
    if not w.get("started"):
        out.message = "The warranty starts on the delivery date; this order hasn't been delivered yet."
        return out
    if intent.reason == "physical_damage":
        out.message = "Physical or liquid damage isn't covered by the warranty, but I can help you book a paid repair."
        return out
    claim = intent.reason in DEFECT or intent.type in ("product_issue",) or "claim" in (intent.claims or [])
    if not claim and intent.type == "warranty" and not intent.reason:
        out.message = (f"{item['product_name']} has a {w['warranty_months']}-month warranty, valid until {w['warranty_end']}"
                       f" ({'active' if w['in_warranty'] else 'expired'}).")
        return out
    if w["in_defect_window"]:
        out.decision = "ASK"
        out.message = (f"{item['product_name']} is still within the {w['defect_window_days']}-day defect window, so you can get a "
                       "replacement or refund instead of a repair. Which would you prefer? Please also share photos of the issue.")
        out.pending = {"intent": Intent(type="replacement", order_id=o["order_id"], reason=intent.reason or "defective").model_dump(),
                       "missing": "evidence", "options": []}
        return out
    if w["in_warranty"]:
        r = ctx.act("create_support_ticket", customer_id=ctx.cid, order_id=o["order_id"], category="warranty",
                    summary=f"Warranty claim: {item['product_name']} ({intent.reason or 'defect'}), warranty until {w['warranty_end']}",
                    priority="medium", team="Returns & Warranty")
        out.decision = "ACT"
        out.message = (f"{item['product_name']} is under warranty until {w['warranty_end']}. I've registered a warranty claim"
                       f"{' (' + r['id'] + ')' if r else ''}. The service centre will diagnose it within 3 business days and "
                       "repair it within 15 business days. Since it's past the return window, the remedy is repair (or a "
                       "replacement if the centre finds it irreparable), not a refund.")
        return out
    out.message = (f"The warranty on {item['product_name']} ended on {w['warranty_end']}, so I can't offer a free repair, "
                   "replacement or refund. I can help you book a paid repair at an authorised service centre.")
    return out


def h_cancel(intent, ctx, out):
    res = resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
    if not res.ok:
        return _ask_for_order(out, res, intent, ctx, "cancel")
    o = res.order
    oid = o["order_id"]
    out.order_id, out.reasons = oid, res.reasons
    allowed = section("cancellation")["allowed_statuses"]
    status = o["order_status"]
    if status == "cancelled":
        out.message = f"{oid} is already cancelled. Refund status: {o['refund_status']}."
        return out
    if any(a.get("category") == "cancellation" for a in prior_actions(oid, {"ticket"})):
        out.message = f"{oid} has already been cancelled at your request."
        return out
    if status in IN_TRANSIT:
        out.message = (f"{oid} has already shipped, so it can't be cancelled. You can refuse the delivery at the door (it "
                       "comes back to us and is refunded) or return it after delivery under our return policy.")
        out.reasons.append("Cancellation not allowed after shipment (cancellation policy section 1).")
        return out
    if status not in allowed:
        out.message = f"{oid} has been delivered, so it can't be cancelled - but I can help you with a return."
        return out
    lim = section("cancellation")["abuse_limit"]
    n = cancellations_recent(ctx.cid, ctx.now)
    if n > lim["max_cancellations"]:
        return _escalate(out, "suspicious", f"{n} cancellations in {lim['days']} days (limit {lim['max_cancellations']})",
                         message="I've passed this cancellation to our team for a quick review.")
    r = ctx.act("create_support_ticket", customer_id=ctx.cid, order_id=oid, category="cancellation",
                summary="Cancel order before shipment (customer request)", priority="medium", team="Order Management")
    out.decision = "ACT"
    out.message = f"I've cancelled {oid}{' (ref ' + r['id'] + ')' if r else ''}."
    if o["payment_method"] != "cash_on_delivery" and o["payment_status"] == "paid":
        amt = float(o["total_amount"])
        rf = ctx.act("create_refund", order_id=oid, customer_id=ctx.cid, amount=amt, reason="cancellation",
                     destination="original_payment_method")
        out.refund_amount = amt
        out.message += (f" A full refund of {inr(amt)} including shipping{' (' + rf['id'] + ')' if rf else ''} goes back to "
                        f"your {o['payment_method'].replace('_', ' ')} ({section('payment')['refund_timelines'].get(o['payment_method'], '')}).")
    else:
        out.message += " It was cash on delivery, so there's nothing to refund."
    return out


def h_address_change(intent, ctx, out, dep: Outcome | None = None):
    if dep is None:
        res = resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
        if not res.ok:
            return _ask_for_order(out, res, intent, ctx, "update")
        o = res.order
    else:
        o = ctx.tracer("get_order", order_id=dep.order_id, customer_id=ctx.cid).get("order") if dep.order_id else None
        if not o:
            out.decision = "ASK"
            out.message = "Which order should the new address apply to?"
            return out
    oid = o["order_id"]
    out.order_id = oid
    if o["order_status"] not in section("shipping")["address_change_allowed_statuses"]:
        state = "lost in transit" if o["delivery_status"] == "lost" else o["order_status"].replace("_", " ")
        out.decision = "ASK"
        out.message = (f"{oid} is already {state}, so its delivery address can't be changed. Would you like me to save "
                       f"{intent.new_address or 'the new address'} to your address book for future orders?")
        out.reasons.append("Address changes are only possible before shipment (shipping policy section 6).")
        return out
    if not intent.new_address:
        out.decision = "ASK"
        out.message = f"Sure - what's the full new address with pincode for {oid}?"
        out.pending = {"intent": {**intent.model_dump(), "order_id": oid}, "missing": "address", "options": []}
        return out
    r = ctx.act("create_support_ticket", customer_id=ctx.cid, order_id=oid, category="account",
                summary=f"Address change before shipment to: {intent.new_address}", priority="medium", team="Order Management")
    out.decision = "ACT"
    out.message = (f"I've updated the delivery address for {oid} to {intent.new_address}{' (ref ' + r['id'] + ')' if r else ''}. "
                   "Address changes are allowed once per order.")
    return out


def h_payment_issue(intent, ctx, out):
    res = resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
    if not res.ok:
        return _ask_for_order(out, res, intent, ctx, "check the payment for")
    o = res.order
    oid = o["order_id"]
    out.order_id, out.reasons = oid, res.reasons
    pay = section("payment")
    age = order_age_hours(o, ctx.now)
    if intent.reason == "duplicate_charge":
        r = ctx.act("create_support_ticket", customer_id=ctx.cid, order_id=oid, category="payment",
                    summary="Customer reports double charge", priority="high", team="Refunds & Payments")
        out.decision = "ACT"
        out.message = (f"I've raised a payment ticket for the double charge on {oid}{' (' + r['id'] + ')' if r else ''}. "
                       "Once verified, the extra amount is refunded within 5-7 business days.")
        return out
    if o["payment_status"] == "pending":
        if age < pay["pending_wait_hours"]:
            out.message = (f"The payment for {oid} is still being confirmed by your bank (placed {age:.0f} hours ago). Banks can "
                           f"take up to {pay['pending_wait_hours']} hours; please wait a little - no refund is needed yet.")
            return out
        r = ctx.act("create_support_ticket", customer_id=ctx.cid, order_id=oid, category="payment",
                    summary=f"Payment pending > {pay['pending_wait_hours']}h", priority="high", team="Refunds & Payments")
        out.decision = "ACT"
        out.message = (f"The payment for {oid} has been pending for more than {pay['pending_wait_hours']} hours, so I've raised "
                       f"a payment ticket{' (' + r['id'] + ')' if r else ''}. Unconfirmed prepaid payments are auto-reversed "
                       f"within {pay['auto_reversal_business_days']} business days.")
        return out
    if o["payment_status"] == "failed":
        out.message = (f"The payment for {oid} failed and the order was auto-cancelled. Any amount debited is automatically "
                       f"reversed within {pay['auto_reversal_business_days']} business days.")
        return out
    out.message = f"The payment for {oid} shows as {o['payment_status']} ({o['payment_method'].replace('_', ' ')})."
    return out


def h_refund_status(intent, ctx, out):
    res = resolve_order(intent, ctx.cid, ctx.tracer, ctx.now)
    if not res.ok:
        return _ask_for_order(out, res, intent, ctx, "check the refund for")
    o = res.order
    out.order_id, out.reasons = o["order_id"], res.reasons
    refunded = sum(float(i.get("refund_amount") or 0) for i in res.all_items)
    timeline = section("payment")["refund_timelines"].get(o["payment_method"], "")
    out.message = (f"Refund status for {o['order_id']}: {o['refund_status'].replace('_', ' ')}"
                   f"{' (' + inr(refunded) + ')' if refunded else ''}. Refunds to {o['payment_method'].replace('_', ' ')} "
                   f"take {timeline} to appear after release.")
    return out


def h_product_info(intent, ctx, out):
    hint = intent.product_hint or ""
    r = ctx.tracer("get_product", query=hint) if hint else {"found": False}
    if not r.get("found"):
        from app.data import get_store
        words = [w for w in hint.lower().split() if len(w) > 2]
        hits = [p for p in get_store().products.values() if words and all(w in p["product_name"].lower() for w in words)]
        if len(hits) == 1:
            r = ctx.tracer("get_product", product_id=hits[0]["product_id"])
    if not r.get("found"):
        out.decision = "ASK"
        out.message = "Which product would you like to know about? The full product name helps me find the right specs."
        return out
    p, specs = r["product"], r["specs"]
    spec_txt = "; ".join(f"{k}: {v}" for k, v in list(specs.items())[:6])
    out.message = (f"{p['product_name']} ({p['brand']}) is priced at {inr(p['price'])} (MRP {inr(p['mrp'])}), "
                   f"status: {p['status'].replace('_', ' ')}. {spec_txt}. Warranty: {p['warranty_months']} months; "
                   f"{'returnable' if p['returnable'] else 'not returnable'} for change of mind.")
    return out


def h_complaint(intent, ctx, out):
    r = ctx.act("create_support_ticket", customer_id=ctx.cid, order_id=intent.order_id, category="complaint",
                summary="Customer complaint (service/experience)", priority="medium", team="Customer Experience")
    out.decision = "ACT"
    out.message = (f"I'm sorry about your experience. I've logged your feedback with our Customer Experience team"
                   f"{' (' + r['id'] + ')' if r else ''}. Is there a specific order I can help with right now?")
    return out


def h_human(intent, ctx, out):
    return _escalate(out, "human_request", "customer asked for a human agent", priority="medium",
                     message="Of course - I'm connecting you with a member of our support team.")


HANDLERS = {
    "greeting": h_greeting, "other": h_other, "order_status": h_order_status, "delivery_issue": h_delivery_issue,
    "refund": h_refund, "return": h_return, "replacement": h_replacement, "product_issue": h_product_issue,
    "warranty": h_warranty, "cancel": h_cancel, "address_change": h_address_change, "payment_issue": h_payment_issue,
    "refund_status": h_refund_status, "product_info": h_product_info, "complaint": h_complaint, "human_agent": h_human,
}


def overall(outcomes: list[Outcome]) -> str:
    return max((o.decision for o in outcomes), key=lambda d: PRIORITY[d], default="ANSWER")
