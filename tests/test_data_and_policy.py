"""Step 2: data loader + policy store."""
import json
from datetime import datetime

from app.config import IST
from app.data import get_store
from app.policy_store import get_policy, load_policies


def test_dataset_loads_with_expected_counts():
    s = get_store().stats()
    assert s["customers"] == 1500 and s["orders"] == 8000 and s["order_items"] == 12444
    assert s["products"] == 300 and s["support_tickets"] == 2500 and s["conversations"] == 1500
    assert s["product_specs"] == 300


def test_dates_are_typed_ist():
    o = next(iter(get_store().orders.values()))
    assert o["order_date"].tzinfo is not None
    assert o["order_date"].utcoffset().total_seconds() == 5.5 * 3600


def test_indexes_link_customer_order_items():
    store = get_store()
    cid, oids = next(iter(store.orders_by_customer.items()))
    assert all(store.order(o)["customer_id"] == cid for o in oids)
    assert store.items(oids[0]) and store.items(oids[0])[0]["product_name"]


def test_version_boundary_v1_last_minute():
    p = get_policy(datetime(2026, 5, 31, 23, 59, tzinfo=IST))
    assert p["version"] == "v1"
    assert p["windows_days"]["change_of_mind"] == 10 and p["approval_threshold"] == 100000


def test_version_boundary_v2_first_minute():
    p = get_policy(datetime(2026, 6, 1, 0, 0, tzinfo=IST))
    assert p["version"] == "v2"
    assert p["windows_days"]["change_of_mind"] == 7 and p["approval_threshold"] == 75000
    assert p["restocking_fee"]["percent"] == 5 and p["restocking_fee"]["cap"] == 2500


def test_policy_mutation_is_data_only(tmp_path):
    """Adding a v3 to policies.json changes behaviour without code changes."""
    src = load_policies()
    data = json.loads(json.dumps({k: v for k, v in src.items()}, default=str))
    for v in data["refund_policies"]:
        v.pop("_from", None), v.pop("_to", None)
    v3 = dict(data["refund_policies"][-1], version="v3", applies_from="2026-10-01T00:00:00+05:30")
    v3["windows_days"] = dict(v3["windows_days"], change_of_mind=3)
    data["refund_policies"][-1]["applies_to"] = "2026-09-30T23:59:59+05:30"
    data["refund_policies"].append(v3)
    f = tmp_path / "policies.json"
    f.write_text(json.dumps(data))
    assert get_policy(datetime(2026, 10, 2, tzinfo=IST), path=f)["windows_days"]["change_of_mind"] == 3
    assert get_policy(datetime(2026, 9, 2, tzinfo=IST), path=f)["version"] == "v2"
