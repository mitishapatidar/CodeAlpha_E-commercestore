import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Tests are deterministic: never call a real LLM and pin "now" to the dataset's end.
os.environ["LLM_MODE"] = "off"
os.environ.setdefault("AGENT_NOW", "2026-10-03T12:00:00+05:30")
import tempfile  # noqa: E402

os.environ["NOVAMART_RUNTIME_DIR"] = tempfile.mkdtemp(prefix="novamart-test-")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_actions():
    """Each test starts with no prior agent actions (the duplicate-refund guard is global by design)."""
    from app import tools
    if tools.ACTIONS_LOG.exists():
        tools.ACTIONS_LOG.unlink()
    tools.reset_actions_index()
    yield
