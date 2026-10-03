"""Step 3: the 10 tools + policy engine maths, on real rows."""
import json
from datetime import datetime, timedelta

from app import policy_engine as pe
from app import tools
from app.config import ACTIONS_LOG, IST
from app.data import get_store
from tests.finders import NOW, clean_items, delivered, find_order


def test_get_customer_by_id_and_email():
    c = next(iter(get_store().customers.values()))
    assert tools.get_customer(customer_id=c["customer_id"])["customer"]["email"] == c["email"]
    assert tools.get_customer(email=c["email"].upper())["customer"]["customer_id"] == c["customer_id"]
    assert tools.get_customer(customer_id="CUST-99999")["found"] is False


def test_get_order_enforces_ownership():
    o, _, _ = find_order(lambda o, i, c: True)
    assert tools.get_order(o["order_id"], o["customer_id"])["owned"] is True
    other = tools.get_order(o["order_id"], "CUST-00000")
    assert other == {"found": True, "owned": False, "order_id": o["order_id"]}
    assert tools.get_order("ORD-999999", o["customer_id"])["found"] is False


def test_get_product_has_specs_and_warranty():
    p = tools.get_product(product_id="PROD-00135")
    assert p["found"] and p["specs"] and p["product"]["warranty_months"]


def test_get_conversations_returns_history_and_open_tickets():
    store = get_store()
    cid = next(c for c, ts in store.tickets_by_customer.items() if any(t["status"] == "open" for t in ts))
    r = tools.get_conversations(cid)
    assert r["open_tickets"]


def test_window_day0_and_edge():
    d = datetime(2026, 7, 6).date()
    assert pe.day_n(d, d) == 0
    assert pe.day_n(d, datetime(2026, 7, 13).date()) == 7


def test_eligibility_v2_change_of_mind_edge():
    """v2 worked example: delivered 07-06, request day 8 -> not eligible (7 days); day 7 -> eligible."""
    o, items, c = find_order(lambda o, i, c: o["order_date"] >= datetime(2026, 6, 1, tzinfo=IST) and delivered(o)
                             and all(x["returnable"] for x in i) and c["loyalty_tier"] in ("bronze", "silver"))
    dlv = datetime.combine(o["actual_delivery_date"], datetime.min.time(), IST)
    day7 = pe.check_eligibility(o, items, "change_of_mind", c, dlv + timedelta(days=7, hours=10))
    day8 = pe.check_eligibility(o, items, "change_of_mind", c, dlv + timedelta(days=8, hours=10))
    assert day7["eligible"] and day7["day_n"] == 7
    assert not day8["eligible"] and day8["day_n"] == 8


def test_loyalty_extension_platinum():
    o, items, c = find_order(lambda o, i, c: o["order_date"] >= datetime(2026, 6, 1, tzinfo=IST) and delivered(o)
                             and all(x["returnable"] for x in i) and c["loyalty_tier"] == "platinum")
    dlv = datetime.combine(o["actual_delivery_date"], datetime.min.time(), IST)
    r = pe.check_eligibility(o, items, "change_of_mind", c, dlv + timedelta(days=10, hours=9))
    assert r["eligible"] and r["window_days"] == 10 and r["loyalty_extension_days"] == 3


def test_refund_cap_and_restocking_v2_laptop():
    o, items, _ = find_order(lambda o, i, c: o["order_date"] >= datetime(2026, 6, 1, tzinfo=IST) and len(i) == 1
                             and i[0]["category"] == "Laptops" and clean_items(i))
    r = pe.calculate_refund(o, items, "change_of_mind", requested_amount=10_000_000, whole_order=True, now=NOW())
    paid = round(items[0]["final_price"] * 1.18, 2)
    fee = min(round(paid * 0.05, 2), 2500)
    assert r["restocking_fee"] == fee
    assert r["refund_amount"] == round(min(paid - fee, o["total_amount"]), 2)
    assert r["capped"] is True
    # no restocking fee for a defect
    assert pe.calculate_refund(o, items, "defective", whole_order=True, now=NOW())["restocking_fee"] == 0


def test_refund_never_exceeds_order_total():
    o, items, _ = find_order(lambda o, i, c: clean_items(i) and o["shipping_fee"] > 0 and len(i) == 1)
    r = pe.calculate_refund(o, items, "damaged", requested_amount=None, whole_order=True, now=NOW())
    assert r["refund_amount"] <= o["total_amount"]


def test_threshold_judged_on_order_total():
    o, _, _ = find_order(lambda o, i, c: o["order_date"] >= datetime(2026, 6, 1, tzinfo=IST)
                         and 75000 < o["total_amount"] <= 100000)
    assert pe.over_threshold(o)["over"] is True
    o1, _, _ = find_order(lambda o, i, c: o["order_date"] < datetime(2026, 6, 1, tzinfo=IST)
                          and 75000 < o["total_amount"] <= 100000)
    assert pe.over_threshold(o1)["over"] is False


def test_write_tools_log_and_never_overpay():
    o, items, _ = find_order(lambda o, i, c: delivered(o))
    r = tools.create_refund(o["order_id"], o["customer_id"], 1.0, "test")
    assert r["success"] and r["id"].startswith("RFD-")
    last = json.loads(ACTIONS_LOG.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert last["id"] == r["id"]
    assert tools.create_refund(o["order_id"], o["customer_id"], o["total_amount"] + 1, "x")["success"] is False
    assert tools.create_refund(o["order_id"], "CUST-00000", 1.0, "x")["success"] is False
    assert tools.escalate_to_human(o["customer_id"], "test", "Support Lead")["id"].startswith("ESC-")
    assert tools.create_support_ticket(o["customer_id"], "delivery", "t")["id"].startswith("TCK-")
    assert tools.create_return(o["order_id"], o["customer_id"], [items[0]["order_item_id"]], "t")["id"].startswith("RET-")


def test_tracer_records_calls_and_dedupes_reads():
    o, _, _ = find_order(lambda o, i, c: True)
    t = tools.ToolTracer()
    t("get_order", order_id=o["order_id"], customer_id=o["customer_id"])
    t("get_order", order_id=o["order_id"], customer_id=o["customer_id"])
    assert len(t.calls) == 1 and "delivery_otp_verified" not in json.dumps(t.calls)


def test_tool_specs_cover_all_tools():
    assert {s["name"] for s in tools.TOOL_SPECS} == set(tools.TOOLS) and len(tools.TOOLS) == 10
