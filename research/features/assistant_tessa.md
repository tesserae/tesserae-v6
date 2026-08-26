# Tessa, the assistant

**Live since 2026-08-25.** A research assistant that runs searches against this
corpus and reports what came back. Not a chatbot with opinions about classical
literature, and not a substitute for reading.

Runs on a model hosted on this server (Qwen3-30B-A3B under llama.cpp, systemd
unit `tesserae-assistant`, port 8081), so nothing a reader asks leaves the
machine.

---

## What she does

- Finds where a word or phrase occurs and **lists the actual lines**.
- Says what the corpus holds in a language or by an author.
- Reports **inflected variants unprompted**. An exact search for *arma virumque*
  misses Eobanus entirely; he has the phrase 21 times in other cases. She says
  so and offers them.
- Follows up: "what about Eobanus?" keeps the thread.
- Explains how the site works, including connecting an outside AI.

## Architecture

`backend/assistant/`:

| File | Role |
|---|---|
| `agent.py` | the loop: seed, fast paths, chooser, compute facts, narrate, guard |
| `searches.py` | the searches she may run, over loopback HTTPS |
| `model.py` | model client and the guardrails |
| `prompts.py` | system prompts, built per request |
| `router.py` | deterministic routing for meta and advice questions |

Searches are called over loopback rather than imported, so she cannot drift from
what the site actually does, and a hung search takes an HTTP timeout rather than
the request thread. Deliberately **no fusion comparison of two large works**:
that takes minutes and a model that can start one will.

---

## The failures, which are the useful part

Every one was reported by NC from the live site.

**Recited tool lists instead of searching.** When no search produced facts, the
question fell through to the old guide path, which has no corpus access and can
only name tools. Asked "are you sure it's not in Eobanus?" she replied "use
string_search…". Removed for corpus questions: if nothing else applies she lists
holdings and answers from those.

**No conversation memory.** Each question arrived alone, so "is it in Eobanus?"
had no idea what "it" was. History now travels from the page, with a
session-cookie fallback so a stale browser still works.

**History threaded into `answer()` but not `answer_stream()`.** Every test called
`answer()` directly; the browser uses the stream. The fix passed cleanly and was
dead in the page. Tests now go through the HTTP endpoint.

**Reasoned from a sample to the corpus, three times.** Told the corpus holds
1,826 Latin works and shown 20 authors, she reported Statius and the Aeneid
absent. The corpus holds 23 Statius entries and 14 Aeneid entries. Fixed at two
levels: a **census** of per-language counts in front of every answer, and
**named works resolved in code** against the real listing before the model sees
anything.

**Fabricated primary text, twice.**

1. Asked for the Eobanus instances, she produced twelve citations each quoting
   the Aeneid's opening line. The 21 real lines had been retrieved correctly and
   then discarded by a 3,000-character cap on the fact block before the model saw
   them. Fixed: the cap holds a listing answer, facts carrying real lines are
   ordered first, and truncation announces itself.
2. Padding a list to a stated count of twelve, she invented loci (Martial
   1.11.1, Salutati 1.1) and pasted Vergil's line under each.

**She would not list instances because the prompt forbade it.** The narration
prompt ended "no headings, no lists", so listing was the one thing she could not
do when asked to list. And the facts carried the number 21 with no lines: a
count is not an instance.

---

## Guardrails

Every answer is checked before display:

| Check | What it enforces |
|---|---|
| references | citations must come from a search that ran |
| numbers | figures must appear in the results **or in the question** |
| quotes supported | quoted text must appear in the results |
| **quotes paired** | quoted text must match the citation it is printed under |

The pairing check exists because the third was not enough: it asks whether text
exists *somewhere* in the results, and Vergil's line does, so quoting it under
Martial passed.

**Failures are appended to the answer**, where the reader sees them, not written
to a log. Detecting a fabricated citation and printing it unannotated is worse
than not checking, because it lends the invention the authority of a tool that
claims to verify.

---

## Design rules learned

- **Deterministic beats prompt.** The variant offer was requested in the prompt
  all day; the model complied on short answers and forgot on long ones, which is
  exactly when it matters. It is now computed in code.
- **Never let a sample look like the whole.** Put real counts in front of the
  model on every answer.
- **"Cannot ask" and "found nothing" are different answers**, and only one means
  the corpus lacks the subject.

---

## Open

- Answers are long. A listing is right; the prose around it could be shorter.
- Highlighting of matched terms shipped 2026-08-25; worth checking it reads well
  on a phone.
