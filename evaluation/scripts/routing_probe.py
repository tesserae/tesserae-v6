"""What does Tessa think you asked?

NC, after the router sent a question about the site's search capabilities off to
search the corpus for "arma virumque": "We discussed earlier that the idea was
that the AI would do at least a little bit of thinking, but it seems now we're
having to hardcode every rule. What's the deal?"

The deal, measured: the router is 1,748 lines holding 130 literal phrases in 9
lists, and it decides by substring match. Three of those decisions are
judgments, not lookups:

    kind            is this about the SITE, or about the CORPUS, or is it a
                    request for holdings, or a description of a SUBJECT?
    carries         does it carry the previous turn's subject forward?
    subject         if so, what?

This file is ground truth for those three, so the replacement can be measured
rather than argued about. Every case is a question a reader would plausibly
type. `kind` and `carries` are what a careful person would say the question
means, which is exactly the standard the router has to meet.

WHY IT PROBES THE DECISION AND NOT THE ANSWER

guide_probe.py already measures the answer end to end and takes minutes per
run. This measures the branch taken, so it runs in milliseconds and can be used
while iterating. The end-to-end tests are what confirm the wiring afterwards;
this is not a substitute for them. Testing the wrong door is how the
conversation bug shipped in the first place, so `classify` must be the function
the router actually calls, not a copy of its logic.

    python evaluation/scripts/routing_probe.py            # score the router
    python evaluation/scripts/routing_probe.py --verbose  # and list every miss
"""
import argparse
import os
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT)

# A previous exchange about a phrase, for the follow-up cases.
PHRASE_HISTORY = [
    {'role': 'user', 'text': 'Where does the phrase "arma virumque" appear?'},
    {'role': 'assistant',
     'text': '"arma virumque" appears at Vergil, Aeneid 1.1, and is echoed by '
             'Ovid, Quintilian and Seneca.'},
]

# kind:
#   site     the Help page answers it; search nothing
#   corpus   a word or phrase to look for in the texts
#   theme    a described subject, for the passage index
#   holdings what the corpus contains
#   read     wants to read a text, not search it
PROBES = [
    # ---- about the site. NC's bug lived here; the list had no word for "site" ----
    {'q': "tell me about the site's search capabilities", 'kind': 'site', 'carries': False},
    {'q': 'what can this site search for?', 'kind': 'site', 'carries': False},
    {'q': 'what search types are there?', 'kind': 'site', 'carries': False},
    {'q': 'what are the different kinds of search?', 'kind': 'site', 'carries': False},
    {'q': 'what can you do?', 'kind': 'site', 'carries': False},
    {'q': 'what is fusion search?', 'kind': 'site', 'carries': False},
    {'q': 'what is theme search and when should I use it?', 'kind': 'site', 'carries': False},
    {'q': 'how is theme search different from line search?', 'kind': 'site', 'carries': False},
    {'q': 'what is the reader?', 'kind': 'site', 'carries': False},
    {'q': 'how do I export my results?', 'kind': 'site', 'carries': False},
    {'q': 'can I use this with ChatGPT?', 'kind': 'site', 'carries': False},
    {'q': 'how do I cite Tesserae?', 'kind': 'site', 'carries': False},
    {'q': 'what do the channels mean?', 'kind': 'site', 'carries': False},
    {'q': 'is there an API?', 'kind': 'site', 'carries': False},
    {'q': 'why did my search return nothing?', 'kind': 'site', 'carries': False},
    {'q': 'what languages does the site cover?', 'kind': 'site', 'carries': False},

    # ---- the same words, but about the corpus. These must NOT go to the guide ----
    {'q': 'where does furor appear?', 'kind': 'corpus', 'carries': False},
    {'q': 'find "arma virumque" in the corpus', 'kind': 'corpus', 'carries': False},
    {'q': 'which authors use the word pietas?', 'kind': 'corpus', 'carries': False},
    {'q': 'does Lucan ever use "sacer ignis"?', 'kind': 'corpus', 'carries': False},

    # ---- follow-ups. The subject is in the previous turn, not this sentence ----
    {'q': 'how about in post-classical authors?', 'kind': 'corpus',
     'carries': True, 'subject': 'arma virumque', 'history': PHRASE_HISTORY},
    {'q': 'what about Ovid?', 'kind': 'corpus',
     'carries': True, 'subject': 'arma virumque', 'history': PHRASE_HISTORY},
    {'q': "are you sure it's not in Eobanus?", 'kind': 'corpus',
     'carries': True, 'subject': 'arma virumque', 'history': PHRASE_HISTORY},
    {'q': 'and in Greek?', 'kind': 'corpus',
     'carries': True, 'subject': 'arma virumque', 'history': PHRASE_HISTORY},
    {'q': 'any earlier ones?', 'kind': 'corpus',
     'carries': True, 'subject': 'arma virumque', 'history': PHRASE_HISTORY},
    {'q': 'show me the actual lines', 'kind': 'corpus',
     'carries': True, 'subject': 'arma virumque', 'history': PHRASE_HISTORY},

    # ---- a site question AFTER a search still carries nothing. The bug itself ----
    {'q': "tell me about the site's search capabilities", 'kind': 'site',
     'carries': False, 'history': PHRASE_HISTORY},
    {'q': 'what search types are there?', 'kind': 'site',
     'carries': False, 'history': PHRASE_HISTORY},
    {'q': 'how do I export that?', 'kind': 'site',
     'carries': False, 'history': PHRASE_HISTORY},

    # ---- a fresh question after a search carries nothing either ----
    {'q': 'where does the word amor appear in Catullus?', 'kind': 'corpus',
     'carries': False, 'history': PHRASE_HISTORY},
    {'q': 'compare Statius Thebaid 12 with Vergil Aeneid 1', 'kind': 'corpus',
     'carries': False, 'history': PHRASE_HISTORY},

    # ---- described subjects. Words will not find these ----
    {'q': 'are there any passages about a storm at sea?', 'kind': 'theme', 'carries': False},
    {'q': 'find me a warrior arming for battle', 'kind': 'theme', 'carries': False},
    {'q': 'passages about lamenting the dead', 'kind': 'theme', 'carries': False},
    {'q': 'is there anything about a descent to the underworld?', 'kind': 'theme',
     'carries': False},
    {'q': 'scenes of hospitality between strangers', 'kind': 'theme', 'carries': False},

    # ---- holdings ----
    {'q': 'what texts do you have by Ovid?', 'kind': 'holdings', 'carries': False},
    {'q': 'how many Greek works are there?', 'kind': 'holdings', 'carries': False},
    {'q': 'what Hebrew texts are in the corpus?', 'kind': 'holdings', 'carries': False},
    {'q': 'do you have Statius?', 'kind': 'holdings', 'carries': False},

    # ---- reading ----
    {'q': 'let me read Aeneid 6', 'kind': 'read', 'carries': False},
    {'q': 'open the Iliad book 1', 'kind': 'read', 'carries': False},
    {'q': 'show me the text of Catullus 64', 'kind': 'read', 'carries': False},
]


# HELD OUT. Written after the classifier scored 43/43 on the set above, and
# never looked at while tuning the prompt, because 100% on the cases you tuned
# against measures nothing. Different wordings, and deliberately harder: site
# questions that use corpus vocabulary, corpus questions that name features,
# follow-ups with no content words at all.
HELDOUT = [
    {'q': 'how do the rare word searches differ from the fusion ones?',
     'kind': 'site', 'carries': False},
    {'q': 'does Tesserae handle Greek accents?', 'kind': 'site', 'carries': False},
    {'q': 'why are some of my results marked weak?', 'kind': 'site', 'carries': False},
    {'q': 'can I download the parallels as a spreadsheet?', 'kind': 'site',
     'carries': False},
    {'q': 'what is the difference between a lemma and an exact search?',
     'kind': 'site', 'carries': False},
    {'q': 'who built this?', 'kind': 'site', 'carries': False},
    {'q': 'is the Aeneid searchable here?', 'kind': 'holdings', 'carries': False},

    {'q': 'find every line containing nefas', 'kind': 'corpus', 'carries': False},
    {'q': 'does anyone else say "conticuere omnes"?', 'kind': 'corpus',
     'carries': False},
    {'q': 'trace the phrase "sunt lacrimae rerum"', 'kind': 'corpus', 'carries': False},
    {'q': 'which poets echo Lucretius on death?', 'kind': 'corpus', 'carries': False},

    {'q': 'a hero descending into the underworld to meet the dead',
     'kind': 'theme', 'carries': False},
    {'q': 'anything where a god disguises themselves as a mortal?',
     'kind': 'theme', 'carries': False},
    {'q': 'I want scenes of a city burning', 'kind': 'theme', 'carries': False},
    {'q': 'passages describing a banquet', 'kind': 'theme', 'carries': False},

    {'q': 'list the works of Seneca', 'kind': 'holdings', 'carries': False},
    {'q': 'how much Coptic is in here?', 'kind': 'holdings', 'carries': False},
    {'q': 'which Latin authors are represented?', 'kind': 'holdings', 'carries': False},

    {'q': 'open Georgics 4 for me', 'kind': 'read', 'carries': False},
    {'q': 'I would like to read the Bacchae', 'kind': 'read', 'carries': False},

    # follow-ups with almost no content of their own
    {'q': 'anywhere else?', 'kind': 'corpus', 'carries': True,
     'subject': 'arma virumque', 'history': PHRASE_HISTORY},
    {'q': 'only in poetry?', 'kind': 'corpus', 'carries': True,
     'subject': 'arma virumque', 'history': PHRASE_HISTORY},
    {'q': 'and before Vergil?', 'kind': 'corpus', 'carries': True,
     'subject': 'arma virumque', 'history': PHRASE_HISTORY},
    {'q': 'why does that matter?', 'kind': 'corpus', 'carries': True,
     'subject': 'arma virumque', 'history': PHRASE_HISTORY},

    # a site question and a fresh question, both after a search
    {'q': 'can I save these results?', 'kind': 'site', 'carries': False,
     'history': PHRASE_HISTORY},
    {'q': 'now find "pius Aeneas"', 'kind': 'corpus', 'carries': False,
     'history': PHRASE_HISTORY},
]


def current(question, history):
    """What the router decides TODAY, read off the functions it really calls.

    THE ORDER HERE MATTERS AND WAS WRONG ONCE. A first version tried
    _is_about_the_site as soon as the other named paths declined, which scored
    the router at 70% on kind and made "where does furor appear?" look like a
    question about the site. That is not what the code does: line 1630 guards
    that branch with `if not all_facts`, so it is only reached when every fast
    path declined AND no search produced anything. Reproducing the guard means
    asking first whether the question offers something to search for at all --
    a quoted phrase, a carried subject, a bare word, or the name of a text.

    Flattering the replacement by understating the baseline would make this
    whole exercise worthless.
    """
    from backend.assistant import agent
    q = (question or '')
    ql = q.lower()
    carried = agent._carried_phrase(question, history)
    if agent._is_about_the_tool(question):
        kind = 'site'
    elif agent._theme_question(question) and not agent._quoted_phrase(question):
        kind = 'theme'
    elif any(h in ql for h in agent._HOLDINGS_QUESTION):
        kind = 'holdings'
    elif any(r in ql for r in agent._READ_INTENT):
        kind = 'read'
    elif (agent._quoted_phrase(question) or carried
          or agent._TEXT_NAME.search(q)
          or any(agent._is_a_word(w.strip('?.,";')) for w in q.split())):
        kind = 'corpus'          # something concrete to look for
    elif agent._is_about_the_site(question):
        kind = 'site'
    else:
        kind = 'corpus'
    return {'kind': kind, 'carries': carried is not None, 'subject': carried}


def score(fn, verbose=False, probes=None):
    probes = PROBES if probes is None else probes
    kind_ok = carry_ok = both_ok = 0
    misses = []
    for p in probes:
        got = fn(p['q'], p.get('history'))
        k = got['kind'] == p['kind']
        c = bool(got['carries']) == bool(p['carries'])
        if k:
            kind_ok += 1
        if c:
            carry_ok += 1
        if k and c:
            both_ok += 1
        else:
            misses.append((p, got))
    n = len(probes)
    print(f'  kind correct  : {kind_ok:>3}/{n}  ({100*kind_ok/n:.0f}%)')
    print(f'  carry correct : {carry_ok:>3}/{n}  ({100*carry_ok/n:.0f}%)')
    print(f'  both correct  : {both_ok:>3}/{n}  ({100*both_ok/n:.0f}%)')
    if verbose and misses:
        print('\n  misses:')
        for p, got in misses:
            h = ' (after a search)' if p.get('history') else ''
            print(f"    {p['q']!r}{h}")
            print(f"      want kind={p['kind']:8} carries={bool(p['carries'])}")
            print(f"      got  kind={got['kind']:8} carries={bool(got['carries'])}"
                  f"{'  subject=' + repr(got['subject']) if got['carries'] else ''}")
    return both_ok, len(probes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--which', default='current', choices=('current', 'classify'))
    ap.add_argument('--set', dest='which_set', default='tuned',
                    choices=('tuned', 'heldout', 'both'))
    args = ap.parse_args()

    if args.which == 'classify':
        from backend.assistant import classify as C
        label, fn = 'MODEL CLASSIFIER', (lambda q, h: C.classify(q, h).as_probe())
    else:
        label, fn = 'CURRENT ROUTER', current

    sets = {'tuned': [('tuned on', PROBES)], 'heldout': [('HELD OUT', HELDOUT)],
            'both': [('tuned on', PROBES), ('HELD OUT', HELDOUT)]}[args.which_set]
    for name, probes in sets:
        print(f'\n{label} - {name} ({len(probes)} probes)')
        score(fn, args.verbose, probes)
    return 0


if __name__ == '__main__':
    sys.exit(main())
