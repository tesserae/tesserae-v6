"""
Persian function words / stopwords for Tesserae V6.

BUG FIX (2026-09-04): entries below are written in native Persian orthography
(Persian ya U+06CC, Persian kaf U+06A9, alif-madda U+0622, ...) for readability,
but the indexed lemma stream is folded through `normalize_persian()`
(Persian ya -> Arabic ya U+064A, Persian kaf -> Arabic kaf U+0643, alif variants
-> bare alif U+0627) before it ever reaches the stoplist comparison in
`fusion._STOPLISTS`. Because the raw literal set was registered unnormalized,
21 of the original 64 entries -- including some of the highest-frequency words
in the language (که "that/who", می "progressive marker", کرد "did/made", این/آن
"this/that", نیست "is-not", یک "one") -- silently never matched anything. This
is why the fa smoke test's top hits were full of unfiltered common verbs
(کند/شود etc.): the stoplist that was supposed to catch them was inert for
exactly the highest-value entries. Normalizing at import time (below) fixes
this for the existing 64 AND for every new entry added here, regardless of
which orthographic form is typed.

Additions (2026-09-04): extended past the original 64 using the fa_index.db
`lemma_doc_freq` table (28-text corpus) -- the ~250 lemmas at df>=26 (present
in nearly every text), tie-broken by total token frequency from `postings`.
Added only unambiguous auxiliaries/copulas/prepositions/pronouns/particles;
left in anything polysemous with a plausible content reading (e.g. باز
"again"/"falcon", روی "on"/"face", گرد "around"/"dust", حال "now"/"state",
دیگر "other" as a near-content determiner, numerals دو/صد/یکی) per the
"when unsure, leave it in" rule -- these can filter down further later with
more evidence.
"""

from backend.persian.processor import normalize_persian

_RAW_STOP_WORDS = {
    # Conjunctions
    'و', 'یا', 'اما', 'ولی', 'که', 'تا', 'چون', 'اگر', 'گر',
    'کز',       # contraction of "که" + "ز" ("that from") -- added 2026-09-04
    'چو',       # poetic contraction of "چون" ("as/when") -- added 2026-09-04
    # Prepositions
    'از', 'به', 'با', 'در', 'بر', 'تا', 'برای', 'بی', 'مگر',
    'جز',       # "except/save" -- added 2026-09-04
    'پیش',      # "before/in front of" -- added 2026-09-04
    'سوی',      # "toward" -- added 2026-09-04
    'میان',     # "between/among" -- added 2026-09-04
    'زیر',      # "under/below" -- added 2026-09-04
    'درون',     # "inside" -- added 2026-09-04
    'بالا',     # "up/above" -- added 2026-09-04
    'مانند',    # "like/such as" -- added 2026-09-04
    'زی',       # archaic "toward" -- added 2026-09-04
    # Pronouns
    'من', 'تو', 'او', 'ما', 'شما', 'ایشان', 'آن', 'این',
    'خود', 'خویش', 'خویشتن',  # reflexive "self/own" -- added 2026-09-04
    'وی',                      # 3rd person "he/she/it" -- added 2026-09-04
    'کس', 'کسی',               # indefinite "person/anyone/someone" -- added 2026-09-04
    # Demonstratives
    'آن', 'این', 'همان', 'همین', 'چنین', 'چنان',
    # Ezafe / copula
    'است', 'بود', 'شد', 'هست', 'نیست', 'باشد', 'بودن',
    'گشت', 'گردید',  # "became" -- alternate copulas to شد, same register -- added 2026-09-04
    # Auxiliary / common verbs
    'کرد', 'کردن', 'شدن', 'داشتن', 'داشت', 'دارد',
    'توان',  # modal "can/able to" (impersonal, e.g. می‌توان کرد) -- added 2026-09-04
    # Negation
    'نه', 'نی', 'نیست', 'مگر',
    # Common particles
    'هم', 'هر', 'چه', 'کی', 'کجا', 'چرا', 'بس',
    'را', 'می', 'نمی', 'بر',
    'چی',  # colloquial variant of "چه" ("what") -- added 2026-09-04
    'تر',  # comparative-degree suffix, tokenized standalone -- added 2026-09-04
    # Relative / interrogative
    'کدام', 'چگونه', 'چند',
    # Very common words in poetry
    'ای', 'اندر', 'مرا', 'ترا', 'ز', 'بر', 'همه', 'یک',
}

# Normalize every entry the same way indexed lemmas are normalized, so the
# stoplist actually matches what fusion._STOPLISTS compares against. Also
# de-duplicates entries that only differed by orthographic variant.
# Arabic-script punctuation marks that the tokenizers currently keep as
# standalone tokens (comma, question mark, semicolon, full stop). Found in
# the Urdu web test 2026-09-05; the tokenizer fix is an open item because it
# forces an index rebuild.
_PUNCTUATION_TOKENS = {'\u060c', '\u061f', '\u061b', '\u06d4'}
PERSIAN_STOP_WORDS = {normalize_persian(w) for w in _RAW_STOP_WORDS} | _PUNCTUATION_TOKENS
