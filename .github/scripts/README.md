# Claude PR automation

This directory holds the scripts and workflows that automate first-pass PR review for Tesserae V6.

## Files

- `claude_pr_review.py` — Calls the Anthropic API with a PR's diff, file list, and metadata. Writes a markdown review to a file. Used by `.github/workflows/claude-pr-review.yml`.
- `claude_pr_safe_check.py` — Classifies a PR by safety pattern (`safe:docs`, `safe:typo`, `safe:dep-patch`, or `unsafe:<reason>`). Used by `.github/workflows/claude-pr-auto-approve.yml`.

## Workflows

- `.github/workflows/claude-pr-review.yml` — Runs on every PR open and update. Posts a Claude-authored first-pass review as a comment. Always runs; does not gate the merge.
- `.github/workflows/claude-pr-auto-approve.yml` — Runs on every PR open and update. Classifies the PR. If the classification is one of the safe patterns AND the repository variable `CLAUDE_AUTO_APPROVE_ENABLED` is `true`, posts a GitHub "APPROVE" review on Neil's behalf. **Never auto-merges.** The merge button stays with Neil.

## Setup

1. **Add the Anthropic API key as a repository secret.**
   ```
   gh secret set ANTHROPIC_API_KEY --repo tesserae/tesserae-v6
   ```
   Paste the API key from `console.anthropic.com` when prompted.

2. **(Optional) Turn on auto-approve.** Detection always runs and posts the classifier verdict as a comment. To actually have the workflow approve safe-pattern PRs:
   ```
   gh variable set CLAUDE_AUTO_APPROVE_ENABLED --body "true" --repo tesserae/tesserae-v6
   ```
   Default is off, by design. Watch a few weeks of detection-only verdicts first.

## Cost model

Each first-pass review costs roughly $0.01 to $0.05 against the Anthropic API account, depending on diff size. The workflow uses Claude Sonnet 4.5 with a 60K-character diff budget. For Tesserae's volume (a few PRs per week), monthly cost is in the low single dollars.

The safety classifier is rule-based Python with no API calls and no cost.

## Safety properties

- The review workflow only posts comments. It cannot push code, merge PRs, or change branch protection.
- The auto-approve workflow posts comments and (when enabled) a GitHub APPROVE review. It does not merge.
- Both workflows skip draft PRs.
- Both workflows have `permissions: contents:read, pull-requests:write` and nothing else.
- The `ANTHROPIC_API_KEY` is only readable inside the workflow's execution; it is not exposed in the comment, in logs (it is masked by Actions), or to forks (workflows on forked PRs do not get repo secrets by default).
