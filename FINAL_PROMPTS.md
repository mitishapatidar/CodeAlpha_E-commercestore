# Claude-only final prompts (from 14:00) – backend already done (105/105 tests)

| Time | Prompt |
|---|---|
| 14:00–14:35 | C1 – React frontend |
| 14:35–14:50 | C2 – Polish + verify in browser |
| 14:50–15:05 | C3 – Docs + README final |
| 15:05–15:15 | C4 – Final check + push |
| 15:15–15:35 | Record demo video (team) |
| 15:35–15:45 | Rehearse pitch |

## C1 – React frontend
```
Plan change: Antigravity is dropped. You (Claude) now also own frontend/ and docs/. Update COORDINATION.md accordingly (one status line).
Build frontend/ "NovaMart Agent Console" against the running backend, following API_CONTRACT.md (plus your additive fields).
Stack: Vite + React + TypeScript + Tailwind CSS v4 (@tailwindcss/vite) + lucide-react + framer-motion. API base from VITE_API_URL (default http://localhost:8000). No mock mode needed; if /health fails, show a clear "backend offline" banner with a retry.
Layout (full height, 3 columns):
1. Top bar: "NovaMart · Agent Console" logo, live status dot, model name, policy versions, session stats (messages, total tokens, LLM calls, avg latency).
2. Left sidebar (300px): debounced customer search; selected customer card (name, email, city, loyalty-tier chip, segment, status); order list (ID, date, ₹ amount, status chips); "Demo scenarios" from /demo-scenarios grouped by category, each with an expected-decision chip and one-click run; a "Reset demo data" button (POST /demo/reset).
3. Center chat: agent messages on the left, customer on the right. Each agent reply has a decision badge – ANSWER emerald, ASK sky, ACT amber, ESCALATE rose – with an icon, plus refund ₹ / ticket ID chips. Typing state "Agent is verifying…" animates the loop steps. Enter sends, Shift+Enter adds a newline. A "New session" button calls /reset. Empty state with 4 suggestion chips.
4. Right panel (380px), "Agent Brain" for the selected message: a vertical timeline Understand → Verify → Policy → Decide → Act built from intents (type, order, decision, reason), tool_calls (name, compact params, ✓/✗, summary), policy_version, flags as warning chips (injection/legal/safety), reasoning steps, tokens + latency, and a "Copy JSON" button. Clicking any agent message shows its trace here.
Design: dark, bg #0B0F17, panels #111827, 1px #1F2937 borders, rounded-2xl, red→orange accent gradient (event theme), Inter font, smooth framer-motion entrances, accessible focus rings, no layout shift, ₹ formatting with en-IN. Responsive: the right panel becomes a drawer below 1024px and the sidebar becomes a drawer below 640px.
Finish when npm run build has zero errors. Commit "[A] step 12: React agent console" and push.
```

## C2 – Polish + verify in the browser
```
Start the backend and frontend, open the UI in the browser, and run ALL demo scenarios one by one. For each, confirm the badge matches expected_decision and that the trace renders. Fix any UI bug, overflow, long-text wrapping, or console error. Add loading skeletons and error toasts with retry. Take screenshots of 3 key scenarios (refund cap ACT, OTP contradiction ESCALATE, prompt injection) into docs/screenshots/. Commit and push.
```

## C3 – Docs + README final
```
Finalize the submission docs from the real code:
- README.md: one-paragraph pitch, screenshot, features, quick start (backend + frontend + tests), env vars, model used (name + version), project structure, demo video link placeholder <DEMO_LINK>, team section placeholder.
- docs/ARCHITECTURE.md: mermaid diagrams of the agent loop and the data model, plus the component list.
- docs/PROMPT_STRATEGY.md: instruction hierarchy L1–L4, injection defense, 2-LLM-call design, measured token stats per message from real runs, and the actual prompts used.
- docs/LIMITATIONS.md: honest failure modes.
- docs/DEMO_SCRIPT.md: a 4-minute script with 7 scenarios and what to say for each.
Also fill prompt_log.md with the main prompts used in this build (tool, goal, short prompt, result). Commit and push.
```

## C4 – Final check
```
Final submission check: clone the repo fresh into a temp folder, follow the README exactly (pip install, npm install, run backend + frontend, pytest), and fix anything that fails. Make sure .env is not committed, requirements.txt and package.json are complete, and the repo is public-ready. Run POST /demo/reset. Give me a 60-second pitch script plus the 5 strongest points to tell the judges. Commit and push.
```

## Mutation prompt (if organizers change a policy)
```
Policy update announced: <paste rule>. Update data/policies.json only (new version / applies_from), with no code change. Add 2 tests for it, run all tests, show which demo decisions changed, then commit and push.
```

## Bug-fix prompt
```
Bug: <exact error / wrong behavior>. Steps: <what I did>. Expected: <x>. Fix minimally, re-run related tests/build, then commit and push.
```
