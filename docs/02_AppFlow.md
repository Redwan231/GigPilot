# 02 — Application Flow & State Machine

**Product:** GigPilot
**Version:** 1.0 (MVP)
**Last updated:** 2026-11-20

> Screen-by-screen navigation, routes, actions, and every empty/loading/error state.
> Routes here are the contract between frontend (Next.js App Router) and backend.
> Any screen or state not listed is out of scope.

---

## 1. Route Map (Next.js App Router)

| Route | Auth | Screen | Notes |
|---|---|---|---|
| `/` | public | Landing | Redirects to `/app` if authenticated |
| `/login` | public | Login | Redirects to `/app` if already authed |
| `/signup` | public | Sign up | |
| `/onboarding` | protected | Profile + sample upload wizard | Forced after first signup until complete |
| `/app` | protected | Job feed (home) | Default authed landing |
| `/app/jobs/[jobId]` | protected | Job detail + score + draft | |
| `/app/proposals` | protected | Proposals list (outcomes) | |
| `/app/proposals/[proposalId]` | protected | Proposal detail / edit | |
| `/app/dashboard` | protected | Win-rate analytics | |
| `/app/settings` | protected | Profile, samples, plan, credits | |
| `*` | — | 404 Not Found | |

**Route protection:** A Next.js middleware checks the presence/validity of the session (access token in memory + refresh cookie). Unauthed access to a `protected` route → redirect to `/login?next=<path>`. Authed access to `/login` or `/signup` → redirect to `/app`.

---

## 2. Global States

Every data-fetching screen implements these four states explicitly:

- **Loading:** skeleton matching the final layout (never a bare spinner on full-page loads).
- **Empty:** purposeful illustration + one-line explanation + primary CTA.
- **Error:** inline error card with a human message + "Retry" button; never a raw stack trace.
- **Success:** the content.

**Global auth failure (401 on any API call):** attempt one silent refresh; if refresh fails, clear session and redirect to `/login?expired=1`.

**Global offline / network error:** toast "You're offline — changes aren't saved" and disable mutating actions.

---

## 3. Auth Flow (state machine)

```
            ┌─────────┐
            │ Visitor │
            └────┬────┘
      ┌──────────┴──────────┐
      ▼                     ▼
 [/signup]              [/login]
      │                     │
  submit creds          submit creds
      │                     │
  ┌───▼───┐  invalid    ┌───▼───┐ invalid
  │ 201   │◄────────┐   │ 200   │◄────────┐
  └───┬───┘  show   │   └───┬───┘  show    │
      │     field   │       │    "invalid  │
      │     errors──┘       │    creds"────┘
      ▼                     ▼
 profile_complete == false? ──yes──► [/onboarding]
      │                                   │
      no                            complete wizard
      ▼                                   │
   [/app] ◄───────────────────────────────┘
```

**Token model (see `04_TRD.md` for crypto detail):**
- Access token: JWT, 15 min, held in memory (JS variable / React context) — never localStorage.
- Refresh token: opaque, 7 days, httpOnly + Secure + SameSite=Lax cookie; rotated on every use.
- On app load: call `POST /auth/refresh`; if 200, hydrate session; if 401, treat as logged-out.

---

## 4. Screen Specs

### 4.1 Landing (`/`)
- **Purpose:** explain value, drive signup.
- **Sections:** hero (tagline + "Get started" CTA → `/signup`), 3 value props (Discover / Draft / Learn), pricing (Free vs Pro), footer.
- **Actions:** "Get started" → `/signup`; "Log in" → `/login`.
- **States:** static; no data fetch.

### 4.2 Sign up (`/signup`)
- **Fields:** email, password (min 8, 1 number), confirm password.
- **Validation:** inline, on blur + on submit. Email format, password strength meter, match check.
- **Action:** `POST /auth/signup` → on 201, auto-login and go to `/onboarding`.
- **Errors:** 409 email exists → inline "An account with this email already exists. Log in?" (link). 422 → field errors.

### 4.3 Login (`/login`)
- **Fields:** email, password.
- **Action:** `POST /auth/login` → 200 sets session, redirect to `next` param or `/app` (or `/onboarding` if `profile_complete=false`).
- **Errors:** 401 → "Email or password is incorrect." (generic, no user enumeration).
- **Extras:** `?expired=1` shows "Your session expired, please log in again."

### 4.4 Onboarding wizard (`/onboarding`) — 3 steps
Forced until `profile_complete = true`. Progress bar. Can go back; cannot skip required fields.

1. **Profile basics:** display name, primary category (dropdown), skills (tag input, ≥ 3), experience level (junior/mid/senior), hourly rate (number, currency USD).
2. **Writing samples:** upload or paste 2–5 past proposals/writing samples (textarea or .txt/.md/.pdf up to 1MB each). **Skippable with explicit "I'll do this later"** → sets cold-start mode (PRD §6); shows warning that drafts won't be voice-matched yet.
3. **Style questionnaire (only if samples skipped):** tone (formal/friendly/direct), proposal length (short/medium/long), greeting style. Used as drafting fallback.
- **Finish action:** `PATCH /me/profile` + `POST /me/samples` → set `profile_complete=true`, go to `/app`.

### 4.5 Job feed (`/app`) — home
- **Data:** `GET /jobs?platform=&category=&skill=&budget_min=&budget_max=&min_score=&sort=newest|score&limit=&cursor=` (cursor-paginated; null-budget jobs are included — see `04_TRD §4.3`).
- **Layout:** left filter rail (platform, category, skill, budget range, min-score), main list of job cards, top bar with credits remaining + search.
- **Job card:** title, platform badge, snippet, budget, posted-time, skill tags, **score chip** (if scored; else "Score" button).
- **Actions per card:** click → `/app/jobs/[jobId]`; "Score" → calls `POST /jobs/{id}/score` (consumes daily score allowance, not a draft credit), updates chip in place.
- **Sort:** newest (default), score desc. Score-sort only ranks already-scored jobs; unscored sink to bottom with CTA.
- **States:**
  - Loading: 6 skeleton cards.
  - Empty (no jobs match filters): "No jobs match these filters. Reset filters." + reset button.
  - Empty (aggregation not yet run / all sources down): "We're fetching fresh jobs — check back in a few minutes." + manual "Refresh" (rate-limited).
  - Error: inline retry.

### 4.6 Job detail (`/app/jobs/[jobId]`)
- **Data:** `GET /jobs/{id}` (full description, metadata, source URL, existing score, existing drafts).
- **Panels:**
  - Header: title, platform, budget, posted time, "View original" (external link, new tab, `rel=noopener`).
  - **Score panel:** if unscored → "Score this job" button (`POST /jobs/{id}/score`). If scored → big score number + per-dimension bars for the 4 MVP dimensions (Skills, Seniority, Rate fit, Freshness — see `04_TRD §5b`); "Why?" expander calls `GET /jobs/{id}/score/why` (lazy-generates + caches reasoning).
  - **Draft panel:** "Generate proposal" button (disabled if 0 credits → shows upgrade prompt). On click → `POST /jobs/{id}/draft` (consumes 1 credit). Streams/returns draft into an editable textarea.
  - Draft actions: Save, Copy, Export (.txt/.md), Regenerate (consumes another credit — confirm dialog), "Mark as used" → creates a Proposal record.
- **States:**
  - Scoring in progress: button → inline spinner + "Scoring…".
  - Drafting in progress: textarea skeleton + "Drafting in your voice…".
  - Draft error (AI timeout/failure): "Draft failed — your credit was not charged. Retry." (credit only deducted on success).
  - 0 credits: draft button disabled + "You've used all 30 drafts this month. Upgrade to Pro for 500." (link to settings/plan).

### 4.7 Proposals list (`/app/proposals`)
- **Data:** `GET /proposals?status=...`
- **List item:** job title, platform, created date, status badge (draft / used / won / lost / no-response).
- **Actions:** click → detail; quick outcome set (won/lost/no-response) via inline control → `PATCH /proposals/{id}` (US-E1).
- **States:** empty → "No proposals yet. Find a job and generate your first draft." + CTA to `/app`.

### 4.8 Proposal detail (`/app/proposals/[proposalId]`)
- View/edit saved proposal text, linked job, outcome control, timestamps.
- Actions: edit + save (`PATCH`), set outcome, delete (confirm).

### 4.9 Dashboard (`/app/dashboard`)
- **Data:** `GET /me/stats`
- **Widgets:** win-rate % (won / outcome-marked), proposals sent over time (line), outcome breakdown (pie), avg score of won vs lost (bar), credits used this month.
- **States:** empty (no outcomes yet) → "Mark proposal outcomes to unlock your win-rate insights."

### 4.10 Settings (`/app/settings`)
- **Tabs:** Profile (edit US-A3 fields), Samples (list/add/delete writing samples — re-embeds on change), Plan & Credits (current tier, credits remaining, reset date; "Upgrade" is a demo stub that explains payments are coming), Account (change password, log out, delete account).

---

## 5. Core-Loop Happy Path (end to end)

```
login → /app feed → open job → "Score" → see 82/100
     → "Generate proposal" (−1 credit) → edit draft → "Mark as used"
     → later: /app/proposals → set outcome "Won"
     → /app/dashboard → win-rate updates → scoring recalibrates next time
```

---

## 6. Error & Edge-Case Matrix

| Situation | UX behavior | Credit effect |
|---|---|---|
| AI scoring timeout/5xx | inline error + retry; score left unscored | none (scoring not metered as credit) |
| Daily scoring cap hit | "Daily scoring limit reached. Resets in Xh." | blocked |
| AI drafting timeout/5xx | "Draft failed — credit not charged. Retry." | **refund/none** (deduct only on success) |
| 0 draft credits | button disabled + upgrade prompt | blocked |
| Source platform adapter down | job still viewable from cache; "source link may be stale" | n/a |
| Duplicate job across platforms | shown once (dedup by platform+external_id + fuzzy title) | n/a |
| User deletes all samples | drafting falls back to cold-start questionnaire mode | n/a |
| Refresh token expired | redirect `/login?expired=1` | n/a |
| Rate-limited manual "Refresh" | toast "Please wait before refreshing again." | n/a |
