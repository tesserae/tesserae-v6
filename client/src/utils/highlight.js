// The one place that decides which words of a line to highlight.
//
// Three call sites used to carry their own copy (inside SearchResults.jsx):
//   markMatchedWords     the CSV export, bolds matched words as **word**;
//   highlightResultHtml  the result card, wraps matched words in <mark>;
//   renderInstanceText   the corpus panel's instance lines, bolds them.
// They differ on purpose, so each keeps its own entry point and its output is
// proved against client/src/utils/__fixtures__/highlight_cases.json, recorded
// from the three old functions on main. What they share lives here once:
// the edge-punctuation strip, the Hebrew point strip and the word splitter.
//
//   - Words: the CSV export and the instance lines match surface words
//     from matched_words; the card also uses the server's highlight_indices,
//     lemmas, sound n-grams, semantic stems and the poem's rhyme word.
//   - Edge punctuation: the instance lines also strip the middle dot and the
//     Greek ano teleia; the other two do not.
//   - Folds: the instance lines fold Latin u/v and j/i and Greek accents; the
//     card folds Latin u/v, Coptic blocks, Hebrew points and Persian letters;
//     the CSV export folds nothing but case.
//   - Whole word or part: the CSV export bolds only the letters inside the
//     punctuation of a token; the other two mark the whole whitespace part.
import { createElement } from 'react';
import { normalizeCoptic } from './copticUtils';

// Hebrew nikkud and cantillation, and the maqaf, off a string.
const stripHebrewPoints = (s) => s.normalize('NFD').replace(/[֑-ֽֿ-ׇ]/g, '').replace(/־/g, '');

// Hebrew maqaf (U+05BE) joins words in the display text but the backend
// splits them, so for Hebrew it is a split point too.
const wordSplitter = (lang) => (lang === 'he' ? /(\s+|־)/ : /(\s+)/);

// Punctuation cut off the front and back of a word before it is compared.
// EDGE is what the CSV export and the card cut; the instance lines also cut
// the middle dot and the Greek ano teleia (EDGE_WIDE).
const EDGE = [/^[.,;:!?'"()\u2014\u2013-]+/, /[.,;:!?'"()\u2014\u2013-]+$/];
const EDGE_WIDE = [/^[.,;:!?'"()—–··-]+/, /[.,;:!?'"()—–··-]+$/];
const stripEdges = (w, [lead, trail]) => w.replace(lead, '').replace(trail, '');

// CSV export: matched words in the text wrapped as **word**. side is
// 'source' or 'target'; only the surface words in matched_words count.
export const markMatchedWords = (text, matchedWords, side) => {
  if (!text || !matchedWords || matchedWords.length === 0) return text;
  const words = new Set();
  matchedWords.forEach(m => {
    const w = side === 'source' ? m.source_word : m.target_word;
    if (w) words.add(w.toLowerCase());
  });
  if (words.size === 0) return text;
  return text.replace(/\S+/g, token => {
    const stripped = stripEdges(token.toLowerCase(), EDGE);
    if (stripped && words.has(stripped)) {
      const start = token.toLowerCase().indexOf(stripped);
      return token.slice(0, start) + '**' + token.slice(start, start + stripped.length) + '**' + token.slice(start + stripped.length);
    }
    return token;
  });
};

// Result card: the HTML for one side of a result, matched words in <mark>.
// textData is {text, tokens, highlight_indices}; the card passes the other
// side for semantic matches and the poem's poetics for Persian and Urdu.
export const highlightResultHtml = (textData, language = null, matchedWords = [], isSource = true, otherTextData = null, poetics = null) => {
  if (!textData) return '';

  if (typeof textData === 'string') return textData;

  const { text, tokens, highlight_indices } = textData;

  if (!text) return '';

  // Build set of words to highlight from multiple sources
  const wordsToHighlight = new Set();
  // For sound matching: n-grams to search for within words
  const soundNgrams = new Set();

  // 1. From highlight_indices (if available)
  if (tokens && highlight_indices && highlight_indices.length > 0) {
    highlight_indices.forEach(i => {
      const token = tokens[i]?.toLowerCase();
      if (token) wordsToHighlight.add(token);
    });
  }

  // 2. From matched_words (for semantic and sound matches)
  if (matchedWords && matchedWords.length > 0) {
    matchedWords.forEach(m => {
      // Add the source or target word based on which side we're rendering
      const word = isSource ? m.source_word : m.target_word;
      if (word) wordsToHighlight.add(word.toLowerCase());
      // Also add the lemma (handles cases where lemma differs from token)
      if (m.lemma && !m.lemma.includes('\u2248') && m.lemma !== 'semantic') {
        // Check if this looks like a sound n-gram match (e.g., "[ngram]", "source~target")
        const lemmaStr = String(m.lemma);
        if (lemmaStr.includes('[') || lemmaStr.includes('~')) {
          // Extract n-grams from sound match format
          const ngrams = lemmaStr.split(/[[\],~\s]+/).filter(s => s.length >= 2);
          ngrams.forEach(ng => soundNgrams.add(ng.toLowerCase()));
        } else {
          wordsToHighlight.add(lemmaStr.toLowerCase());
        }
      }
      // Handle display field for sound matches
      if (m.display) {
        const displayStr = String(m.display);
        if (displayStr.includes('[') || displayStr.includes('~')) {
          const ngrams = displayStr.split(/[[\],~\s]+/).filter(s => s.length >= 2);
          ngrams.forEach(ng => soundNgrams.add(ng.toLowerCase()));
        }
      }
    });
  }

  // 3. Find common word stems between source and target (ONLY for semantic matches)
  // For exact/lemma matches, we trust the backend highlight_indices which respect the stoplist
  const isSemanticMatch = matchedWords?.some(m => m.similarity !== undefined || m.lemma === 'semantic');
  if (isSemanticMatch && otherTextData && otherTextData.tokens && tokens) {
    const thisTokens = new Set(tokens.map(t => t?.toLowerCase()).filter(Boolean));
    const otherTokens = new Set(otherTextData.tokens.map(t => t?.toLowerCase()).filter(Boolean));

    // Find tokens that share a common stem (first 4+ chars) - catches hasta/hastam
    thisTokens.forEach(token => {
      if (token.length >= 4) {
        const stem = token.slice(0, Math.min(token.length - 1, 5));
        otherTokens.forEach(otherToken => {
          if (otherToken.length >= 4 && otherToken.startsWith(stem)) {
            wordsToHighlight.add(token);
          }
        });
      }
    });
  }

  // Poetics (fa/ur/ar, 2026-09-06): the rhyme word sits just before the
  // refrain (or is the last word when the match is rhyme-letter only);
  // it gets its own colour, the refrain keeps the usual highlight.
  const rhymeWords = new Set();
  if (poetics) {
    const named = isSource ? poetics.source_rhyme_word : poetics.target_rhyme_word;
    if (named) rhymeWords.add(String(named).toLowerCase());
    else if (tokens && tokens.length) {
      const start = isSource ? poetics.source_radif_start : poetics.target_radif_start;
      const idx = poetics.rhyme_only ? start : start - 1;
      if (idx >= 0 && idx < tokens.length && tokens[idx]) rhymeWords.add(String(tokens[idx]).toLowerCase());
    } else if (text) {
      // results cached before the rhyme word was named: take it from the
      // line itself, the word before the refrain (or the last word)
      const words = text.split('\n')[0].split(/\s+/).filter(Boolean);
      const n = poetics.rhyme_only ? 0 : (poetics.radif_len || 0);
      const idx = words.length - 1 - n;
      if (idx >= 0) rhymeWords.add(words[idx].toLowerCase());
    }
  }
  // Compare in one script form: the stored tokens are normalized (Persian
  // yeh and kaf folded to the Arabic letters, alef variants to alef) while
  // the displayed line keeps its own spelling, so fold both the same way.
  const foldScript = (w) => w
    .replace(/[\u064B-\u065F\u0670\u06D6-\u06ED\u0640\u200C\u200F\u200E]/g, '')
    .replace(/[\u064A\u06CC\u0649\u06D2\u06D3]/g, '\u06CC')
    .replace(/[\u0643\u06A9]/g, '\u06A9')
    .replace(/[\u0622\u0623\u0625\u0671]/g, '\u0627')
    .replace(/[\u06C1\u06BE\u06C3\u0629]/g, '\u0647')
    .replace(/\u06BA/g, '\u0646');
  const isRhymeWord = (word) => {
    if (!rhymeWords.size) return false;
    const n = foldScript(word.toLowerCase().replace(/[.,;:!?'"()\u2014\u2013\u060C\u061B\u061F\u06D4-]+$/, ''));
    for (const rw of rhymeWords) if (foldScript(rw) === n) return true;
    return false;
  };

  // Helper to check if a word matches any highlight word or contains sound n-grams
  const shouldHighlight = (word) => {
    const normalized = stripEdges(word.toLowerCase(), EDGE);
    if (wordsToHighlight.has(normalized)) return true;

    // Hyphenated compounds and elided forms: "Arch-fiend" -> arch / fiend,
    // "reply'd" -> reply. Highlight if any interior sub-part matches a
    // highlight word. Common in English (Milton) and safe elsewhere.
    if (normalized.includes('-') || normalized.includes("'") || normalized.includes('\u2019')) {
      const parts = normalized.split(/[-'\u2019]/).filter(p => p.length >= 2);
      for (const part of parts) {
        if (wordsToHighlight.has(part)) return true;
      }
    }

    // For sound matching: check if word contains any of the matched n-grams
    if (soundNgrams.size > 0) {
      for (const ngram of soundNgrams) {
        if (normalized.includes(ngram)) return true;
        // Also check with Greek accent normalization (strip diacritics for matching)
        const normalizedNoAccents = normalized.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        const ngramNoAccents = ngram.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        if (normalizedNoAccents.includes(ngramNoAccents)) return true;
      }
    }

    // For Latin, also check u/v equivalence
    if (language === 'la') {
      const uvNormalized = normalized.replace(/[uv]/g, 'u');
      for (const hw of wordsToHighlight) {
        if (hw.replace(/[uv]/g, 'u') === uvNormalized) return true;
      }
    }
    // Coptic uses two equivalent Unicode blocks (U+03E2-03EF and
    // U+2CB2-2CBF) for the same seven letters. Backend tokens are
    // normalised to the latter; .tess display text uses the former.
    // Normalise both sides before comparing. Backend tokens are
    // sub-word morphemes (Scriptorium CoNLL-U) but the displayed text is
    // whitespace-split into bound groups, so a sub-word match must
    // highlight any bound group that contains it.
    if (language === 'cop') {
      const copNormalized = normalizeCoptic(normalized);
      for (const hw of wordsToHighlight) {
        const hwNorm = normalizeCoptic(hw);
        if (!hwNorm) continue;
        if (hwNorm === copNormalized) return true;
        if (copNormalized.includes(hwNorm)) return true;
      }
    }
    // Hebrew: the display text is fully pointed (nikkud + cantillation) but the
    // highlight tokens/lemmas are unvocalized. Strip both before comparing.
    if (language === 'he') {
      const heNorm = stripHebrewPoints(normalized);
      for (const hw of wordsToHighlight) {
        if (stripHebrewPoints(hw) === heNorm) return true;
      }
    }
    return false;
  };

  if (wordsToHighlight.size === 0 && soundNgrams.size === 0) {
    // Still need to handle line breaks in window results
    return text.includes('\n') ? text.replace(/\n/g, '<br class="verse-break" />') : text;
  }

  // Split text into verses (window results have \n between lines)
  const verses = text.split('\n');
  const highlightedVerses = verses.map(verse => {
    const parts = verse.split(wordSplitter(language));
    return parts.map(part => {
      if (/^\s+$/.test(part)) return part; // whitespace
      if (shouldHighlight(part)) {
        return `<mark class="bg-yellow-200 px-0.5 rounded">${part}</mark>`;
      }
      return part;
    }).join('');
  });

  return highlightedVerses.join('<br class="verse-break" />');
};

// Bold the matched words inside a corpus-instance line. matched_words are the
// actual surface tokens the line-search flagged, so normalize the same way the
// card highlighter does (case, trailing punctuation, Latin u/v, Greek accents).
export const renderInstanceText = (text, matchedWords, lang) => {
  if (!text) return null;
  const strip = (w) => stripEdges(w.toLowerCase(), EDGE_WIDE);
  const norm = (w) => {
    let n = strip(w);
    if (lang === 'la') n = n.replace(/[uv]/g, 'u').replace(/j/g, 'i');
    if (lang === 'grc') n = n.normalize('NFD').replace(/[̀-ͯ]/g, '');
    // Hebrew: strip nikkud + cantillation (matched_words are unvocalized, but the
    // displayed .tess text is fully pointed) and the maqaf so it does not fuse words.
    if (lang === 'he') n = stripHebrewPoints(n);
    return n;
  };
  const wanted = new Set((matchedWords || []).map(norm).filter(Boolean));
  if (!wanted.size) return text;
  // Hebrew maqaf (U+05BE) joins words in the display text but the backend splits
  // them, so split on it too (kept as its own inert part) to highlight each word.
  return text.split(wordSplitter(lang)).map((part, i) => {
    if (/^\s+$/.test(part) || !part) return part;
    return wanted.has(norm(part))
      ? createElement('strong', { key: i, className: 'font-semibold text-gray-900' }, part)
      : createElement('span', { key: i }, part);
  });
};
