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
content lemmas (e.g. ϭⲟⲓⲥ "lord", ⲣⲱⲙⲉ "man", ⲛⲟⲩⲧⲉ "god") are
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
    'ϯ',         # Bohairic def. art. fem.
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
    'ⲡⲉϥ',       # poss. art. "his"
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
    'ϩⲛ',        # in (Sahidic)
    'ϧⲉⲛ',       # in (Bohairic)
    'ϩⲓ',        # on / upon
    'ϩⲓⲧⲛ',      # through / by means of (instrumental)
    'ϩⲓⲧⲙ',      # through / by (variant before labials)
    'ⲉϫⲛ',       # upon
    'ⲉϫⲉⲛ',      # upon (variant)
    'ⲛⲥⲁ',       # after / behind
    'ϩⲁ',        # to / until
    'ⲙⲡⲉ',       # before
    'ⲙⲡ',        # before (variant)
    'ⲉⲡ',        # to (the)
    'ⲉⲡⲉ',       # to (the)
    'ⲉⲡⲓ',       # to (the, Bohairic)
    'ⲡⲉϫⲉ',      # to (the) — variant of ⲉⲡⲉ
    'ⲕⲁⲧⲁ',      # according to (Greek κατά). Coptic Kappa U+2C95.
    'ⲡⲁⲣⲁ',      # contrary to (Greek παρά)
    'ⲉⲧⲃⲉ',      # because of / about

    # ---- Directional adverbs / particles ----
    'ⲉⲃⲟⲗ',      # out / forth
    'ⲉϩⲟⲩⲛ',     # in / inside
    'ⲉϩⲣⲁⲓ',     # up / down (depending on vector)
    'ⲉⲡⲁϩⲟⲩ',    # back / behind
    'ⲡⲉ',        # there / abroad (homophone with copula above; same form)
    'ⲙⲁ',        # place
    'ⲙⲙⲁⲩ',      # there
    'ⲙⲙⲟϥ',      # of him / object pronoun
    'ⲙⲙⲟⲥ',      # of her / object pronoun
    'ⲙⲙⲟⲟⲩ',     # of them
    'ⲙⲙⲱⲧⲛ',     # of you (pl)

    # ---- Independent personal pronouns (Sahidic) ----
    'ⲁⲛⲟⲕ',      # I
    'ⲛⲧⲟⲕ',      # you (m)
    'ⲛⲧⲟ',       # you (f)
    'ⲛⲧⲟϥ',      # he
    'ⲛⲧⲟⲥ',      # she
    'ⲁⲛⲟⲛ',      # we
    'ⲛⲧⲱⲧⲛ',     # you (pl)
    'ⲛⲧⲟⲟⲩ',     # they
    # Bohairic equivalents (the ⲑ-series)
    'ⲛⲑⲟⲕ',      # you (m)
    'ⲛⲑⲟ',       # you (f)
    'ⲛⲑⲟϥ',      # he
    'ⲛⲑⲟⲥ',      # she
    'ⲛⲑⲱⲧⲉⲛ',    # you (pl)
    'ⲛⲑⲱⲟⲩ',     # they

    # ---- Suffix-pronoun-like clitics that appear as standalone tokens ----
    'ϥ',         # 3sg masc bound pronoun
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
    'ⲟⲩⲟϩ',      # and (Bohairic) — top-20 most frequent token
    'ⲇⲉ',        # but / and (Greek δέ)
    'ⲅⲁⲣ',       # for (Greek γάρ)
    'ⲁⲗⲗⲁ',      # but (Greek ἀλλά)
    'ⲙⲉⲛ',       # μέν
    'ⲏ',         # or
    'ⲉⲓⲧⲉ',      # whether...whether
    'ϭⲉ',        # then / now / so (also "now" — Greek δη?)
    'ϫⲉ',        # that / because (subordinator; was ϫⲉ)
    'ⲉⲡⲓⲇⲏ',     # since (Greek ἐπειδή)
    'ⲱⲥⲇⲉ',      # so that (Greek ὥστε)
    'ⲕⲁⲓ',       # also / even (Greek καί). Coptic Kappa U+2C95.
    'ⲱⲥ',        # as / like (Greek ὡς)
    'ⲡⲗⲏⲛ',      # however (Greek πλήν)
    'ϫⲓⲛ',       # since / from (temporal/spatial)
    'ⲧⲉⲛⲟⲩ',     # now (temporal adverb)

    # ---- Relative / circumstantial / converter morphemes ----
    'ⲉⲣⲉ',       # circumstantial converter
    'ⲉⲧⲉⲣⲉ',     # relative converter
    'ⲉⲧⲉ',       # relative converter (short)
    'ⲉⲧ',        # relative prefix
    'ⲛⲉⲣⲉ',      # past circumstantial
    'ⲛⲧⲉⲣⲉ',     # temporal "when"
    'ⲉϥ',        # circumstantial + 3sg
    'ⲉⲩ',        # circumstantial + 3pl
    'ⲛϭⲓ',       # subject-marker particle "the one who"
    'ϯ',         # auxiliary I (perfect/preterit), the same form as the Bohairic article above

    # ---- Auxiliary / tense-aspect-mood morphemes ----
    'ⲁ',         # perfect auxiliary
    'ⲙⲡ',        # negative perfect (already above as preposition; same surface form)
    'ⲛⲁ',        # future / "will"
    'ⲛⲉ',        # imperfect (also copula above; same form)
    'ⲡⲉⲣⲉ',      # past
    'ⲉⲣⲉ',       # subjunctive (also relative above)
    'ⲙⲁⲣⲉ',      # imperative-let
    'ⲙⲡⲣ',       # negative imperative
    'ⲉⲣϣⲁⲛ',     # conditional
    'ⲉⲩϣⲁⲛ',     # conditional + 3pl
    'ϣⲁⲣⲉ',      # habitual aspect auxiliary "habitually / often"

    # ---- Negation ----
    'ⲁⲛ',        # negative postclitic
    'ⲧⲙ',        # negative infinitive

    # ---- High-frequency light verbs / copula-like ----
    'ϣⲱⲡⲉ',      # to be / become (Sahidic)
    'ϣⲱⲡⲓ',      # to be / become (Bohairic)
    'ⲉⲓ',        # to come
    'ⲉⲓⲣⲉ',      # to do (Sahidic)
    'ⲓⲣⲓ',       # to do (Bohairic)
    'ⲡⲉϫⲉ',      # to say (suppletive form)
    'ϫⲱ',        # to say
    'ϭⲱ',        # to put / leave
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
    'ⲉⲓⲥϩⲏⲏⲧⲉ',  # behold!

    # ---- Greek loanword particles / very-high-frequency loanwords ----
    'ⲇⲉ',        # δέ (already above)
    'ⲅⲁⲣ',       # γάρ (already above)

    # ---- Bohairic-specific high-frequency forms not yet covered ----
    'ⲡⲉⲧ',       # the one who
    'ⲫⲁⲓ',       # this (already above)
    'ⲛⲏ',        # the ones / those
}
