# Thread dossier — Tesserae-through-your-AI (open API access + AI orchestration)

**Status:** Guide LIVE. Proof-of-concept done. Crash-risk assessed. Feature-request-via-AI endpoint APPROVED to build (gated PR), pending a GitHub token.
**Last updated:** 2026-08-10
**Owner:** Neil Coffee / Claude · **Prompted by:** Neil Bernstein (Neil B.)
**One-line:** Let a user's *own* AI assistant drive Tesserae's open API through a full find-and-interpret research pipeline — so Tesserae supplies free, auditable search and the user's AI supplies the (bring-your-own-cost) interpretation.

---

## 1. Genealogy — how this arose and the reasoning

**Origin (Neil B.'s question, relayed by NC).**
> "Could an AI agent go through multiple steps — compare one text against another, select high-ranked parallels, then compare them across the poetic corpus for uniqueness and serve up an interpretation? Tesserae is already better than MQDQ in serving up the good stuff first, but MQDQ has the benefit of displaying the poetic corpus in its results."

NC's hard constraint: **he cannot pay for AI/Claude tokens for every user.** That rules out Tesserae hosting the AI itself and points to **bring-your-own-AI**: the user brings their own assistant, Tesserae exposes the search.

**Two candidate routes, one dropped.**
1. *(Dropped)* A manual "research dossier / paste-brief" the user copies into an AI by hand. Superseded by route 2 and explicitly retired by NC.
2. *(Pursued)* Give the user's AI the **API** plus a **context prompt** so it can operate Tesserae knowledgeably and autonomously.

**Feasibility findings that made route 2 viable.**
- Tesserae's search endpoints are **open — no key, no login.** A server-side AI agent can call them directly.
- **CORS is irrelevant here:** it only governs browser-origin requests; a server-side agent isn't affected.
- Apache routes **only `/api` to Flask**; everything else is static. So the API is a clean, self-contained surface to document.
- Therefore: a well-written context prompt can turn any web-capable AI into a competent Tesserae operator at **zero cost to Tesserae.**

**Design principles NC set for the guide (these are the intellectual core, worth quoting in any write-up).**
1. **Teach the whole toolbox, not just Neil B.'s route.** Neil B. knows Latin epic; he does *not* know Tesserae's full feature set. The guide documents all six search types + per-language coverage, so the AI can recommend the right tool.
2. **Educate the user non-intrusively.** Follow the user's lead; surface a relevant capability briefly, then defer. One suggestion, not a sales pitch.
3. **Hold a hard line between Tesserae's results and the AI's own products.** This is the ethical spine: *Tesserae output is auditable* (transparent, reproducible, adjustable — we can inspect and modify the whole process), whereas *the AI's downstream interpretation is a black box unless the user makes it auditable.* The guide instructs the AI to label the two, never let inference masquerade as a Tesserae finding, and gently encourage the user to preserve that distinction in publication (cite Tesserae for the parallels/rarity; present analysis as AI-assisted-and-author-checked). It also recommends the user keep their own side auditable — log the exact queries/results, and keep a repository of the secondary material the AI drew on.

**Why the provenance principle matters (for articles/talks).** It reframes Tesserae's transparency as a *methodological advantage in the age of AI*: the search layer is examinable and reproducible; the interpretive layer, if left to a black-box model, is not — so the responsible workflow keeps them distinct and makes both auditable. This is a defensible scholarly stance and a selling point.

**The feature-request sub-thread (how a user's AI asks us for more).**
NC asked: if a user's AI hits a wall (wants a feature/language/text we don't have), can the *protocol itself* let the AI file that request in the most actionable form for us?
- Decided the AI captures a **fixed schema** (type, title, problem, desired, example, tried, **auto-captured search context**, optional contact) and **requires explicit user sign-off before sending anything** (NC, 2026-08-10: the AI must *not* auto-send — the user confirms every submission). The auto-captured context is the differentiator — the request arrives with its own reproduction case.
- Submission channel: users mostly **won't have GitHub accounts**, so a prefilled-GitHub-issue-URL route was rejected. NC chose **auto-file to GitHub Issues** (server-side) so requests land in the **dev team's** actual triage workflow.
- **Discovery that reshaped the build:** Tesserae *already has* a private feedback system — `POST /api/feedback` (stores to a `feedback` table, emails the team via local Postfix, reviewable in the Admin panel) and a structured `text_requests` corpus-addition pipeline with an approval workflow. So intake is not built from scratch.
- **Refined, approved design:** reuse the existing intake; for actionable types (`feature`/`language`/`bug`) also **auto-file a labeled GitHub issue** (`from-ai-protocol` + type), **with the user's email stripped from the public issue** (kept only in the DB + the private notification email); route corpus-addition requests to the existing `text_requests` pipeline; gate GitHub behind a token + kill-switch so that, absent the token, it degrades to the existing private path. NC's instruction: *"build it as a gated PR — strip the email."*

---

## 2. Current state — everything needed to rebuild

### 2a. The guide (DONE, live)
- **Source (Markdown):** `scratchpad/tesserae_api_guide.md` (working copy; regenerate the HTML from this).
- **Repo copy (committed):** `static/downloads/ai-guide.html` — committed to `main` as **`76cd7ef`** ("Add AI-assistant API guide page").
- **Served copy (live):** `/var/www/tesseraev6_flask/public_data/ai-guide.html`.
- **Live URL:** **https://tesserae.caset.buffalo.edu/tesserae-data/ai-guide.html**
- **claude.ai artifact (review view):** https://claude.ai/code/artifact/edfb170e-e019-4fc8-8c8d-84fbcde3b42e
- **Design:** self-contained HTML, site identity (amber/gold, Crimson Pro serif, Noto Sans), one-click "Copy the full guide" (copies a plain-text version embedded in a `<script type="text/plain" id="guide-src">`). Sections: how-to-behave · what Tesserae is · the API · full toolbox table · request shapes · flagship workflow · **Provenance** · keep-your-side-auditable · caveats.

### 2b. Hosting architecture (learned the hard way — see also memory `feedback_production_deploy_frontend.md`)
- Prod Apache vhost `vhost-tess-new.conf` (ServerName `tesserae.caset.buffalo.edu`) routes **only `/api` → Flask** (`WSGIScriptAlias /api …/tesseraev6_flask.wsgi`). Everything else served by Apache from `DocumentRoot /var/www/tess-new` → symlink → `…/tesseraev6_flask/dist`, with an SPA rewrite (non-`/api/`,`/tesserae-data/`,`/blog/` and not-a-real-file → `/index.html`).
- Consequences: (1) the Flask `/static/downloads/` `before_request` hook is **dead for web traffic** (those URLs never reach Flask → SPA fallback); (2) a raw file in `dist/` would serve but gets wiped by the `git checkout -- dist/` + `npm run build` deploy step.
- **Durable static hosting = the Apache alias `/tesserae-data` → `/var/www/tesseraev6_flask/public_data`** (writable by ncoffee:tessdev, correct content-types, outside `dist/`, not git-tracked — like the index tarballs there). That's why the guide lives at `/tesserae-data/ai-guide.html`.
- A prettier URL (e.g. `/ai-guide`) or fixing `/static/downloads/*` needs an Apache Alias/RewriteRule change (Chris/root).

### 2c. Proof-of-concept (DONE — full pipeline run live against the API)
- **Comparison:** `POST /api/search-fusion` `source=vergil.aeneid.part.1.tess`, `target=lucan.bellum_civile.part.1.tess`, `language=la` → SSE stream (raw saved at `scratchpad/poc_fusion.sse`), 500 ranked pairs.
- **Top parallels (sorted by `fused_score`):** #1 Aen 1.146 *syrtis…aequor* × BC 1.499 *Syrtibus…aequor* (score 17.5, 4 ch); #2 *Hesperiam…arva* × *Hesperia…arvis* (16.5, 4 ch); #3 Aen 1.103 ***fluctusque ad sidera** tollit* × BC 1.416 ***fluctusque ad sidera** ducat* (9.6, **7 ch** incl. quotation).
- **Corpus-uniqueness step** (`POST /api/line-search`, whole corpus): `aequor+syrtis` ≈ 9 lines; `arvum+hesperia` ≈ 8; `fluctusque ad sidera` ≈ **0 elsewhere** (near-unique Vergilian phrase Lucan reuses almost verbatim). ⇒ the entire search→select→uniqueness pipeline works end-to-end via the open API, at zero AI cost — a publishable observation produced autonomously.

### 2d. Crash / OOM / wait-time assessment (DONE)
- **Usage (search_logs, ~190 days):** 2,203 searches, ≈11.6/day avg; last 30 days ≈8/day. Busiest human hour = 66. The access-log "228 search-POSTs/minute" spike is an automated midnight benchmark, not concurrent users.
- **Capacity:** 62 GB RAM (≈54 free) + 23 GB swap. Concurrency gate (PR #141): **max 8 concurrent, queue when free RAM < 25 GB, 300 s queue timeout.**
- **Verdict — OOM/crash risk LOW:** the API path uses the *same* endpoints → the *same* gate → **cannot bypass** the OOM protection; excess load **queues, not crashes**. Neil B.'s pipeline is **1 heavy fusion + many *light* index lookups**; the light lookups barely touch the gate. Realistic failure mode under heavy concurrent use = **wait/queue time**, which degrades gracefully. If API/AI usage grows: add an API-specific rate-limit or lane; not needed now.

### 2e. Feature-request-via-AI endpoint (APPROVED — NOT YET BUILT)
- **Existing infra to reuse:** `POST /api/feedback` `{name,email,type,message}` → `feedback` table (id/status/created_at/admin_notes/responded_by) + `notify_feedback` email (SMTP `localhost:25`, recipients from the `settings` table) + Admin-panel review (`/api/admin/feedback` GET/PUT). Separate `text_requests` table + approval pipeline for corpus additions.
- **To build (gated PR):**
  1. On feedback of type `feature`/`language`/`bug`: after the existing DB insert + email, **create a GitHub issue** in `tesserae/tesserae-v6` via a bot token — labeled `from-ai-protocol` + the type — **omitting the user's email** (email stays in DB + notification only).
  2. Accept the richer AI schema (problem/desired/example/tried/**context**) — pack it into the issue body; keep contact private.
  3. Route corpus/text-addition requests to the existing `text_requests` flow (curatorial approval), not GitHub.
  4. **Gate:** `GITHUB_FEEDBACK_TOKEN` + `GITHUB_FEEDBACK_REPO=tesserae/tesserae-v6` + a kill-switch env. **If token absent → behave exactly as the existing private path** (safe to merge before provisioning).
  5. Anti-spam: rate-limit, payload caps, required fields, `from-ai-protocol` label for bulk filtering.
  6. Update the guide with a "Requesting a feature/language/text" section: the AI drafts the schema, **warns the user the description becomes a public GitHub issue**, confirms, then submits; email optional and kept private.
- **The one external dependency (NC/Chris):** a **fine-grained GitHub PAT** (ideally from a shared/bot account, not NC's personal account), scoped to **only `tesserae/tesserae-v6`, Issues: read/write**, placed in prod `.env` as `GITHUB_FEEDBACK_TOKEN` (+ `GITHUB_FEEDBACK_REPO`).

### 2f. Open API reference (as used by the guide)
`GET /api/languages` · `GET /api/texts?language=` · `POST /api/search-fusion` (SSE) · `POST /api/line-search` · `POST /api/wildcard-search` · `POST /api/hapax-search` · `POST /api/rare-bigram-search`. All open, no auth.

---

## 3. How to resume / next steps
1. **Build the gated feature-request PR** (2e) — approved; strip email; degrade-safe without the token.
2. **Provision the GitHub token** (NC/Chris) — the only blocker to activating GitHub auto-file.
3. **Add the guide to the Help page** (NC flagged this first, before the feature-request work): a "Guide for AI assistants →" link/section in Help or About — a minor `client/` change → build → deploy.
4. **Native connector — WANTED (NC, 2026-08-10), not optional:** make it native/easy for Claude and ChatGPT — an **OpenAPI spec → a ChatGPT Custom GPT / GPT Action**, and/or an **MCP server for Claude**, so users don't paste a prompt at all. Scope TBD; the pasteable guide is the interim.
5. **Corpus-uniqueness + corpus display on results** (the MQDQ gap Neil B. named) — separate build; the PoC shows the uniqueness half already works via `line-search`.

## 4. Related
- Sibling thread: `2026-08-10_adjustable-channel-weights_PR187.md` (the API's forthcoming `channel_weights`/`disabled_channels` params should be documented in the guide once #187 ships).
- Concurrency gate: PR #141 (`backend/concurrency_gate.py`), prod config `data/concurrency_config.json` (max 8 / 25 GB).
- Deploy/hosting gotchas: memory `feedback_production_deploy_frontend.md`.
