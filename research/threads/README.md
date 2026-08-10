# Research threads — living workstream dossiers

Each file here is a **living record of one workstream**, written so that (a) the current work state can be rebuilt from it, and (b) it doubles as a **genealogical record** — the origin, reasoning, decisions, and rejected alternatives — for future presentations and articles. Update the relevant dossier as a thread progresses; don't let detail live only in chat.

Each dossier has the same two-part spine: **§1 Genealogy** (why this exists, the thinking, the forks) and **§2 Current state** (exact commits/branches/PRs, files, endpoints, env, what's deployed vs. gated, how to resume).

## Active threads
| Thread | File | Status |
|---|---|---|
| User-adjustable channel weights & on/off (PR #187) | [2026-08-10_adjustable-channel-weights_PR187.md](2026-08-10_adjustable-channel-weights_PR187.md) | Draft PR, verified default-equivalent, awaiting preview decision |
| Tesserae-through-your-AI (open API + AI orchestration) | [2026-08-10_ai-api-access.md](2026-08-10_ai-api-access.md) | Guide live; PoC done; feature-request endpoint approved to build (needs GitHub token) |

## Consolidated work plan (as of 2026-08-10)

Four workstreams. Three active, one recommended for parking.

**1 — Adjustable weights & channel on/off (PR #187).** Draft PR, proven not to change anyone's default results. To finish: decide whether to preview on the live site, then rebase onto `main`, un-draft, merge, deploy. Open product question: keep the standalone single-channel search modes or retire them.

**2 — "Tesserae through your AI" guide.** Live at `/tesserae-data/ai-guide.html`. Remaining: (a) surface it with a link/section on the Help page (NC wanted this first); (b) once #187 ships, document its two new knobs in the guide; (c) **native connector (NC wants this):** OpenAPI → ChatGPT Custom GPT/Action and/or an MCP server for Claude, so users don't paste a prompt at all.

**3 — Feature/language requests via the AI channel (new gated PR).** Designed + approved, not built. To finish: build the gated PR (reuse the existing `/api/feedback` system + mirror actionable requests to GitHub Issues, user email stripped from the public issue); add a "how to request" section to the guide; NC/Chris provision one GitHub token to switch the GitHub half on.

**4 — MQDQ-style corpus display. RECOMMEND PARK.** The "show the poetic corpus in results" gap Neil B. named is largely already closed: the **corpus-wide search button** already runs a result's shared words across the whole corpus, and the AI guide uses the same capability (`line-search`) for its uniqueness step — the PoC did exactly this. The only thing MQDQ does that we don't is display those corpus hits *inline automatically* instead of on a click. That's a small optional polish, not a real gap. Park unless NC wants the inline auto-display.

**Recommended sequence:** (1) commit these dossiers → (2) build #3's gated PR (approved, self-contained, merges safely even before the token) → (3) add the guide link to the Help page (#2a) → (4) decide #187 preview and ship, then update the guide (#2b) → park #4.

## Conventions
- Filename: `YYYY-MM-DD_short-slug.md` (date the thread was first captured here).
- Keep the status line at the top current.
- Cross-link sibling threads at the bottom.
