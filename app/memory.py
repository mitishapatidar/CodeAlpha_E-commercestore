"""Conversation memory: in-session state + prior conversations/tickets from the dataset."""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

from app.data import get_store

_EVIDENCE_CUSTOMER = re.compile(r"\b(photo|photos|pic|pics|picture|image|video|screenshot|attached|sent)\b", re.I)
_EVIDENCE_AGENT_ACK = re.compile(r"\b(thanks for the (photo|photos|pictures|images|video)|received (the|your) (photo|photos|images|video))\b", re.I)
_AGENT_ASKED_PHOTO = re.compile(r"\b(share|send|upload|attach)\b.{0,30}\b(photo|photos|picture|image|video)\b", re.I)


@dataclass
class Session:
    session_id: str
    customer_id: str | None
    history: list[dict] = field(default_factory=list)       # [{"role": "customer"|"agent", "text": str}]
    pending: list[dict] = field(default_factory=list)       # intents waiting for info: {"intent": {...}, "missing": str, "options": [...]}
    claims: dict[str, set] = field(default_factory=dict)    # order_id -> claims made in this session
    evidence: bool = False
    warned_abuse: bool = False
    clarify_asked: set = field(default_factory=set)
    prior: dict | None = None                              # get_conversations result, loaded once per session
    last_seen: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self, ttl_s: int = 6 * 3600):
        self._s: dict[str, Session] = {}
        self._lock = threading.Lock()
        self.ttl = ttl_s

    def get(self, session_id: str, customer_id: str | None) -> Session:
        with self._lock:
            now = time.time()
            for k in [k for k, v in self._s.items() if now - v.last_seen > self.ttl]:
                del self._s[k]
            s = self._s.get(session_id)
            if s is None or (customer_id and s.customer_id and s.customer_id != customer_id):
                s = Session(session_id=session_id, customer_id=customer_id)  # never mix customers in one session
                self._s[session_id] = s
            s.last_seen = now
            return s

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._s.pop(session_id, None)


SESSIONS = SessionStore()


def prior_evidence(customer_id: str, order_id: str | None) -> dict:
    """Did the customer already send photos in an earlier conversation (optionally for this order)?"""
    for conv in reversed(get_store().convs_by_customer.get(customer_id, [])):
        if order_id and conv.get("order_id") not in (None, order_id):
            continue
        for m in conv["messages"]:
            if (m["role"] == "agent" and _EVIDENCE_AGENT_ACK.search(m["message"])) or (
                    m["role"] == "customer" and _EVIDENCE_CUSTOMER.search(m["message"])):
                return {"found": True, "conversation_id": conv["conversation_id"], "when": conv["started_at"]}
    return {"found": False}


def agent_asked_for_photo(customer_id: str) -> bool:
    convs = get_store().convs_by_customer.get(customer_id, [])
    return bool(convs) and any(m["role"] == "agent" and _AGENT_ASKED_PHOTO.search(m["message"])
                               for m in convs[-1]["messages"])


def open_ticket_for(prior: dict | None, order_id: str, categories: set[str]) -> dict | None:
    if not prior:
        return None
    for t in prior.get("open_tickets", []):
        if t.get("order_id") == order_id and t["category"] in categories:
            return t
    return None
