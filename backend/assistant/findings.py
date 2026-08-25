"""Computed findings: what the evidence actually shows, worked out in Python.

This is the layer that makes a small model safe to use here. Everything a reader
would call analysis (which kind of evidence dominates, how distinctive the shared
vocabulary is, whether the hits cluster on one theme, whether the case is strong)
is COMPUTED from the search engine's own output, then handed to the model to put
into prose. The model adds fluency, never facts.

The pattern is production doctrine elsewhere (Tableau states its AI "isn't
involved in the identification of data insights"), and it is measured: Reiter
reports 52 to 76 percent fewer content errors from small models when the input is
restructured this way.

One caution shapes the design. Grenander et al. (2025) found plan-then-narrate did
NOT help small models when the plan was itself model-generated. What makes this
version work is that the plan is externally true, so every field below must be a
COMPUTED quantity or a corpus fact, never a model guess. The one field that is
itself a model product, the passage index's content agreement, is labelled as such
so the narration can hedge it.
"""
import collections
import re

# Which channels count as which kind of evidence. Fusion reports the channels
# that fired on each pair, and the mix is the most telling thing about a match.
_VERBATIM = {'quotation'}
_LEXICAL = {'exact', 'lemma', 'lemma_min1', 'rare_word'}
_SUBLEXICAL = {'sound', 'edit_distance'}
_STRUCTURAL = {'syntax', 'syntax_structural'}
_MEANING = {'semantic', 'dictionary', 'context'}

# Evidence-sufficiency bands. These decide which claim the narration is ALLOWED
# to make, so "the evidence does not settle this" is a computed branch rather
# than something the model must decide (small models cannot reason reliably
# about their own uncertainty, so we do not ask them to).
VERDICTS = {
    'verbatim': 'A verbatim run of shared words. The strongest evidence of direct reuse.',
    'distinctive_lexical': 'Shared vocabulary rare enough that coincidence is unlikely.',
    'moderate_lexical': 'Shared vocabulary, but common enough that convention could explain it.',
    'thematic': 'Agreement in content and situation rather than in wording.',
    'weak': 'Little beyond ordinary shared vocabulary.',
}


def _channels_of(result):
    return set(result.get('channels') or [])


def _idf_values(result):
    """Per-word corpus rarity carried on the matched words, when present."""
    out = []
    for w in (result.get('matched_words') or []):
        if isinstance(w, dict) and isinstance(w.get('idf_score'), (int, float)):
            out.append(float(w['idf_score']))
    return out


def _ref_of(result, side):
    v = result.get(side)
    if isinstance(v, dict):
        return v.get('ref') or ''
    return str(v or '')


def _work_of(ref):
    """Author-and-work part of a reference tag, for clustering."""
    m = re.match(r'^([a-z_]+(?:\.[a-z_]+)?)', str(ref).strip().lower())
    return m.group(1) if m else str(ref)


def summarize_results(results, source_id=None, target_id=None, limit=25):
    """Reduce a ranked result list to the facts a narration may use.

    Every number here comes from the search engine or the corpus. Nothing is
    inferred by a language model.
    """
    top = [r for r in (results or []) if isinstance(r, dict)][:limit]
    if not top:
        return {'n_results': 0, 'verdict': 'weak',
                'verdict_note': 'The search returned nothing to analyse.'}

    chan_counts = collections.Counter()
    for r in top:
        for c in _channels_of(r):
            chan_counts[c] += 1

    idfs = [v for r in top for v in _idf_values(r)]
    mean_idf = round(sum(idfs) / len(idfs), 2) if idfs else None
    max_idf = round(max(idfs), 2) if idfs else None

    n = len(top)
    verbatim_hits = sum(1 for r in top if _channels_of(r) & _VERBATIM)
    rare_hits = chan_counts.get('rare_word', 0)
    meaning_hits = sum(1 for r in top if _channels_of(r) & _MEANING)
    multi_channel = sum(1 for r in top if len(_channels_of(r)) >= 3)

    # The verdict is a rule over computed quantities, in strength order.
    if verbatim_hits:
        verdict = 'verbatim'
    elif mean_idf is not None and mean_idf >= 7.0 and rare_hits >= max(2, n // 4):
        verdict = 'distinctive_lexical'
    elif rare_hits >= max(2, n // 4) or (mean_idf is not None and mean_idf >= 5.0):
        verdict = 'moderate_lexical'
    elif meaning_hits >= n // 2:
        verdict = 'thematic'
    else:
        verdict = 'weak'

    # Which works the matches land in, since a cluster in one book means more
    # than the same count scattered across a corpus.
    tgt_works = collections.Counter(_work_of(_ref_of(r, 'target')) for r in top)
    src_works = collections.Counter(_work_of(_ref_of(r, 'source')) for r in top)

    # Themes, when the passage index contributed them. Labelled as model-derived.
    themes = collections.Counter()
    for r in top:
        for t in (r.get('themes') or []):
            themes[str(t).lower()] += 1

    facts = {
        'n_results': n,
        'source': source_id,
        'target': target_id,
        'channels_fired': dict(chan_counts.most_common()),
        'verbatim_pairs': verbatim_hits,
        'rare_word_pairs': rare_hits,
        'multi_channel_pairs': multi_channel,
        'mean_word_rarity_idf': mean_idf,
        'max_word_rarity_idf': max_idf,
        'rarity_scale_note': 'IDF 0-10, higher is rarer corpus-wide.',
        'verdict': verdict,
        'verdict_note': VERDICTS[verdict],
        'target_concentration': tgt_works.most_common(3),
        'source_concentration': src_works.most_common(3),
    }
    if themes:
        facts['shared_themes'] = themes.most_common(4)
        facts['themes_caveat'] = ('Theme tags come from machine-written passage '
                                  'descriptions, so treat them as suggestive.')
    return facts


def format_for_narration(facts, passages=None, max_passages=5):
    """Render computed facts as the prompt block the model narrates.

    Plain text rather than JSON on purpose: asking a small model to reason inside
    a JSON envelope measurably degrades open-weight models, so the structure is
    given as readable lines and any formatting happens after generation.
    """
    if not facts or not facts.get('n_results'):
        return 'COMPUTED FACTS: the search returned no results to analyse.'

    lines = ['COMPUTED FACTS (calculated by the search engine, not by you):']
    if facts.get('source') and facts.get('target'):
        lines.append(f"- Comparison: {facts['source']} against {facts['target']}")
    lines.append(f"- {facts['n_results']} top-ranked parallels examined.")

    ch = facts.get('channels_fired') or {}
    if ch:
        top_ch = ', '.join(f'{k} on {v} of {facts["n_results"]}'
                           for k, v in list(ch.items())[:6])
        lines.append(f'- Evidence channels that fired: {top_ch}.')
    lines.append(f"- Verbatim runs of shared words: {facts.get('verbatim_pairs', 0)} pairs.")
    lines.append(f"- Rare-word matches: {facts.get('rare_word_pairs', 0)} pairs.")
    if facts.get('mean_word_rarity_idf') is not None:
        lines.append(f"- Mean shared-word corpus rarity: {facts['mean_word_rarity_idf']} "
                     f"(scale 0-10, higher is rarer). Rarest single word: "
                     f"{facts.get('max_word_rarity_idf')}.")
    conc = facts.get('target_concentration') or []
    if conc:
        # Spelled out rather than written as "aeneid (3)". A bare number in
        # parentheses after a work name reads as a book number, and a model asked
        # to narrate it duly reported matches concentrating in "Book 3" when the
        # 3 was a count. Numbers in this block have to say what they count.
        n = facts['n_results']
        lines.append('- Where the matches land: '
                     + '; '.join(f'{c} of the {n} in {w}' for w, c in conc) + '.')
    if facts.get('shared_themes'):
        lines.append('- Themes shared across the matches: '
                     + ', '.join(f'{t} ({c})' for t, c in facts['shared_themes']) + '.')
        lines.append(f"- Caveat: {facts['themes_caveat']}")
    lines.append(f"- EVIDENCE VERDICT (computed rule): {facts['verdict'].upper()}. "
                 f"{facts['verdict_note']}")

    if passages:
        lines.append('')
        lines.append('PASSAGES (the only text you may quote):')
        for i, p in enumerate(passages[:max_passages], 1):
            s = p.get('source_text') or p.get('source', {}).get('text', '')
            t = p.get('target_text') or p.get('target', {}).get('text', '')
            sr = _ref_of(p, 'source')
            tr = _ref_of(p, 'target')
            lines.append(f'[{i}] {sr}: "{str(s)[:180]}"')
            lines.append(f'    {tr}: "{str(t)[:180]}"')
    return '\n'.join(lines)
