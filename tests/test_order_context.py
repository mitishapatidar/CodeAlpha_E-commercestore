"""A message that names an order but not the problem gets an answer about that order, and the follow-up keeps it."""
from fastapi.testclient import TestClient

from app.main import app


def test_named_order_then_problem_keeps_order_context():
    c = TestClient(app)
    first = c.post("/chat", json={"customer_id": "CUST-00001", "session_id": "ctx-1",
                                  "message": "I have a problem with my Auralix Wave Core 500 from order ORD-004897"}).json()
    assert first["decision"] == "ASK"
    assert "ORD-004897" in first["reply"] and "Auralix Wave Core 500" in first["reply"]
    second = c.post("/chat", json={"customer_id": "CUST-00001", "session_id": "ctx-1", "message": "it arrived damaged"}).json()
    assert second["decision"] != "ASK"
    assert "Auralix Wave Core 500" in second["reply"]


def test_someone_elses_order_is_not_described():
    c = TestClient(app)
    r = c.post("/chat", json={"customer_id": "CUST-00001", "session_id": "ctx-2", "message": "help with ORD-000001"}).json()
    assert r["decision"] == "ASK" and "couldn't find" in r["reply"]
