"""Central settings, read once from the environment / .env file."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

IST = timezone(timedelta(hours=5, minutes=30))


def _env(name: str, default: str = "") -> str:
    # python-dotenv keeps inline comments out, but strip stray whitespace anyway
    return os.getenv(name, default).split(" #")[0].strip()


DATA_DIR = (ROOT / _env("DATA_DIR", "data")).resolve()
POLICY_FILE = DATA_DIR / "policies.json"
RUNTIME_DIR = Path(_env("NOVAMART_RUNTIME_DIR") or ROOT / "runtime")
ACTIONS_LOG = RUNTIME_DIR / "actions_log.jsonl"

LLM_PROVIDER = _env("LLM_PROVIDER", "anthropic").lower()
LLM_MODEL = _env("LLM_MODEL", "claude-opus-5-5")
LLM_API_KEY = _env("LLM_API_KEY") or _env("ANTHROPIC_API_KEY")
LLM_TIMEOUT_S = float(_env("LLM_TIMEOUT_S", "30"))
# "off" forces the deterministic path (useful for tests and offline demos)
LLM_MODE = _env("LLM_MODE", "auto").lower()  # auto | off

# Optional fixed "current time" for reproducible evaluation (ISO 8601).
AGENT_NOW = _env("AGENT_NOW")


def now_ist(override: str | datetime | None = None) -> datetime:
    """The agent's notion of *now*: request override > AGENT_NOW env > wall clock (IST)."""
    value = override or AGENT_NOW
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=IST)
    if value:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=IST)
    return datetime.now(IST)
