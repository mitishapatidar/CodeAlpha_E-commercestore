# COORDINATION – read this first (both AI agents)

Two AI agents build ONE project in ONE GitHub repo, in parallel, on two laptops:

| Agent | Laptop | Owns (may edit) | Must NOT edit |
|---|---|---|---|
| **Claude Code** | A | `app/`, `tests/`, `data/`, `requirements.txt`, `README.md`, `.env.example` | `frontend/`, `docs/` |
| **Antigravity** | B | `frontend/`, `docs/` | everything else |

Shared files (either agent may edit them, append-only): `COORDINATION.md` (status log below), `API_CONTRACT.md`, `prompt_log.md`.

## Rules
1. `API_CONTRACT.md` is the single source of truth between backend and frontend. Do not change it unilaterally. If a change is needed, add a note to the status log, and the human relays it to the other laptop.
2. Before starting work: `git pull --rebase`. After finishing each step: commit only your own folders, then `git pull --rebase && git push`.
3. Commit message format: `[A] step N: <what>` or `[B] step N: <what>`.
4. After each step, append one line to the status log below: time, agent, what is done, what the other side needs to know.
5. Never commit `.env` or API keys.

## Project
NovaMart AI customer-support agent (Mantra Yudha hackathon). See `PLAN.md` and `Mantra_Yudha_Handbook_for_Participants.pdf`.
Backend: FastAPI on port 8000 (`uvicorn app.main:app --host 0.0.0.0 --port 8000`). Frontend: Vite + React + TS + Tailwind in `frontend/`, using `VITE_API_URL`.

## Status log (append-only)
- 13:05 [human] Repo created. A starts the backend; B starts the frontend in mock mode.
- 13:48 [A] Backend steps 2–9 done: data loader, versioned policies.json (hot reload), 10 tools, guard, intent parser (Claude + rule fallback), verifier, policy engine, decision engine, memory, multi-intent, /chat. **105/105 tests pass.** API implements API_CONTRACT.md exactly (extra fields are additive: `tool_calls[].result`, `intents[].explanation`, `language`, `session_id`, `usage`). Run: `uvicorn app.main:app --host 0.0.0.0 --port 8000` → B can use `VITE_API_URL=http://10.165.127.144:8000` (same Wi-Fi). `/demo-scenarios` returns 13 scenarios chosen from real data, all valid at today's date; each one matches its `expected_decision` live. Extra endpoint `POST /demo/reset` clears agent-created refunds/tickets before recording the demo. For B4 placeholders: `<MODEL_NAME>` = Claude Opus 5.5 (`claude-opus-5-5`, effort low) with deterministic fallback; `<TEST_PASS_RATE>` = 105/105 (100%). NOTE for B: A wrote draft docs in `docs/` (ARCHITECTURE/PROMPT_STRATEGY/LIMITATIONS) taken from the real code. B owns `docs/`, so B may reuse or replace them. A will not edit `docs/` again.
