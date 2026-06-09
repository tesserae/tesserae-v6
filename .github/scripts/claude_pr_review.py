#!/usr/bin/env python3
"""Call Claude to review a PR and write a markdown review to stdout.

Inputs come from environment variables (set by the GitHub Actions workflow):
  ANTHROPIC_API_KEY     - Anthropic API key (GitHub Actions secret)
  PR_NUMBER             - PR number being reviewed
  PR_TITLE              - PR title
  PR_AUTHOR             - PR author's GitHub username
  PR_BODY               - PR body / description (may be empty)
  PR_BASE               - base branch name (usually "main")
  PR_HEAD               - head branch name
  PR_FILES_JSON         - JSON list of changed files with additions/deletions
  PR_DIFF_PATH          - path to file containing the unified diff

The script writes the review markdown to PR_REVIEW_OUT path.

The review is a short, factual code review aligned with the Tesserae V6 review
style. It is NOT a merge approval. It is a digest for a human reviewer.
"""
import json
import os
import sys
import urllib.request
import urllib.error

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-fable-5"
MAX_TOKENS = 2000
DIFF_TOKEN_BUDGET_CHARS = 60_000  # ~15K tokens, leaves headroom for prompt + reply


def truncate_diff(diff: str, budget: int) -> str:
    """Truncate a unified diff to the given character budget, preferring to cut at file
    boundaries (lines starting with 'diff --git') so the review still sees whole files."""
    if len(diff) <= budget:
        return diff
    head = diff[:budget]
    last_file_boundary = head.rfind("\ndiff --git")
    if last_file_boundary > budget // 2:
        truncated = head[:last_file_boundary]
        omitted = diff[last_file_boundary:]
        return truncated + (
            f"\n\n[diff truncated after {len(truncated):,} chars; "
            f"{len(omitted):,} chars omitted across additional files]\n"
        )
    return head + "\n\n[diff truncated]\n"


def build_prompt(pr_number, pr_title, pr_author, pr_body, pr_files, diff) -> str:
    files_summary = "\n".join(
        f"  - {f['path']} (+{f['additions']}/-{f['deletions']})"
        for f in pr_files[:30]
    )
    if len(pr_files) > 30:
        files_summary += f"\n  - ... and {len(pr_files) - 30} more files"

    return f"""You are doing a first-pass code review of a pull request to the Tesserae V6 repository on behalf of the maintainer Neil Coffee. Your review is a digest that helps Neil decide whether to merge, request changes, or look more carefully. You are not the final approver.

# Tesserae V6 context

Tesserae V6 is a multi-channel intertextual search system for classical languages (Latin, Greek, English, Coptic, Arabic, Persian; Hebrew and Urdu in progress). The backend is Flask (Python) under `backend/`. The frontend is React + Vite under `client/`, built to `dist/`. Production runs on Apache + mod_wsgi at tesserae.caset.buffalo.edu.

# Risk areas to flag explicitly

- **Highest risk** if touched: `backend/fusion.py` and `backend/scorer.py` (search scoring), `backend/matcher.py` (matching channels), `backend/synonym_dict.py` (Greek-Latin dictionary), `backend/text_processor.py` (tokenization, lemmatization), database migrations, anything involving auth or admin login.
- **Medium risk**: `backend/blueprints/admin.py`, `client/src/components/admin/`, anything that adds a new Python dependency in `requirements.txt` or `package.json`.
- **Low risk**: documentation (`*.md`), text-source metadata, the contents of `texts/`, benchmark files under `evaluation/`.

# What to look for

1. **Scope.** Is the diff focused on one change, or sprawling?
2. **Untouched expectations.** Are the right paths touched and are out-of-scope paths left alone?
3. **Risk classification.** Using the table above, what is the overall risk?
4. **Specific things Neil should verify.** Two or three concrete items, with file:line references.
5. **Cleanliness.** Any obvious code-quality issues, missing tests, dead code, or commented-out debug statements? Any chance of conflict with the production-deploy workflow (frontend rebuild, WSGI touch)?
6. **Merge recommendation.** One of: ready to merge, request changes, needs Neil's judgment.

# PR being reviewed

- **Number:** #{pr_number}
- **Title:** {pr_title}
- **Author:** @{pr_author}
- **Body:**

{pr_body or '(no body)'}

# Files changed

{files_summary or '(no files)'}

# Unified diff

```diff
{diff}
```

# Output format

Write a single markdown comment, structured as follows. No preamble, no signoff.

```markdown
**Claude PR review (automated first pass)**

**Summary.** One sentence on what the PR does.

**Risk classification.** Low / Medium / High, with the path(s) that drive the classification.

**Things to check.**
- file.py:line — specific thing to verify.
- file.py:line — another.

**Recommendation.** Ready to merge / Request changes (and what changes) / Needs Neil's judgment (and why).

_This is an automated review. Neil reviews and approves the actual merge._
```
"""


def call_anthropic(api_key: str, prompt: str) -> str:
    body = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Anthropic API error {e.code}: {body}")

    parts = data.get("content", [])
    text_blocks = [p.get("text", "") for p in parts if p.get("type") == "text"]
    if not text_blocks:
        raise SystemExit(f"Unexpected Anthropic response: {json.dumps(data)[:500]}")
    return "\n".join(text_blocks).strip()


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set")

    pr_number = os.environ.get("PR_NUMBER", "?")
    pr_title = os.environ.get("PR_TITLE", "")
    pr_author = os.environ.get("PR_AUTHOR", "")
    pr_body = os.environ.get("PR_BODY", "")
    pr_diff_path = os.environ.get("PR_DIFF_PATH", "/tmp/pr.diff")
    pr_files_json = os.environ.get("PR_FILES_JSON", "[]")
    out_path = os.environ.get("PR_REVIEW_OUT", "/tmp/review.md")

    pr_files = json.loads(pr_files_json)

    with open(pr_diff_path) as f:
        diff = truncate_diff(f.read(), DIFF_TOKEN_BUDGET_CHARS)

    prompt = build_prompt(pr_number, pr_title, pr_author, pr_body, pr_files, diff)
    review = call_anthropic(api_key, prompt)

    with open(out_path, "w") as f:
        f.write(review)
    print(f"Wrote review to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
