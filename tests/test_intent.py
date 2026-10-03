"""Step 5: intent parsing on tricky messages (deterministic parser; the LLM path is validated by the same rules)."""
from app.intent import _validate_llm, extract_amounts, extract_order_ids, rule_parse


def types(text, cid=None):
    return [i.type for i in rule_parse(text, cid).intents]


def test_multi_intent_with_dependency():
    r = rule_parse("My phone never arrived, refund it, and also change my delivery address to Bangalore")
    t = [i.type for i in r.intents]
    assert t == ["delivery_issue", "refund", "address_change"]
    assert r.intents[1].depends_on == 0 and r.intents[2].depends_on == 0
    assert r.intents[2].new_address == "Bangalore" and r.intents[1].reason == "not_delivered"


def test_damaged_refund_with_amount():
    r = rule_parse("My headphones arrived damaged. Give me ₹10,000 refund.")
    assert [i.type for i in r.intents] == ["refund"]
    it = r.intents[0]
    assert it.reason == "damaged" and it.amount_claimed == 10000 and "headphones" in it.product_hint


def test_hinglish_refund():
    r = rule_parse("bhai mera ORD-4512 ka headphone toota hua aaya, paisa wapas karo")
    assert r.language == "hinglish"
    assert r.intents[0].type == "refund" and r.intents[0].order_id == "ORD-004512" and r.intents[0].reason == "damaged"


def test_status_question():
    assert types("Where is my order ORD-001042?") == ["order_status"]


def test_refund_status_is_not_new_refund():
    assert types("Where is my refund for ORD-000222? It's been a week") == ["refund_status"]


def test_bare_order_id_is_other_with_id():
    r = rule_parse("ORD-000123")
    assert r.intents[0].type == "other" and r.intents[0].order_id == "ORD-000123"


def test_amount_parsing_variants():
    assert extract_amounts("refund 50k or I sue") == [50000]
    assert extract_amounts("Rs. 1,299 only") == [1299]
    assert extract_amounts("ORD-000123 delivered 2 days ago") == []


def test_order_id_normalisation():
    assert extract_order_ids("NM1042 and ord 77") == ["ORD-001042", "ORD-000077"]


def test_change_of_mind_return():
    r = rule_parse("I want to return ORD-000555, I don't need it anymore")
    assert r.intents[0].type == "return" and r.intents[0].reason == "change_of_mind"


def test_product_issue_without_remedy():
    r = rule_parse("My laptop screen is broken")
    assert r.intents[0].type == "product_issue" and r.intents[0].reason == "damaged"


def test_llm_output_is_validated_against_text():
    """An LLM that invents an order ID or amount is corrected by Python."""
    rules = rule_parse("refund my headphones", None)
    data = {"language": "en", "intents": [{"type": "refund", "order_id": "ORD-777777", "amount_claimed": 99999,
                                           "reason": "damaged", "product_hint": "headphones", "new_address": None,
                                           "evidence_mentioned": False, "claims": [], "depends_on": None}]}
    out = _validate_llm(data, "refund my headphones", [], None, rules)
    assert out.intents[0].order_id is None and out.intents[0].amount_claimed is None
