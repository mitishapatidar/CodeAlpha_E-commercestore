"""Deterministic policy maths. No LLM, no I/O besides the policy store.

Every function returns plain dicts with a `reasons` list so the decision can be
audited line by line.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from app.config import IST
from app.data import as_date
from app.policy_store import get_policy, gst_rate, section

DEFECT_REASONS = {"defective", "damaged", "wrong_item", "missing_item"}


def day_n(delivery: date, request: date) -> int:
    """Calendar days since delivery; delivery day is day 0."""
    return (request - delivery).days


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def window_for(policy: dict, reason: str, loyalty_tier: str | None) -> dict:
    base = policy["windows_days"].get(reason)
    ext = 0
    if base is not None and reason in policy.get("loyalty_extension_reasons", []):
        ext = int(policy.get("loyalty_extension_days", {}).get((loyalty_tier or "").lower(), 0))
    return {"base_days": base, "loyalty_extension_days": ext, "total_days": None if base is None else base + ext}


def check_eligibility(order: dict, items: list[dict], reason: str, customer: dict | None,
                      now: datetime, earlier_request: datetime | None = None) -> dict:
    """Is a refund/return for `reason` allowed under the order's policy version?"""
    policy = get_policy(order["order_date"], now)
    reasons: list[str] = [f"Policy {policy['version']} applies (order placed {order['order_date']:%Y-%m-%d}; "
                          f"version chosen by placement date)."]
    out = {"policy_version": policy["version"], "reason": reason, "eligible": False,
           "approval_threshold": policy["approval_threshold"], "reasons": reasons}

    # Lost / not delivered claims use the ETA-based window
    if reason in ("not_delivered", "lost"):
        eta = as_date(order.get("estimated_delivery_date"))
        if order.get("delivery_status") == "delivered":
            reasons.append("Order is marked delivered; a not-delivered refund window does not apply.")
            return out
        if not eta:
            reasons.append("No estimated delivery date on record.")
            return out
        win = policy["not_delivered_claim"]
        start, end = eta + timedelta(days=win["from_eta_plus_days"]), eta + timedelta(days=win["until_eta_plus_days"])
        today = now.astimezone(IST).date()
        out.update(window_start=str(start), window_end=str(end))
        if today < start:
            reasons.append(f"Not-delivered claims open on {start} (ETA {eta} + {win['from_eta_plus_days']} days).")
            out["too_early"] = True
        elif today > end:
            reasons.append(f"Not-delivered claim window closed on {end}.")
        else:
            out["eligible"] = True
            reasons.append(f"Inside not-delivered claim window ({start} to {end}).")
        return out

    delivered = as_date(order.get("actual_delivery_date"))
    if not delivered or order.get("delivery_status") != "delivered":
        reasons.append("Order has not been delivered yet, so return/refund windows have not started.")
        out["not_delivered"] = True
        return out

    win = window_for(policy, reason, customer.get("loyalty_tier") if customer else None)
    if win["total_days"] is None:
        reasons.append(f"No refund window is defined for reason '{reason}'.")
        return out

    request_dt = now
    if earlier_request and earlier_request < now:
        n_early = day_n(delivered, earlier_request.astimezone(IST).date())
        if 0 <= n_early <= win["total_days"]:
            request_dt = earlier_request
            reasons.append(f"Customer first raised this on {earlier_request:%Y-%m-%d} (day {n_early}); "
                           "eligibility judged on that date (request-raised-in-time exception).")
    n = day_n(delivered, request_dt.astimezone(IST).date())
    out.update(delivered_on=str(delivered), day_n=n, window_days=win["total_days"],
               base_window_days=win["base_days"], loyalty_extension_days=win["loyalty_extension_days"],
               last_eligible_date=str(delivered + timedelta(days=win["total_days"])))
    ext_txt = f" + {win['loyalty_extension_days']} loyalty days" if win["loyalty_extension_days"] else ""
    if n <= win["total_days"]:
        out["eligible"] = True
        reasons.append(f"Delivered {delivered}; request on day {n} is within the {win['base_days']}-day "
                       f"{reason.replace('_', ' ')} window{ext_txt}.")
    else:
        reasons.append(f"Delivered {delivered}; request on day {n} is outside the {win['base_days']}-day "
                       f"{reason.replace('_', ' ')} window{ext_txt} (last day {out['last_eligible_date']}).")
        if reason == "change_of_mind":
            defect = policy["windows_days"].get("defective")
            if defect is not None and n <= defect:
                reasons.append(f"Still inside the {defect}-day defect window if the item is faulty.")

    if reason == "change_of_mind":
        non_returnable = [i["product_name"] for i in items if not i.get("returnable")]
        if non_returnable:
            out["eligible"] = False
            out["non_returnable"] = non_returnable
            reasons.append(f"Not returnable for change of mind: {', '.join(non_returnable)}.")
    return out


def calculate_refund(order: dict, items: list[dict], reason: str, requested_amount: float | None = None,
                     whole_order: bool = False, now: datetime | None = None) -> dict:
    """refund = min(requested, item value incl. GST - restocking [+ shipping]), capped at what is still refundable."""
    policy = get_policy(order["order_date"], now)
    gst = gst_rate()
    fee_rule = policy.get("restocking_fee", {})
    lines, reasons = [], []
    item_total = restocking_total = 0.0
    for it in items:
        paid = round(float(it["final_price"]) * (1 + gst), 2)
        fee = 0.0
        if (reason in fee_rule.get("reasons", []) and it.get("category") in fee_rule.get("categories", [])
                and fee_rule.get("percent")):
            fee = min(round(paid * fee_rule["percent"] / 100, 2), float(fee_rule.get("cap") or 1e12))
            reasons.append(f"Restocking fee {fee_rule['percent']}% (cap INR {fee_rule['cap']}) on "
                           f"{it['product_name']} ({it['category']}, change of mind): INR {fee:,.0f}.")
        item_total += paid
        restocking_total += fee
        lines.append({"order_item_id": it["order_item_id"], "product_name": it["product_name"],
                      "paid_incl_gst": paid, "restocking_fee": fee, "refundable": round(paid - fee, 2)})

    shipping = 0.0
    if whole_order and reason in policy.get("shipping_refund_reasons_full_order", []):
        shipping = float(order.get("shipping_fee") or 0)
        if shipping:
            reasons.append(f"Shipping fee INR {shipping:,.0f} refunded (whole order, reason '{reason}').")

    already = sum(float(i.get("refund_amount") or 0) for i in items)
    order_total = float(order["total_amount"])
    max_refund = round(min(item_total - restocking_total + shipping, order_total) - already, 2)
    max_refund = max(max_refund, 0.0)
    if already:
        reasons.append(f"INR {already:,.0f} already refunded on these items.")
    reasons.insert(0, f"Item value incl. {int(gst * 100)}% GST: INR {item_total:,.0f}; "
                      f"order total INR {order_total:,.0f}; maximum refundable INR {max_refund:,.0f}.")

    refund = max_refund
    capped = False
    if requested_amount is not None and requested_amount > 0:
        if requested_amount > max_refund:
            capped = True
            reasons.append(f"Requested INR {requested_amount:,.0f} exceeds the maximum refundable "
                           f"INR {max_refund:,.0f}; capped (compensation above the paid amount is not payable).")
        refund = min(requested_amount, max_refund)
    return {"policy_version": policy["version"], "lines": lines, "item_value": round(item_total, 2),
            "restocking_fee": round(restocking_total, 2), "shipping_refund": shipping,
            "max_refundable": max_refund, "requested_amount": requested_amount,
            "refund_amount": round(refund, 2), "capped": capped, "reasons": reasons}


def over_threshold(order: dict, now: datetime | None = None) -> dict:
    policy = get_policy(order["order_date"], now)
    t = policy["approval_threshold"]
    over = float(order["total_amount"]) > t
    return {"over": over, "threshold": t, "order_total": float(order["total_amount"]),
            "policy_version": policy["version"],
            "reason": (f"Order total INR {order['total_amount']:,.0f} {'exceeds' if over else 'is within'} the "
                       f"{policy['version']} approval threshold of INR {t:,.0f} (judged on order total).")}


def warranty_status(item: dict, order: dict, now: datetime) -> dict:
    delivered = as_date(order.get("actual_delivery_date"))
    today = now.astimezone(IST).date()
    if not delivered:
        return {"started": False, "reason": "Warranty starts on delivery; order not delivered yet."}
    months = int(item.get("warranty_months") or 0)
    end = add_months(delivered, months)
    policy = get_policy(order["order_date"], now)
    defect_days = policy["windows_days"].get("defective", 0)
    n = day_n(delivered, today)
    return {"started": True, "warranty_months": months, "warranty_end": str(end), "in_warranty": today <= end,
            "in_defect_window": n <= defect_days, "defect_window_days": defect_days, "day_n": n,
            "policy_version": policy["version"],
            "reason": (f"{item.get('product_name')}: {months}-month warranty from {delivered} to {end}; "
                       f"today is day {n} ({'inside' if n <= defect_days else 'outside'} the {defect_days}-day "
                       f"defect window, warranty {'active' if today <= end else 'expired'}).")}


def delay_info(order: dict, now: datetime) -> dict:
    ship = section("shipping")
    eta = as_date(order.get("estimated_delivery_date"))
    today = now.astimezone(IST).date()
    if not eta or order.get("delivery_status") == "delivered":
        return {"days_late": 0}
    late = (today - eta).days
    g = ship["delay_goodwill"]
    credit = 0
    if late > g["after_days"]:
        credit = min((late // g["credit_per_full_days"]) * g["credit_amount"], g["max_credit"])
    return {"days_late": max(late, 0), "goodwill_credit": credit,
            "suspected_lost": late > ship["suspected_lost_after_days"]}
