"""Versioned policy store backed by data/policies.json.

Nothing in the agent hardcodes a window, fee or threshold: every number comes
from here. The file is re-read whenever its mtime changes, so a mid-event policy
mutation is a data edit (add a version with its `applies_from`) - no code change,
no restart.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import IST, POLICY_FILE

_lock = threading.Lock()
_cache: dict[str, Any] = {"mtime": None, "data": None, "path": None}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)


def load_policies(path: Path = POLICY_FILE) -> dict:
    path = Path(path)
    mtime = path.stat().st_mtime
    with _lock:
        if _cache["data"] is None or _cache["mtime"] != mtime or _cache["path"] != str(path):
            data = json.loads(path.read_text(encoding="utf-8"))
            versions = sorted(data["refund_policies"], key=lambda v: _parse_dt(v["applies_from"]))
            for v in versions:
                v["_from"] = _parse_dt(v["applies_from"])
                v["_to"] = _parse_dt(v.get("applies_to"))
            data["refund_policies"] = versions
            _cache.update(mtime=mtime, data=data, path=str(path))
        return _cache["data"]


def get_policy(order_date: datetime, request_date: datetime | None = None, path: Path = POLICY_FILE) -> dict:
    """Return the refund/return policy version that governs an order.

    Default rule (both v1 and v2 docs): the version is chosen by the order
    *placement* date and is never applied retroactively. If a future mutation
    switches meta.version_selection to "request_date", the date of the request is
    used instead.
    """
    data = load_policies(path)
    basis = data["meta"].get("version_selection", "order_date")
    when = request_date if (basis == "request_date" and request_date) else order_date
    if when.tzinfo is None:
        when = when.replace(tzinfo=IST)

    chosen = None
    for v in data["refund_policies"]:
        if v["_from"] <= when and (v["_to"] is None or when <= v["_to"]):
            chosen = v
    if chosen is None:  # gap or before first version: fall back to latest version that started before `when`
        started = [v for v in data["refund_policies"] if v["_from"] <= when]
        chosen = started[-1] if started else data["refund_policies"][0]
    return chosen


def section(name: str, path: Path = POLICY_FILE) -> dict:
    """Non-versioned policy sections: shipping, payment, cancellation, warranty, escalation..."""
    return load_policies(path)[name]


def gst_rate() -> float:
    return float(load_policies()["meta"].get("gst_rate", 0.18))
