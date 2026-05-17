"""
Coptic function words / stopwords for Tesserae V6.

Curated list of high-frequency Sahidic and Bohairic Coptic particles,
prepositions, pronouns, articles, conjunctions, and other function-class
forms. Forms are normalised to the **U+2CB2-2CBF** Coptic-specific block
(matching backend `normalize_coptic` output) — the same form used in the
per-file lemma caches under `cache/lemmas/cop/`. Without this, the
stoplist would miss tokens whose Hori/Shei/Janja/Cima letters live in
U+2CB2-2CBF rather than U+03E2-03EF.

The list is sized for **sub-word tokenisation** (one entry per morpheme).
After tokenisation switched from bound-group to sub-word level
(2026-05-01), the per-token vocabulary inflated 2-3x, so a much larger
stoplist is needed to keep the rare_word / lemma channels from drowning
in trivial morpheme overlap.

Coverage is intentionally aggressive: any morpheme that contributes
function-class meaning rather than referential content is in. Borderline
content lemmas (e.g. ⲽⲟⲓⲥ "lord", ⲣⲱⲙⲉ "man", ⲛⲟⲩⲧⲉ "god") are
NOT stoplisted even though they're frequent — those represent real
content overlap when shared.
"""

# Each morpheme is given in NORMALISED form (U+2CB2-2CBF for the
# Coptic-only letters Shei, Fei, Khei, Hori, Janja, Cima, Dei).
COPTIC_STOP_WORDS = {
    # ---- Articles / determiners (definite / indefinite / possessive) ----
    'ⲡ',         # def. art. masc. sg.
    'ⲧ',         # def. art. fem. sg.
    'ⲛ',         # def. art. pl. / genitive linker / preposition "of"
    'ⲟⲩ',        # indef. art. sg. / "what"
    'ⲡⲓ',        # Bohairic def. art. masc.
    'ϯ',         # Bohairic def. art. fem.  (legacy block)
    'ⲿ',         # Bohairic def. art. fem.  (normalised form of ϯ)
    'ⲛⲓ',        # Bohairic def. art. pl.
    'ⲡⲉ',        # is / masc. copula / poss. art. "your(2)"
    'ⲧⲉ',        # is / fem. copula
    'ⲛⲉ',        # are / pl. copula
    'ⲡⲁ',        # poss. art. "my"
    'ⲡⲉⲕ',       # poss. art. "your(m)"
    'ⲧⲉⲕ',       # poss. art. "your(m)"  fem.
    'ⲛⲉⲕ',       # poss. art. "your(m)"  pl.
    'ⲡⲟⲩ',       # poss. art. "their"
    'ⲡⲉⲛ',       # poss. art. "our"
    'ⲡⲉⲩ',       # poss. art. "their"
    'ⲡⲉⲵ',       # poss. art. "his"
    'ⲡⲉⲥ',       # poss. art. "her"
    'ⲛⲟⲩ',       # poss. art. pl.
    'ⲡⲉⲧⲛ',      # poss. art. "your(pl)" m.
    'ⲧⲉⲧⲛ',      # poss. art. "your(pl)" f.
    'ⲛⲉⲧⲛ',      # poss. art. "your(pl)" pl.

    # ---- Prepositions ----
    'ⲉ',         # to / toward
    'ⲙ',         # of / accusative / variant of ⲛ before labials
    'ⲙⲛ',        # with / and (Sahidic)
    'ⲛⲉⲙ',       # with / and (Bohairic)
    'ⲛⲧⲉ',       # of / belonging to
    'ⲹⲛ',        # in (Sahidic)
    'ⲷⲉⲛ',       # in (Bohairic)
    'ⲹⲓ',        # on / upon
    'ⲹⲓⲧⲛ',      # through / by means of (instrumental)
    'ⲹⲓⲧⲙ',      # through / by (variant before labials)
    'ⲉⲻⲛ',       # upon
    'ⲉⲻⲉⲛ',      # upon (variant)
    'ⲛⲥⲁ',       # after / behind
    'ⲹⲁ',        # to / until
    'ⲙⲡⲉ',       # before
    'ⲙⲡ',        # before (variant)
    'ⲉⲡ',        # to (the)
    'ⲉⲡⲉ',       # to (the)
    'ⲉⲡⲓ',       # to (the, Bohairic)
    'ⲡⲉⲻⲉ',      # to (the) — variant of ⲉⲡⲉ
    'ⲕⲁⲧⲁ',      # according to (Greek κατά). Coptic Kappa U+2C95.
    'ⲡⲁⲣⲁ',      # contrary to (Greek παρά)
    'ⲉⲧⲃⲉ',      # because of / about

    # ---- Directional adverbs / particles ----
    'ⲉⲃⲟⲗ',      # out / forth
    'ⲉⲹⲟⲩⲛ',     # in / inside
    'ⲉⲹⲣⲁⲓ',     # up / down (depending on vector)
    'ⲉⲡⲁⲹⲟⲩ',    # back / behind
    'ⲡⲉ',        # there / abroad (homophone with copula above; same form)
    'ⲙⲁ',        # place
    'ⲙⲙⲁⲩ',      # there
    'ⲙⲙⲟⲵ',      # of him / object pronoun
    'ⲙⲙⲟⲥ',      # of her / object pronoun
    'ⲙⲙⲟⲟⲩ',     # of them
    'ⲙⲙⲱⲧⲛ',     # of you (pl)

    # ---- Independent personal pronouns (Sahidic) ----
    'ⲁⲛⲟⲕ',      # I
    'ⲛⲧⲟⲕ',      # you (m)
    'ⲛⲧⲟ',       # you (f)
    'ⲛⲧⲟⲵ',      # he
    'ⲛⲧⲟⲥ',      # she
    'ⲁⲛⲟⲛ',      # we
    'ⲛⲧⲱⲧⲛ',     # you (pl)
    'ⲛⲧⲟⲟⲩ',     # they
    # Bohairic equivalents (the ⲑ-series)
    'ⲛⲑⲟⲕ',      # you (m)
    'ⲛⲑⲟ',       # you (f)
    'ⲛⲑⲟⲵ',      # he
    'ⲛⲑⲟⲥ',      # she
    'ⲛⲑⲱⲧⲉⲛ',    # you (pl)
    'ⲛⲑⲱⲟⲩ',     # they

    # ---- Suffix-pronoun-like clitics that appear as standalone tokens ----
    'ⲵ',         # 3sg masc bound pronoun
    'ⲥ',         # 3sg fem bound pronoun
    'ⲩ',         # 3pl bound pronoun
    'ⲕ',         # 2sg masc bound pronoun
    'ⲧⲛ',        # 2pl bound pronoun
    'ⲛ',         # 1pl bound pronoun (also def.art.pl above; same form)
    'ⲓ',         # 1sg bound pronoun

    # ---- Demonstratives ----
    # Coptic has two demonstrative sets, far-deictic (ⲡⲁⲓ-) and
    # near-deictic (ⲡⲉⲓ-). Both glossed as "this/that" depending on
    # context. Both surface as standalone tokens after segmentation.
    'ⲡⲁⲓ',       # this (m, far)
    'ⲧⲁⲓ',       # this (f, far)
    'ⲛⲁⲓ',       # these (far)
    'ⲡⲉⲓ',       # this (m, near)
    'ⲧⲉⲓ',       # this (f, near)
    'ⲛⲉⲓ',       # these (near)
    'ⲫⲁⲓ',       # this (m, Bohairic)
    'ⲫⲏ',        # the one (m, Bohairic)
    'ⲑⲏ',        # the one (f, Bohairic)
    'ⲡⲏ',        # the one (m)

    # ---- Conjunctions / discourse particles ----
    'ⲁⲩⲱ',       # and (Sahidic)
    'ⲟⲩⲟⲹ',      # and (Bohairic) — top-20 most frequent token
    'ⲇⲉ',        # but / and (Greek δέ)
    'ⲅⲁⲣ',       # for (Greek γάρ)
    'ⲁⲗⲗⲁ',      # but (Greek ἀλλά)
    'ⲙⲉⲛ',       # μέν
    'ⲏ',         # or
    'ⲉⲓⲧⲉ',      # whether...whether
    'ⲽⲉ',        # then / now / so (also "now" — Greek δη?)
    'ⲻⲉ',        # that / because (subordinator; was ϫⲉ)
    'ⲉⲡⲓⲇⲏ',     # since (Greek ἐπειδή)
    'ⲱⲥⲇⲉ',      # so that (Greek ὥστε)
    'ⲕⲁⲓ',       # also / even (Greek καί). Coptic Kappa U+2C95.
    'ⲱⲥ',        # as / like (Greek ὡς)
    'ⲡⲗⲏⲛ',      # however (Greek πλήν)
    'ⲻⲓⲛ',       # since / from (temporal/spatial)
    'ⲧⲉⲛⲟⲩ',     # now (temporal adverb)

    # ---- Relative / circumstantial / converter morphemes ----
    'ⲉⲣⲉ',       # circumstantial converter
    'ⲉⲧⲉⲣⲉ',     # relative converter
    'ⲉⲧⲉ',       # relative converter (short)
    'ⲉⲧ',        # relative prefix
    'ⲛⲉⲣⲉ',      # past circumstantial
    'ⲛⲧⲉⲣⲉ',     # temporal "when"
    'ⲉⲵ',        # circumstantial + 3sg
    'ⲉⲩ',        # circumstantial + 3pl
    'ⲛⲽⲓ',       # subject-marker particle "the one who"
    'ⲿ',         # auxiliary I (perfect/preterit; also U+2CBF Bohairic article — same form)

    # ---- Auxiliary / tense-aspect-mood morphemes ----
    'ⲁ',         # perfect auxiliary
    'ⲙⲡ',        # negative perfect (already above as preposition; same surface form)
    'ⲛⲁ',        # future / "will"
    'ⲛⲉ',        # imperfect (also copula above; same form)
    'ⲡⲉⲣⲉ',      # past
    'ⲉⲣⲉ',       # subjunctive (also relative above)
    'ⲙⲁⲣⲉ',      # imperative-let
    'ⲙⲡⲣ',       # negative imperative
    'ⲉⲣⲳⲁⲛ',     # conditional
    'ⲉⲩⲳⲁⲛ',     # conditional + 3pl
    'ⲳⲁⲣⲉ',      # habitual aspect auxiliary "habitually / often"

    # ---- Negation ----
    'ⲁⲛ',        # negative postclitic
    'ⲧⲙ',        # negative infinitive

    # ---- High-frequency light verbs / copula-like ----
    'ⲳⲱⲡⲉ',      # to be / become (Sahidic)
    'ⲳⲱⲡⲓ',      # to be / become (Bohairic)
    'ⲉⲓ',        # to come
    'ⲉⲓⲣⲉ',      # to do (Sahidic)
    'ⲓⲣⲓ',       # to do (Bohairic)
    'ⲡⲉⲻⲉ',      # to say (suppletive form)
    'ⲻⲱ',        # to say
    'ⲽⲱ',        # to put / leave
    'ⲟⲩⲱⲙ',      # to eat (very high freq, mostly biblical)

    # ---- Reciprocal / reflexive ----
    'ⲉⲣⲏⲩ',      # each other / fellow / one another
    'ⲙⲡⲣⲧⲣⲉ',    # negative imperative auxiliary "do not let / do not"

    # ---- Quantifiers / determinatives ----
    'ⲛⲓⲙ',       # every / each / who?
    'ⲧⲏⲣ',       # all / whole
    'ⲕⲉ',        # other / another
    'ⲟⲛ',        # also / again

    # ---- Existential / question particles ----
    'ⲟⲩⲛ',       # there is
    'ⲙⲛ',        # there is not (homograph with "with"; same form)
    'ⲙⲙⲟⲛ',      # there is not
    'ⲉⲛⲉ',       # interrogative

    # ---- Common short interjections / discourse markers ----
    'ⲉⲓⲥ',       # behold
    'ⲉⲓⲥⲹⲏⲏⲧⲉ',  # behold!

    # ---- Greek loanword particles / very-high-frequency loanwords ----
    'ⲇⲉ',        # δέ (already above)
    'ⲅⲁⲣ',       # γάρ (already above)

    # ---- Bohairic-specific high-frequency forms not yet covered ----
    'ⲡⲉⲧ',       # the one who
    'ⲫⲁⲓ',       # this (already above)
    'ⲛⲏ',        # the ones / those
}
