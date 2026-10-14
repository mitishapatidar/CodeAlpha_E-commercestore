"""A message that names an order but not the problem gets an answer about that order, and the follow-up keeps it."""
from fastapi.testclient import TestClient

from app.main import app


def test_named_order_then_problem_keeps_order_context():
    c = TestClient(app)
    first = c.post("/chat", json={"customer_id": "CUST-00001", "session_id": "ctx-1",
                                  "message": "I have a problem with my Amazon Echo Dot (5th Gen) (Forest Green) from order ORD-004897"}).json()
    assert first["decision"] == "ASK"
    assert "ORD-004897" in first["reply"] and "Amazon Echo Dot (5th Gen) (Forest Green)" in first["reply"]
    second = c.post("/chat", json={"customer_id": "CUST-00001", "session_id": "ctx-1", "message": "it arrived damaged"}).json()
    assert second["decision"] != "ASK"
    assert "Amazon Echo Dot (5th Gen) (Forest Green)" in second["reply"]


def test_someone_elses_order_is_not_described():
    c = TestClient(app)
    r = c.post("/chat", json={"customer_id": "CUST-00001", "session_id": "ctx-2", "message": "help with ORD-000001"}).json()
    assert r["decision"] == "ASK" and "couldn't find" in r["reply"]


def test_storefront_order_is_saved_and_tracked_by_the_agent():
    c = TestClient(app)
    ship = {"name": "Ravi Ali", "phone": "9876543210", "address": "12 MG Road", "city": "Mumbai", "state": "Maharashtra",
            "pincode": "400001"}
    r = c.post("/orders", json={"customer_id": "CUST-00001", "items": [{"product_id": "PROD-00001", "quantity": 2}],
                                "shipping": ship, "payment_method": "UPI", "payment_ref": "ravi@okaxis"}).json()
    oid = r["order_id"]
    assert r["payment_status"] == "paid" and r["total_amount"] > 0
    assert c.get("/customers/CUST-00001/orders").json()[0]["order_id"] == oid
    reply = c.post("/chat", json={"customer_id": "CUST-00001", "session_id": "new-order", "message": f"Where is my order {oid}?"}).json()
    assert oid in reply["reply"]
    bad = c.post("/orders", json={"customer_id": "CUST-00001", "items": [], "shipping": ship, "payment_method": "UPI"})
    assert bad.status_code == 422
