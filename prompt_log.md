# Mantra Yudha – Prompt Efficiency Log

Team: **ELEVATE**   Problem Statement: **AI Customer Support Agent from Hell (NovaMart)**

Main coding assistant: **Claude Code (Claude Opus 5.5)**. Planning prompts were written up front in `PLAN.md`,
`BUILD_PROMPTS.md` and `FINAL_PROMPTS.md`, then sent one step at a time (delta prompts, not re-explaining context).

| # | Time | Tool | Goal | Prompt (short) | ~Tokens* | Result | Iterations |
|---|------|------|------|----------------|---------|--------|-----------|
| 1 | 08:35 | ChatGPT | Idea generation | Prompt A (problem → plan) | – | ✅ PLAN.md | 1 |
| 2 | 12:50 | Claude Code | Context | Share handbook PDF + dataset; "don't start yet" | small | ✅ handbook + data read, plan confirmed | 1 |
| 3 | 13:00 | Claude Code | LLM choice | "Which LLM? cheaper options?" | small | ✅ Claude Opus 5.5 + provider-agnostic adapter + no-key fallback | 2 |
| 4 | 13:02 | Claude Code | Step 1 setup + schema | BUILD_PROMPTS #1: setup project, inspect data, list every policy rule | medium | ✅ requirements, .env.example, schema table, policy bullets | 1 |
| 5 | 13:10 | Claude Code | Steps 2–9 backend | "Use whatever tools, make it professional" → data loader, policies.json, 10 tools, guard, intent, verifier, policy engine, decision, memory, /chat, tests | large | ✅ 95 → 103 tests, 900-turn fuzz 0 crashes | 1 + 6 minimal-diff fixes |
| 6 | 13:40 | Claude Code | Bug fixes found by own testing | follow-up reason not merged; "laptop" matched "Laptop Bag"; "Spark" product name triggered safety; duplicate refunds | small each | ✅ fixed + regression tests | 4 |
| 7 | 13:48 | Claude Code | API contract alignment | LAPTOP_A_ADDENDUM / API_CONTRACT: exact endpoints + field names | medium | ✅ contract test added, 105 tests | 1 |
| 8 | 14:05 | Claude Code | GitHub setup | Create repo ELEVATE_mantrayudha, branches, add collaborators + organiser | small | ✅ repo, 3 branches, 3 collaborators | 2 |
| 9 | 14:18 | Claude Code | Step 12 React console | FINAL_PROMPTS C1: Vite + React + TS + Tailwind v4, 3-panel console + Agent Brain | large | ✅ build 0 errors, all 13 scenarios ✓ in browser | 1 + polish loop |
| 10 | 14:35 | Claude Code | Storefront UI | "Make the frontend look like the NovaMart e-commerce site" | medium | ✅ storefront + floating support chat, /products + /categories | 1 |
| 11 | 14:45 | Claude Code | Screenshots + README run steps | C2: verify in browser, save 3 key screenshots | small | ✅ docs/screenshots (4) | 1 |
| 12 | 15:00 | Claude Code | Step 13 final docs + submission check | C3/C4: README, ARCHITECTURE, PROMPT_STRATEGY, LIMITATIONS, DEMO_SCRIPT, fresh-clone check | medium | ✅ fresh clone: pip + 106 tests + npm build pass; no .env committed | 1 |

\*Token counts of the coding assistant were not metered per prompt; sizes are relative (small < 500 words, medium
< 1,500, large = multi-step spec).

**Totals:** prompts **12** major (+ ~10 short fix/confirm messages) · first-try success rate **~83 %** (10/12 major
prompts worked without a redo; LLM choice and GitHub setup needed a follow-up).

**Runtime efficiency of the agent itself:** at most 2 LLM calls per customer turn (parse + phrase), effort `low`,
cached system prompts; 0 LLM calls in deterministic mode; average 3.6 tool calls and 3.8 ms per turn across the
13 demo scenarios (see `docs/PROMPT_STRATEGY.md` §8).

Key efficiency techniques used: single master spec (PLAN.md), delta prompts per step, minimal-diff fixes with
regression tests, few-shot examples in the intent prompt, structured JSON output, deterministic Python for all
decisions, LLM output validated instead of re-prompted.
