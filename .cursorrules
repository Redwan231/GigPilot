# CLAUDE.md — GigPilot Agent Operating Rules

> You are the coding agent for **GigPilot**. This file is your contract.
> Read it fully at the start of EVERY task. It overrides your default assumptions.

---

## 0. Read before you write (mandatory, every task)

Before executing ANY task, read these in order:

1. `docs/01_PRD.md` — what we build and the **Out of Scope** list (hard boundary).
2. `docs/02_AppFlow.md` — routes, screens, states.
3. `docs/03_UI_Spec.md` — design tokens & component states.
4. `docs/04_TRD.md` — locked stack, versions, folder structure, security, cost controls.
5. `docs/05_Schema.md` — database schema, RLS, auth flow.
6. `docs/06_Plan.md` — the atomic task checklist you execute.

If anything in the code conflicts with these docs, **the docs win** — stop and reconcile.

---

## 1. How you work

- **Follow `06_Plan.md` top to bottom.** Do the lowest unchecked task whose dependencies are all checked.
- **One task at a time.** After finishing a task:
  1. Run its acceptance check (tests/commands named in the task).
  2. Check its box `[x]` in `06_Plan.md`.
  3. Append one line to the Progress Log in `06_Plan.md`: `YYYY-MM-DD | task-id | <commit-sha> | note`.
  4. Commit with message `feat(<area>): <task-id> <summary>`.
- **Never batch multiple tasks into one commit.** Small, reviewable steps.
- **Do not start a task with unchecked dependencies.**

## 2. Scope discipline (most important rule)

- Build **only** what the docs specify. The `Out of Scope (Non-Goals)` section of `01_PRD.md` is a hard wall: **no payments, no Chrome extension, no bidding-platform BYOK, no auto-submit, no team accounts, no fine-tuning** in this MVP.
- If a task seems to require something not in the docs, **STOP and flag it** in your response. Propose a doc change; do not silently invent scope, schema, or dependencies.
- **No new libraries** beyond `04_TRD.md §1`. If you believe one is needed, stop and flag it.

## 3. Stack & versions (locked)

- Backend: Python 3.12, FastAPI 0.115.x, SQLAlchemy 2.0 async, Pydantic v2, Celery 5.4 + Redis 7.4, LangGraph 0.2.x, Alembic.
- Frontend: Next.js 14.2 App Router, React 18.3, TypeScript 5.4, Tailwind 3.4, TanStack Query, RHF+Zod, Recharts.
- DB: PostgreSQL 16 + pgvector (HNSW, cosine, dim **768** = Gemini `gemini-embedding-001`).
- AI: GLM 5.3 Flash via OpenAI-compatible client (Open Inference); **Gemini `gemini-embedding-001`** embeddings (google-genai).
- Also in scope: an **MCP server** (`mcp/server.py`) wrapping services; **guardrails** (`guardrails/`: injection/sanitize/PII); **evals** (`evals/run_evals.py`). See `04_TRD §7b, §10, §11-evals`.
- Deploy (free, no card, always-on): Vercel + Hugging Face Spaces (Docker, honcho/supervisord runs uvicorn+worker+beat) + Upstash Redis + Supabase Postgres + cron-job.org keep-alive. See `04_TRD §9`.
- Pin exact patch versions in lockfiles on first install; reflect them in `04_TRD.md`.

## 4. Non-negotiable engineering rules

- **Security & tenancy:** every user-owned query filters by the authenticated `user_id` from the JWT (never from the request body). RLS is enabled as defense-in-depth — do not disable it, do not connect the app as a BYPASSRLS/superuser role. Secrets only via env vars; never commit or log them.
- **Cost controls (`04_TRD.md §5`):** scoring is reactive + pre-filtered + terse + cached; a draft credit is deducted **only on AI success**; every LLM call writes `ai_usage`. Never batch-score all jobs for all users.
- **Human-in-the-loop:** GigPilot never auto-submits a proposal. Always.
- **Resilience:** per-source adapter isolation, idempotent upserts, retries with backoff, circuit breakers.
- **Design:** components use semantic design tokens from `03_UI_Spec.md` only — no raw hex, no ad-hoc spacing. Every screen implements loading/empty/error/success. Accessibility rules in §7 of that doc are mandatory (focus-visible, contrast, no color-only meaning).
- **Validation:** all input via Pydantic (backend) and Zod (frontend); reject unknown fields; enforce upload size/count limits.
- **Treat source job text and AI output as untrusted** — sanitize before render; external links `rel="noopener noreferrer"`.

## 5. Testing

- Write the test named in the task's acceptance check before marking it done.
- Security gates (P1-10 RLS isolation, P4-7 RLS pen-test, P4-6 auth hardening) must pass before dependent UI tasks.
- Keep the e2e smoke (P4-10) green after Phase 3.

## 6. When you're unsure

Ask / flag rather than guess. A wrong assumption that violates scope, security, or the schema costs more than a question. State the conflict, cite the doc, propose the smallest fix.

## 7. Definition of Done (per task)

- [ ] Code matches the doc it derives from.
- [ ] Acceptance check passes.
- [ ] No new scope, no new deps (or explicitly flagged).
- [ ] `06_Plan.md` box checked + Progress Log line added.
- [ ] Committed with the convention in §1.
