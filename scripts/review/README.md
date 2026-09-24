# The review tools: catching what Neil catches

Neil's time on this project goes disproportionately into reviewing work that
should not have reached him. Reading back through the corrections, most of
them fall into three kinds, and all three are mechanical enough to check.

This directory is where those checks live. It is not a style guide and not a
second opinion on judgement. It is the set of things Neil has already said,
made into something that fails rather than something to remember.

**Point anyone here.** This is the durable home. It lives in the repository,
so it survives a machine, a session, a model and a context window, and
`CLAUDE.md` names it so a new session finds it without being told.

## Why it exists

Writing a rule down has repeatedly failed to prevent the rule being broken.
The clearest case: on 2026-09-22 Neil cut a piece of filler from an email
draft with "Don't give me the AI, 'and it is worth explaining, because it
shapes . . .' filler." The rule against exactly that had been written down
days earlier, read at the start of the session, and not applied.

The lesson is already recorded in the project's own memory, under the
heading that stated intentions do not persist and only tool choice does. A
check that runs is worth more than a rule that is read.

## What is here

### `prose_check.py`, built and in use

Checks a draft against Neil's writing rules before he sees it. Every rule
traces to a correction he actually made, and the explanation carries his
words, so a later reader can tell a rule from somebody's preference.

```
python3 scripts/review/prose_check.py draft.md
python3 scripts/review/prose_check.py --stdin < draft.txt
python3 scripts/review/prose_check.py --list      # the rules and their sources
```

It exits 1 when it finds something, so a hook or a script can stop on it.
`--warn-only` reports and exits 0.

It skips fenced code, inline code and URLs. A semicolon in a shell command is
not a writing problem, and flagging it would teach everyone to ignore the
tool.

Current rules: em dashes, semicolons, "surface" as a verb, clauses that
announce the next sentence, defining by negation, dropped subjects, hedges
that narrow nothing, engineering-blog register, and colons joining clauses.

**Adding a rule.** Only when Neil has actually made the correction. Put his
words in the rule's `why`, add the real sentence he objected to as a test,
and add a test proving ordinary prose still passes. A checker that cries
about normal writing gets switched off, and then it protects nothing.

### A claim check, not built

The second pattern. Three times on 2026-09-22 a claim reached Neil that had
not been verified at its source. A file said not to exist did exist. A
repository name came from the project's own notes rather than from GitHub.
"The metadata services" went into a draft when nobody had checked which
services the measurement covered. All three share one shape, which is
trusting a note instead of the thing itself.

What would help: before a draft states that a file, a repository, a number
or an interface exists, that claim gets checked against the source, and a
draft carrying an unverified claim is flagged.

### A consequences check for data operations, not built

The third pattern, and the one that costs the most work. A change to the
corpus has a tail that the change itself does not describe. The worked
example is the Archimedes rename of 2026-09-23: the pull request correctly
called for a Greek index rebuild, and the operation also needed the lemma
caches, the passage index, the word index and the Reader's margin cache,
none of which the pull request mentioned. That knowledge sits in
`docs/DATA_OPERATIONS.md` as prose.

What would help: a checklist keyed to what a change touches, so a corpus
rename asks about the passage index by itself.

## What this cannot do

It cannot make the judgements. Whether Poe belongs under Romantic, whether a
Greek edit is sound, whether a request to a librarian is worth making, what a
number means for the project. Those are the work. The point of the checks is
to stop wasting that judgement on catching mechanical mistakes.
