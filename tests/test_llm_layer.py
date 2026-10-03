"""LLM layer with a fake client: the LLM path is validated by Python, and failures fall back safely."""
import json
from types import SimpleNamespace

from app import intent as intent_mod
from app import responder
from app.llm import LLM, Usage


class FakeLLM:
    available = True

    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, *a, **k):
        return self.payload

    def complete(self, *a, **k):
        return self.payload


def test_llm_intents_used_when_valid(monkeypatch):
    payload = {"language": "hinglish", "intents": [
        {"type": "refund", "order_id": "ORD-004512", "product_hint": "headphone", "reason": "damaged",
         "amount_claimed": None, "new_address": None, "evidence_mentioned": False, "claims": ["received_item"],
         "depends_on": None}]}
    monkeypatch.setattr(intent_mod, "get_llm", lambda: FakeLLM(payload))
    r = intent_mod.parse("mera ORD-004512 ka headphone toota aaya, paisa wapas karo", None, [], Usage())
    assert r.parser == "llm" and r.intents[0].order_id == "ORD-004512" and r.language == "hinglish"


def test_llm_failure_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(intent_mod, "get_llm", lambda: FakeLLM(None))
    r = intent_mod.parse("Where is my order ORD-001042?", None, [], Usage())
    assert r.parser == "rules" and r.intents[0].type == "order_status"


def test_responder_rejects_rewrite_with_new_amount(monkeypatch):
    draft = "Hi Asha — I've initiated a refund of ₹2,499 (RFD-ABC123)."
    monkeypatch.setattr(responder, "get_llm", lambda: FakeLLM("Hi Asha! Refund of ₹10,000 done (RFD-ABC123)."))
    reply, src = responder.write_reply(draft, "refund", "en", Usage())
    assert src == "template" and reply == draft


def test_responder_rejects_rewrite_that_drops_reference(monkeypatch):
    draft = "Escalated. Your reference number is ESC-12AB34."
    monkeypatch.setattr(responder, "get_llm", lambda: FakeLLM("I've escalated this for you."))
    assert responder.write_reply(draft, "x", "en", Usage())[1] == "template"


def test_responder_accepts_faithful_rewrite(monkeypatch):
    draft = "Hi Asha — I've initiated a refund of ₹2,499 (RFD-ABC123)."
    good = "Hi Asha, sorry about the trouble! I've started your refund of ₹2,499 (RFD-ABC123)."
    monkeypatch.setattr(responder, "get_llm", lambda: FakeLLM(good))
    assert responder.write_reply(draft, "x", "en", Usage()) == (good, "llm")


def test_anthropic_request_shape_and_refusal_handling():
    """Structured output + low effort; a refusal returns None so callers fall back."""
    seen = {}

    def create(**kw):
        seen.update(kw)
        return SimpleNamespace(stop_reason="end_turn", usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                               content=[SimpleNamespace(type="text", text=json.dumps({"language": "en", "intents": []}))])

    llm = LLM(provider="anthropic", model="claude-opus-5-5", api_key="test")
    llm._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    text, i, o = llm._call_anthropic("sys", "user", intent_mod.INTENT_SCHEMA, 512)
    assert json.loads(text)["language"] == "en" and (i, o) == (10, 5)
    assert seen["output_config"]["format"]["type"] == "json_schema" and seen["output_config"]["effort"] == "low"
    assert seen["model"] == "claude-opus-5-5"

    llm._client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: SimpleNamespace(
        stop_reason="refusal", usage=SimpleNamespace(input_tokens=3, output_tokens=0), content=[])))
    assert llm._call_anthropic("sys", "user", None, 64)[0] is None
