# 01 — Product Requirements Document (PRD)

**Product:** GigPilot
**Version:** 1.0 (MVP)
**Owner:** Team GigPilot (Daffodil International University)
**Status:** Locked for MVP build
**Last updated:** 2026-11-20

> This document is the single source of truth for WHAT we are building and WHY.
> If a requirement is not written here, it is not in the MVP. Do not infer scope.

---

## 1. Core Problem

Freelancers on remote-work and bidding platforms face three compounding problems:

1. **Discovery is fragmented and manual.** Relevant jobs are spread across many platforms (RemoteOK, Remotive, Himalayas, WeWorkRemotely, and bidding sites). Freelancers tab-hop, re-search, and still miss good matches.
2. **Proposals are slow and low-converting.** Writing a tailored proposal takes 30–45 minutes. The average win rate is roughly 3%. Most freelancers fall back on copy-pasted templates that convert even worse.
3. **There is no learning loop.** When a proposal loses, the freelancer gets zero feedback. Nothing improves over time.

This is acute in Bangladesh — the world's second-largest freelancer supply market (700K+ active freelancers, $1B+ annual earnings) — where english-second-language freelancers are disadvantaged on proposal quality specifically.

## 2. Product Vision (one sentence)

GigPilot is an AI agent that aggregates jobs across platforms, scores each one against the freelancer's profile, drafts a proposal in the freelancer's own voice, and learns from won/lost outcomes.

## 3. Target Persona (MVP: exactly one)

**"Rina" — the growth-stage remote freelancer.**

| Attribute | Detail |
|---|---|
| Role | Freelance developer / designer / writer |
| Location | Bangladesh / South Asia (English-second-language) |
| Experience | 1–4 years freelancing, has 5–20 past proposals/projects |
| Pain | Spends evenings searching + writing proposals, low reply rate, no idea why |
| Device | Laptop (primary), Chrome browser |
| Willingness to pay | Low-to-moderate; $19/mo is a real decision (~2–3 hrs billable) |
| Tech literacy | Comfortable with web apps, not with code |

**Explicitly NOT our MVP persona:** agencies, enterprise recruiters, non-freelance job seekers, freelancers with zero writing samples (see cold-start handling in §6).

## 4. MVP User Stories

Stories are grouped by epic. Each has an ID used in `06_Plan.md`.

### Epic A — Account & Profile
- **US-A1:** As a freelancer, I can sign up with email + password so I have a private account.
- **US-A2:** As a freelancer, I can log in and stay logged in across sessions (refresh token).
- **US-A3:** As a freelancer, I can build a profile (skills, categories, hourly rate, experience level, bio) so scoring and drafting are personalized.
- **US-A4:** As a freelancer, I can upload 2–5 past proposals / writing samples so the drafter matches my voice (see cold-start, §6).

### Epic B — Job Aggregation & Discovery
- **US-B1:** As a freelancer, I can see a unified feed of jobs aggregated from multiple platforms.
- **US-B2:** As a freelancer, I can filter the feed by platform, category, skill, and budget.
- **US-B3:** As a freelancer, I can open a job to see full details and its source link.

### Epic C — AI Scoring
- **US-C1:** As a freelancer, I can request a win-probability score (0–100) for a job, computed against my profile. (MVP dimensions use only job-board-available data: skills match, seniority fit, rate/budget fit, freshness — see `04_TRD.md §5b`. We do NOT fake "client history" or "competitor count" that job boards don't expose.)
- **US-C2:** As a freelancer, I can see WHY a job scored the way it did (per-dimension reasoning), on demand.
- **US-C3:** As a freelancer, I can sort/filter my feed by score to focus on best-fit jobs.

### Epic D — AI Drafting (Voice RAG)
- **US-D1:** As a freelancer, I can generate a proposal draft for a job that matches my writing voice.
- **US-D2:** As a freelancer, I can edit the draft before using it.
- **US-D3:** As a freelancer, I can copy/export the final proposal.
- **US-D4:** As a freelancer, each generated draft consumes one credit from my monthly quota.

### Epic E — Win/Loss Learning Loop
- **US-E1:** As a freelancer, I can mark a proposal's outcome (won / lost / no-response).
- **US-E2:** As a freelancer, I can see my win-rate and proposal stats over time on a dashboard.
- **US-E3:** As the system, I use outcome data to adjust future scoring for that freelancer.

### Epic F — Credits & Plan
- **US-F1:** As a free user, I get 30 drafts/month and a daily scoring cap.
- **US-F2:** As a user, I can see my remaining credits and reset date.
- **US-F3:** As a user, I am blocked (with a clear upgrade prompt) when I exceed my quota.

### Epic G — MCP Integration (AI-client access)
- **US-G1:** As a power user, I can connect GigPilot to my AI client (Claude Desktop / Cursor) via an MCP server and run `search_jobs`, `score_job`, `draft_proposal`, `list_proposals`, `set_outcome` as tools — under my account, credits, and limits. (See `04_TRD.md §10`. This is a differentiator and fills the submission's MCP section.)

### Cross-cutting (in scope, not user stories)
- **Guardrails:** prompt-injection defense on untrusted job/sample text, input sanitization, PII scrubbing, output validation (`04_TRD.md §7b`).
- **Evaluation harness:** offline LLM-as-judge for draft quality, scoring accuracy, and injection-resistance (`04_TRD.md §11-evals`).

## 5. Success Metrics

| Metric | Target (first demo cohort) | How measured |
|---|---|---|
| Activation | ≥ 60% of signups complete profile + upload ≥ 2 samples | DB event |
| Core-loop completion | ≥ 50% of activated users generate ≥ 1 draft | DB event |
| Draft acceptance | ≥ 40% of drafts exported/used without full rewrite | edit-delta heuristic |
| Scoring usefulness | ≥ 70% of users use score-sort at least once | UI event |
| Outcome capture | ≥ 25% of sent proposals get an outcome marked | DB event |
| AI cost per Pro user | ≤ $1.00 / month | metered inference log |
| Gross margin (Pro) | ≥ 75% | revenue − variable cost |

## 6. Key Product Decisions (resolved ambiguities)

- **Cold-start for Voice RAG:** New users with < 2 samples get drafts from a **style questionnaire + structured template** (tone, formality, length preferences) instead of RAG retrieval. A persistent banner prompts them to upload samples to unlock true voice-matching. We never block drafting on missing samples.
- **Scoring is reactive, not proactive.** We do NOT pre-score every job for every user (cost + noise). Jobs are cheaply pre-filtered by a non-AI heuristic (skill keyword overlap); AI scoring runs only on jobs the user views or explicitly requests, subject to the daily cap.
- **Credits meter drafting, not scoring.** Scoring is cheap but capped per day to prevent abuse; drafting is the metered quota (30 free / 500 Pro).

## 7. Out of Scope (Non-Goals) — MVP will NOT include

These are deliberately excluded. The coding agent must **not** build them, scaffold them, or add schema/flows for them unless a future PRD version re-includes them.

1. **Payments / billing integration.** No Stripe/bKash/Nagad in MVP. Plan tier is set manually in DB / admin for the demo. (Rationale: Stripe is unavailable in Bangladesh; local gateways need business KYC. Out of scope until post-competition.)
2. **Chrome extension.** Web app only for MVP. Extension is Phase 2 (post-MVP).
3. **Upwork / Fiverr / Freelancer.com bidding-platform integration (BYOK).** MVP uses only the 4 free read-only APIs (RemoteOK, Remotive, Himalayas, WeWorkRemotely). Authenticated bidding platforms are post-MVP.
4. **Auto-submit / auto-apply.** GigPilot never submits a proposal on the user's behalf. Human-in-the-loop always. (This is a permanent product principle, not just MVP.)
5. **Team / agency accounts, multi-seat, roles.** Single-user accounts only.
6. **Mobile native apps.** Responsive web is sufficient.
7. **Multi-language UI / proposal output in non-English languages.** English only for MVP.
8. **Real-time collaboration, chat, messaging with clients.**
9. **Fine-tuning or training custom models.** We use hosted inference (GLM 5.3 Flash) + RAG only.
10. **Advanced analytics (cohorts, funnels, A/B infra).** Only the per-user win-rate dashboard in US-E2.

## 8. Dependencies & Assumptions

- Z.ai GLM 5.3 Flash is reachable via an OpenAI-compatible endpoint (Open Inference) with a valid API key.
- Google Gemini embeddings API key (`gemini-embedding-001`, AI Studio free tier) is available.
- The 4 source platforms expose their current free JSON/RSS endpoints; adapter breakage is expected and handled gracefully (see `04_TRD.md` resilience section).
- Demo runs on free-tier infrastructure (see `04_TRD.md` deployment).

## 9. Open Risks (tracked, not resolved here)

| Risk | Owner doc |
|---|---|
| Source API rate-limits / ToS | `04_TRD.md` §Resilience |
| AI cost blow-up from scoring | `04_TRD.md` §Cost controls |
| Voice RAG cold-start quality | this doc §6 |
| Free-tier abuse (multi-account) | `04_TRD.md` §Security |
| Payment unavailability in BD | out of scope (this doc §7.1) |
