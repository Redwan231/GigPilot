# 03 — UI Specification & Design System

**Product:** GigPilot
**Version:** 1.0 (MVP)
**Last updated:** 2026-11-20
**Implementation:** Tailwind CSS 3.4 + CSS variables. Tokens below are the source of truth; Tailwind config extends from them.

> Every color, size, and component state the app uses. No ad-hoc hex values in components — use tokens only.

---

## 1. Brand

- **Personality:** sharp, confident, "co-pilot" not "chatbot". Clean, dense-but-breathable, dark-first.
- **Accent:** emerald green (growth / "win").
- **Anti-pattern:** avoid generic SaaS purple; avoid rainbow charts; avoid heavy drop shadows.

---

## 2. Color Tokens

Defined as CSS variables on `:root` (light) and `.dark` (dark). Dark is the default app theme; marketing landing is also dark. Light theme must still be fully usable.

### 2.1 Primitive palette

| Token | Hex | Use |
|---|---|---|
| `--brand-600` | `#059669` | Primary accent (light theme) |
| `--brand-500` | `#10B981` | Hover/active |
| `--brand-400` | `#4ADE80` | Accent on dark backgrounds |
| `--brand-050` | `#ECFDF5` | Accent tint bg |
| `--ink-900` | `#0F172A` | Darkest surface / dark bg base |
| `--ink-800` | `#1E293B` | Dark elevated surface |
| `--ink-700` | `#334155` | Dark border / muted |
| `--ink-500` | `#64748B` | Secondary text |
| `--ink-400` | `#94A3B8` | Tertiary text / placeholder |
| `--ink-200` | `#E2E8F0` | Light border |
| `--ink-100` | `#F1F5F9` | Light muted bg |
| `--ink-050` | `#F8FAFC` | Light app bg |
| `--white` | `#FFFFFF` | Light surface |
| `--info` | `#2563EB` | Info/secondary data |
| `--warn` | `#D97706` | Warnings |
| `--danger` | `#DC2626` | Errors/destructive |
| `--success` | `#059669` | Success (== brand) |

### 2.2 Semantic tokens (what components reference)

| Semantic | Light | Dark |
|---|---|---|
| `--bg` | `--ink-050` | `--ink-900` |
| `--surface` | `--white` | `--ink-800` |
| `--surface-2` | `--ink-050` | `--ink-900` |
| `--border` | `--ink-200` | `--ink-700` |
| `--text` | `--ink-900` | `#E8ECF1` |
| `--text-muted` | `--ink-500` | `--ink-400` |
| `--accent` | `--brand-600` | `--brand-400` |
| `--accent-contrast` | `--white` | `--ink-900` |
| `--accent-tint` | `--brand-050` | `rgba(74,222,128,0.12)` |
| `--ring` | `--brand-600` | `--brand-400` |

**Rule:** components reference semantic tokens only (`var(--surface)`, `var(--text)`), never primitives or raw hex. Theme switch flips the semantic layer. Always pair any colored background with a token-defined text color (contrast ≥ 4.5:1 for body text).

---

## 3. Typography

- **Heading font:** `Space Grotesk` (Google Fonts), fallback `ui-sans-serif, system-ui, sans-serif`.
- **Body font:** `Inter` (Google Fonts), fallback `ui-sans-serif, system-ui, sans-serif`.
- **Mono (code/JSON):** `JetBrains Mono`, fallback `ui-monospace, monospace`.

### Type scale (rem, 16px base)

| Token | Size | Line | Weight | Use |
|---|---|---|---|---|
| `display` | 3.0 (48px) | 1.05 | 700 | Landing hero |
| `h1` | 2.0 (32px) | 1.1 | 700 | Page title |
| `h2` | 1.5 (24px) | 1.2 | 600 | Section |
| `h3` | 1.25 (20px) | 1.3 | 600 | Card title |
| `body` | 1.0 (16px) | 1.5 | 400 | Default |
| `small` | 0.875 (14px) | 1.45 | 400 | Secondary |
| `caption` | 0.75 (12px) | 1.4 | 500 | Labels, badges (uppercase, letter-spacing 0.04em) |

Headings use `text-wrap: balance`. Body max line length ~70ch.

---

## 4. Spacing, Radius, Elevation

- **Spacing scale (px):** 4, 8, 12, 16, 24, 32, 48, 64 (Tailwind `1,2,3,4,6,8,12,16`). Use scale only.
- **Container gutter:** min 16px at all widths; content max-width 1200px.
- **Radius:** `sm` 6px (inputs, chips), `md` 10px (cards), `lg` 16px (modals/large cards), `full` 9999px (pills/avatars).
- **Elevation (dark-first, subtle):**
  - `e0` none (flush surfaces)
  - `e1` `0 1px 2px rgba(0,0,0,.25)` (cards)
  - `e2` `0 4px 12px rgba(0,0,0,.30)` (dropdowns, modals)
  - No colored glows except the focus ring.

---

## 5. Core Components & States

Every interactive component defines: **default, hover, active, focus-visible, disabled, loading** (where applicable), plus **error** for inputs.

### 5.1 Button
| Variant | Default | Hover | Active | Disabled | Focus |
|---|---|---|---|---|---|
| Primary | bg `--accent`, text `--accent-contrast` | bg `--brand-500` | brightness 95% | opacity .5, no pointer | 2px `--ring` offset 2px |
| Secondary | bg `--surface`, border `--border`, text `--text` | bg `--surface-2` | — | opacity .5 | ring |
| Ghost | transparent, text `--text-muted` | text `--text`, bg `--surface-2` | — | opacity .5 | ring |
| Danger | bg `--danger`, white text | darken 6% | — | opacity .5 | ring |
- Loading: spinner replaces label, width preserved, `aria-busy=true`, disabled.
- Min hit target 40px height.

### 5.2 Input / Textarea / Select
- Default: bg `--surface`, border `--border`, radius `sm`, text `--text`, placeholder `--text-muted`.
- Focus: border `--accent`, ring 2px `--ring`.
- Error: border `--danger`, helper text `--danger` below, `aria-invalid=true`.
- Disabled: bg `--surface-2`, opacity .6.
- Label always present (visible or `sr-only`).

### 5.3 Score Chip / Badge
- Score chip color by band: 0–49 `--danger` tint, 50–69 `--warn` tint, 70–100 `--success` tint. Text = darker shade of band. Always show the number, never color alone (accessibility).
- Platform badge: neutral surface-2 bg, `caption` text, platform name.
- Status badge (proposal): draft (muted), used (info), won (success), lost (danger), no-response (warn).

### 5.4 Card
- bg `--surface`, border `--border`, radius `md`, padding 16–24, elevation `e1`.
- Hover (clickable): border `--accent` at 40% + cursor pointer.

### 5.5 Modal / Dialog
- Overlay `rgba(0,0,0,.5)`; panel `--surface`, radius `lg`, elevation `e2`, max-width 480px, trap focus, Esc to close, restore focus on close. Confirm dialogs for destructive/credit-consuming repeat actions.

### 5.6 Toast
- Bottom-right stack, auto-dismiss 4s (errors: manual dismiss). Variants: success, error, info. Never use toast for critical blocking errors (use inline).

### 5.7 Skeleton
- `--surface-2` block with subtle shimmer; matches final element dimensions.

### 5.8 Empty state
- Centered: small icon, `h3` title, `small` muted description, one primary button.

### 5.9 Nav
- App shell: left sidebar (Feed, Proposals, Dashboard, Settings) collapsible < 900px to top bar; top bar shows credits pill + user menu. Active route: accent left-border + accent text.

---

## 6. Charts (Dashboard)

- Library: Recharts. Palette: series use `--accent`, `--info`, `--warn`, `--ink-400` in that order. Won = `--success`, Lost = `--danger`, No-response = `--warn`.
- No gridline clutter: horizontal gridlines only, `--border` at low opacity. Axis labels `caption` `--text-muted`. Tooltips use `--surface` + `e2`. Never rely on color alone — label series directly or in legend.

---

## 7. Accessibility (non-negotiable)

- Contrast ≥ 4.5:1 body, ≥ 3:1 large text/UI.
- All interactive elements keyboard-reachable; visible `focus-visible` ring (never `outline:none` without replacement).
- Score/status never communicated by color alone.
- Images/icons have `alt`/`aria-label`. Forms fully labeled. Respect `prefers-reduced-motion` (disable shimmer/transitions).

---

## 8. Responsive Breakpoints

| Name | Width | Behavior |
|---|---|---|
| mobile | < 640 | single column; sidebar → bottom/hamburger; filters in a drawer |
| tablet | 640–1024 | 2-col feed; collapsible sidebar |
| desktop | > 1024 | filter rail + feed + detail |

No horizontal page scroll at any width. Tables/JSON blocks scroll inside their own container.
