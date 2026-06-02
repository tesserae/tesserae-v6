# PR Automation Workflow

**Status:** Active as of 2026-06-02.
**Maintainer:** Neil Coffee.
**Files:** `.github/workflows/claude-pr-review.yml`, `.github/workflows/claude-pr-auto-approve.yml`, `.github/scripts/claude_pr_review.py`, `.github/scripts/claude_pr_safe_check.py`.

This document describes the three-layer automation that handles incoming pull requests for the Tesserae V6 repository. The intent is to remove Neil as the first responder to every PR while keeping the merge decision human.

## The three layers

### Layer 1: Daily PR-triage routine

A scheduled Claude Code routine runs at 12:00 UTC (8 am EDT) every day. It surveys all open pull requests on the repository, drafts a short review of each one (one-paragraph summary, risk classification, two or three concrete items to verify, merge recommendation), and emails the digest to `ncoffee@buffalo.edu` via the Gmail connector. The email is markdown-formatted with one section per open PR, plus a one-line top summary. Each PR section links straight to the PR.

If there are no open PRs that morning, the routine sends a one-line email saying so. The routine never posts comments on GitHub. It is a private digest for the maintainer.

The routine ID is `trig_012q3Nub3wrC17G2pBv6mZeS`. It can be paused, retimed, or edited at https://claude.ai/code/routines/trig_012q3Nub3wrC17G2pBv6mZeS or via the `/schedule` command in Claude Code.

### Layer 2: Instant first-pass review

A GitHub Actions workflow at `.github/workflows/claude-pr-review.yml` runs on every pull-request open and update event. It fetches the PR diff via the `gh` CLI, hands the diff plus PR metadata to a Python script (`.github/scripts/claude_pr_review.py`), and the script calls the Anthropic API with Claude Sonnet 4.5 to generate a code review. The review is posted back as a PR comment within roughly two minutes of the PR event.

The review follows a fixed format. A one-sentence summary of what the PR does. A risk classification (Low, Medium, or High) with the file paths that drive the classification. Two or three concrete things to verify, each with a `file.py:line` reference. A merge recommendation: ready to merge, request changes, or needs Neil's judgment.

The review is informational. It does not approve the PR, does not request changes via the GitHub review mechanism, and does not merge. The footer notes that the review is automated and Neil approves the actual merge.

Draft pull requests are skipped. Forked-repository pull requests have access to repository secrets disabled by default at the platform level, so the workflow simply does not run on them; this is GitHub's standard fork-secret policy.

### Layer 3: Safety classifier and optional auto-approve

A second GitHub Actions workflow at `.github/workflows/claude-pr-auto-approve.yml` runs the same triggers. It calls a rule-based Python script (`.github/scripts/claude_pr_safe_check.py`) to classify the PR by safety pattern. The classifier emits one of these verdicts:

- `safe:docs` if all changed files are documentation: extensions `.md`, `.txt`, `.rst`, or filenames `LICENSE`, `AUTHORS`, `CONTRIBUTORS`, `NOTICE`.
- `safe:typo` if at most two files are changed and the total additions plus deletions are four lines or fewer, and no high-risk path is touched.
- `safe:dep-patch` if only `requirements.txt`, `package.json`, or `package-lock.json` are touched and every version change is a patch-level semver bump.
- `unsafe:touches-high-risk-path:<path>` if any file under the high-risk list (see below) is touched.
- `unsafe:requires-human-review` for anything else.

The verdict is posted as a one-line PR comment.

If the repository variable `CLAUDE_AUTO_APPROVE_ENABLED` is set to `true` AND the verdict starts with `safe:`, the workflow then posts a GitHub APPROVE review on Neil's behalf. The PR shows a green review checkmark. The workflow still does not merge. The merge button stays with Neil.

The default is `CLAUDE_AUTO_APPROVE_ENABLED` unset, which means the classifier posts its verdict but never approves. To turn auto-approve on, run:

```
gh variable set CLAUDE_AUTO_APPROVE_ENABLED --body "true" --repo tesserae/tesserae-v6
```

To turn it back off, set the variable to any value other than `true`, or delete it.

## High-risk paths

The safety classifier treats any change to these paths as `unsafe:touches-high-risk-path`. These paths are the search scoring core, the matching code, the dictionary, the tokenization pipeline, the main Flask app entry point, and the user-facing search blueprints:

- `backend/fusion.py`
- `backend/scorer.py`
- `backend/matcher.py`
- `backend/synonym_dict.py`
- `backend/text_processor.py`
- `backend/app.py`
- `backend/blueprints/admin.py`
- `backend/blueprints/search.py`
- `backend/blueprints/fusion.py`
- `backend/blueprints/hapax.py`

The full list lives in `.github/scripts/claude_pr_safe_check.py` and can be edited there.

## Secrets and configuration

One repository secret is required:

- `ANTHROPIC_API_KEY` — the Anthropic API key from `console.anthropic.com`. Set via `gh secret set ANTHROPIC_API_KEY --repo tesserae/tesserae-v6` or at Settings > Secrets and variables > Actions. Without this, the first-pass review workflow fails at the API call step. The safety classifier workflow continues to work.

One repository variable is optional:

- `CLAUDE_AUTO_APPROVE_ENABLED` — set to the literal string `true` to enable auto-approval of safe-pattern PRs. Default is unset (auto-approve off, classifier verdicts still posted).

## Cost

Each first-pass review costs roughly $0.01 to $0.05 against the Anthropic API account, depending on diff size. The workflow uses Claude Sonnet 4.5 with a 60K-character diff budget. For Tesserae's typical volume, monthly cost is in the low single dollars. The safety classifier is rule-based Python with no API calls and no cost.

Spend appears on the monthly statement at `console.anthropic.com`. The same API key supports any other Tesserae work that calls Claude (the weight-optimization scripts, the planned LLM rerank work in `research/plans/2026-05-30_v6_next_steps_rerank_and_alternatives.md`).

## Safety properties

- The review workflow only posts comments. It cannot push code, merge PRs, or change branch protection or secrets.
- The auto-approve workflow posts comments and (when enabled) a GitHub APPROVE review. It does not merge.
- Both workflows skip draft PRs.
- Both workflows have `permissions: contents:read, pull-requests:write` and nothing else.
- The `ANTHROPIC_API_KEY` is masked in workflow logs and is not exposed to forked-PR workflows.
- The classifier is conservative by design. Any pattern it cannot confidently match returns `unsafe:requires-human-review`, which leaves the PR for Neil.

## What this changes about the contribution loop

Before: a volunteer opened a PR, then messaged Neil on Slack to ask for review. Review timing depended on Neil's availability.

After: a volunteer opens a PR and within roughly two minutes sees a Claude review comment and a safety verdict. The volunteer can address any pointed concerns immediately, before Neil ever looks at the PR. When Neil does come to the PR, he has the Claude review, the safety verdict, and the volunteer's response already in front of him. His decision is closer to "merge or not" than "what is this PR."

The volunteer-facing contract is unchanged. Neil is still the merge gate. Claude's review is a first pass, not a final approval. The volunteer should still expect human review on anything substantive.

## Editing or disabling the workflows

To pause either GitHub Actions workflow: rename the file or set `if: false` on the top-level `jobs:` block. To pause the daily routine: visit the routine page at https://claude.ai/code/routines/trig_012q3Nub3wrC17G2pBv6mZeS or use `/schedule` in Claude Code and disable it.

To edit Claude's review prompt: see the `build_prompt()` function in `.github/scripts/claude_pr_review.py`. The Tesserae-specific context (which paths are high-risk, what the project is) lives there.

To add a safe pattern: edit `.github/scripts/claude_pr_safe_check.py`. Add a detector function, add the verdict string, document the criterion at the top.

To change the daily digest recipient or frequency: update the routine via the API or web UI.
