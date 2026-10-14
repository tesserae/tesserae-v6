// Fixed inputs for the render recording (renderRecording.test.jsx). Nothing
// here is random and nothing reads the clock, so a change in the recorded
// HTML can only come from a change in the code that draws it.

const word = (lemma, sw, tw, extra = {}) => ({ lemma, source_word: sw, target_word: tw, ...extra });

// 30 rows, every field a result card reads. Rows 0-9 Latin lemma matches
// built from tokens and highlight_indices; 10-13 semantic; 14-16 sound
// n-grams; 17-19 Greek; 20-22 Coptic (one in the legacy Unicode block);
// 23 a quotation match; 24-27 poetic (refrain and rhyme); 28 English with a
// hyphenated compound; 29 pointed Hebrew.
export const makeRows = () => {
  const rows = [];
  const latin = [
    ['arma virumque cano', 'arma virumque canit', 'arma', 'virum'],
    ['Troiae qui primus ab oris', 'Troiae primus ab oris', 'Troia', 'primus'],
    ['Italiam fato profugus', 'Italiam profugus fato', 'Italia', 'profugus'],
    ['litora multum ille et terris', 'multum litora iactatus', 'litus', 'multus'],
    ['iactatus et alto vi superum', 'alto superum vi', 'altum', 'supero'],
    ['saevae memorem Iunonis ob iram', 'Iunonis iram memorem', 'Iuno', 'ira'],
    ['multa quoque et bello passus', 'bello passus multa', 'bellum', 'multus'],
    ['dum conderet urbem', 'urbem condere dum', 'urbs', 'condo'],
    ['inferretque deos Latio', 'deos Latio inferret', 'deus', 'Latium'],
    ['genus unde Latinum', 'genus Latinum unde', 'genus', 'Latinus'],
  ];
  latin.forEach(([s, t, l1, l2], i) => {
    const st = s.split(' ');
    const tt = t.split(' ');
    rows.push({
      source: { ref: `vergil.aeneid.part.1.${i + 1}`, citation: `Vergil, Aeneid 1.${i + 1}`, text: s, tokens: st.map((w) => w.toLowerCase()), highlight_indices: [0, 1] },
      target: { ref: `lucan.bellum_civile.part.1.${i + 11}`, citation: `Lucan, Civil War 1.${i + 11}`, text: t, tokens: tt.map((w) => w.toLowerCase()), highlight_indices: [0, 2] },
      source_locus: `vergil.aeneid.part.1.${i + 1}`,
      target_locus: `lucan.bellum_civile.part.1.${i + 11}`,
      matched_words: [word(l1, st[0], tt[0]), word(l2, st[1], tt[1])],
      channels: i % 3 === 0 ? ['lemma', 'exact'] : i % 3 === 1 ? ['lemma'] : ['lemma_min1', 'rare_word'],
      fused_score: 0.95 - i * 0.02,
      formula_count: i % 4 === 0 ? 1 : 12 + i,
      match_basis: 'lemma',
      features: i === 2 ? { meter_score: 0.62, source_scansion: { raw: '-uu-uu-uu-uu-u', meter: 'hexameter' }, target_scansion: { raw: '-uu-uu-uu-uu-x', meter: 'hexameter' } } : {},
    });
  });
  // semantic
  [['hasta ferit hostem', 'hastam iacit hostis', 'hasta', 'hastam'],
   ['cura animum angit', 'curam animus habet', 'cura', 'curam'],
   ['ventus silvas quatit', 'ventos silvae sentiunt', 'ventus', 'ventos'],
   ['mare undas volvit', 'maris unda fremit', 'mare', 'maris']].forEach(([s, t, a, b], i) => {
    const st = s.split(' ');
    const tt = t.split(' ');
    rows.push({
      source: { ref: `ovid.met.1.${i + 20}`, text: s, tokens: st, highlight_indices: [] },
      target: { ref: `seneca.phaedra.${i + 30}`, text: t, tokens: tt, highlight_indices: [] },
      source_locus: `ovid.met.1.${i + 20}`,
      target_locus: `seneca.phaedra.${i + 30}`,
      matched_words: [{ lemma: 'semantic', source_word: st[0], target_word: tt[0], similarity: 0.81 }, { lemma: a, source_word: a, target_word: b, similarity: 0.77 }],
      channels: ['semantic'],
      fused_score: 0.7 - i * 0.01,
      match_basis: 'semantic',
      features: {},
    });
  });
  // sound
  [['strepitus ventorum', 'crepitus ventosus'], ['murmur aquarum', 'murmura aquae'], ['sonitus armorum', 'sonat arma']].forEach(([s, t], i) => {
    rows.push({
      source: { ref: `statius.thebaid.1.${i + 40}`, text: s, tokens: s.split(' '), highlight_indices: [] },
      target: { ref: `lucan.bellum_civile.part.2.${i + 50}`, text: t, tokens: t.split(' '), highlight_indices: [] },
      source_locus: `statius.thebaid.1.${i + 40}`,
      target_locus: `lucan.bellum_civile.part.2.${i + 50}`,
      matched_words: [{ lemma: '[epi]~[epi]', display: '[epi]~[epi]', source_word: '', target_word: '' }, { lemma: '[ent]~[ent]', display: 'tus~tus' }],
      channels: ['sound', 'edit_distance'],
      fused_score: 0.5 - i * 0.01,
      features: {},
    });
  });
  // Greek
  [['μῆνιν ἄειδε θεὰ Πηληϊάδεω', 'μῆνιν θεὰ ἄειδε Ἀχιλῆος'], ['ἄνδρα μοι ἔννεπε Μοῦσα', 'ἄνδρα Μοῦσα μοι ἔννεπε'], ['πολλὰ δ᾽ ἀνθρώπων ἴδεν', 'πολλὰ ἀνθρώπων ἴδεν ἄστεα']].forEach(([s, t], i) => {
    rows.push({
      source: { ref: `homer.iliad.part.1.${i + 1}`, text: s, tokens: s.split(' '), highlight_indices: [0] },
      target: { ref: `homer.odyssey.part.1.${i + 1}`, text: t, tokens: t.split(' '), highlight_indices: [0] },
      source_locus: `homer.iliad.part.1.${i + 1}`,
      target_locus: `homer.odyssey.part.1.${i + 1}`,
      matched_words: [{ lemma: s.split(' ')[0], source_word: s.split(' ')[0], target_word: t.split(' ')[0] }, { lemma: 'θεά', source_word: 'θεὰ', target_word: 'θεὰ' }],
      channels: ['lemma', 'syntax'],
      fused_score: 0.4 - i * 0.01,
      features: {},
    });
  });
  // Coptic (the second row uses the legacy block letter U+03E3)
  [['ⲁⲩⲱ ⲁϥϫⲟⲟⲥ ⲛⲁⲩ', 'ⲁⲩⲱ ⲡⲉϫⲁϥ ⲛⲁϥ'], ['ϣⲁⲣⲉ ⲡⲛⲟⲩⲧⲉ ϫⲟⲟⲥ', 'ⲡⲛⲟⲩⲧⲉ ⲁϥϫⲟⲟⲥ'], ['ⲧⲉⲧⲛⲁⲟⲩⲱϣ ⲙⲙⲟϥ', 'ⲟⲩⲱϣ ⲉⲃⲟⲗ']].forEach(([s, t], i) => {
    rows.push({
      source: { ref: `nt.john.${i + 1}`, text: s, tokens: s.split(' '), highlight_indices: [0] },
      target: { ref: `shenoute.canons.${i + 1}`, text: t, tokens: t.split(' '), highlight_indices: [0] },
      source_locus: `nt.john.${i + 1}`,
      target_locus: `shenoute.canons.${i + 1}`,
      matched_words: [{ lemma: 'ⲁⲩⲱ', source_word: s.split(' ')[0], target_word: t.split(' ')[0] }],
      channels: ['lemma'],
      fused_score: 0.3 - i * 0.01,
      features: {},
    });
  });
  // quotation
  rows.push({
    source: { ref: 'vergil.aeneid.part.2.1', citation: 'Vergil, Aeneid 2.1', text: 'conticuere omnes intentique ora tenebant', tokens: ['conticuere', 'omnes', 'intentique', 'ora', 'tenebant'], highlight_indices: [0, 1, 2, 3, 4] },
    target: { ref: 'macrobius.saturnalia.1.1', text: 'conticuere omnes intentique ora tenebant', tokens: ['conticuere', 'omnes', 'intentique', 'ora', 'tenebant'], highlight_indices: [0, 1, 2, 3, 4] },
    source_locus: 'vergil.aeneid.part.2.1',
    target_locus: 'macrobius.saturnalia.1.1',
    matched_words: [{ lemma: 'conticesco', source_word: 'conticuere', target_word: 'conticuere' }],
    channels: ['quotation', 'exact'],
    fused_score: 0.99,
    formula_count: 3,
    features: {},
  });
  // poetic
  [
    { radif: 'ast', qafia: 'ān', rhyme_only: false, source_lines: [1, 2], target_lines: [1, 2, 3], corpus_poems: 14, source_rhyme_word: 'جان', target_rhyme_word: 'دهان', meter: 'ramal' },
    { radif: 'ast', qafia: 'ā', rhyme_only: true, source_lines: [1], target_lines: [1], corpus_poems: 3, meter: 'hazaj' },
    { radif: '', qafia: 'ūr', rhyme_only: false, source_lines: [4], target_lines: [5], source_radif_start: 3, target_radif_start: 2 },
    { radif: 'man ast', qafia: '', rhyme_only: false, source_lines: [], target_lines: [], radif_len: 2 },
  ].forEach((poetics, i) => {
    rows.push({
      source: { ref: `hafez.diwan.${i + 1}`, text: 'دل من جان ast من است', tokens: ['دل', 'من', 'جان', 'ast', 'من', 'است'], highlight_indices: [1, 5] },
      target: { ref: `iqbal.zabur.${i + 1}`, text: 'جان من دهان ast است', tokens: ['جان', 'من', 'دهان', 'ast', 'است'], highlight_indices: [1, 4] },
      source_locus: `hafez.diwan.${i + 1}`,
      target_locus: `iqbal.zabur.${i + 1}`,
      matched_words: [{ lemma: 'من', source_word: 'من', target_word: 'من' }, { lemma: 'است', source_word: 'است', target_word: 'است' }],
      channels: ['lemma', 'form'],
      fused_score: 0.8 - i * 0.01,
      poetics,
      features: {},
    });
  });
  // English with a hyphenated compound and an elision
  rows.push({
    source: { ref: 'milton.paradise_lost.1.1', text: "Arch-fiend reply'd, and fell", tokens: ['arch-fiend', "reply'd", 'and', 'fell'], highlight_indices: [] },
    target: { ref: 'spenser.faerie_queene.1.2', text: 'the fiend replied from below', tokens: ['the', 'fiend', 'replied', 'from', 'below'], highlight_indices: [] },
    source_locus: 'milton.paradise_lost.1.1',
    target_locus: 'spenser.faerie_queene.1.2',
    matched_words: [{ lemma: 'fiend', source_word: 'fiend', target_word: 'fiend' }, { lemma: 'reply', source_word: 'reply', target_word: 'reply' }],
    channels: ['lemma'],
    fused_score: 0.2,
    features: {},
  });
  // Hebrew, pointed
  rows.push({
    source: { ref: 'genesis.1.1', text: 'בְּרֵאשִׁית בָּרָא אֱלֹהִים', tokens: ['בראשית', 'ברא', 'אלהים'], highlight_indices: [] },
    target: { ref: 'psalms.19.1', text: 'הַשָּׁמַיִם מְסַפְּרִים כְּבוֹד־אֵל', tokens: ['השמים', 'מספרים', 'כבוד', 'אל'], highlight_indices: [] },
    source_locus: 'genesis.1.1',
    target_locus: 'psalms.19.1',
    matched_words: [{ lemma: 'אל', source_word: 'אלהים', target_word: 'אל' }, { lemma: 'ברא', source_word: 'ברא', target_word: 'ברא' }],
    channels: ['lemma'],
    fused_score: 0.1,
    features: {},
  });
  // Every second Latin row arrives pre-rendered by the server, as cached
  // results do, so the card's first branch (source_text) is recorded too.
  rows.forEach((r, i) => {
    if (i < 10 && i % 2 === 1) {
      r.source_text = `<mark class="bg-yellow-200 px-0.5 rounded">${r.source.text.split(' ')[0]}</mark> ${r.source.text.split(' ').slice(1).join(' ')}`;
      r.target_text = r.target.text;
    }
  });
  return rows;
};

export const SOURCE_INFO = { id: 'vergil.aeneid.part.1.tess', author: 'Vergil', title: 'Aeneid 1' };
export const TARGET_INFO = { id: 'lucan.bellum_civile.part.1.tess', author: 'Lucan', title: 'Civil War 1', restricted: true, credit: 'Text licensed for search only.' };

// Reply to POST /api/line-search for the corpus panel.
export const LINE_SEARCH_REPLY = {
  corpus_version: 'v-fixed',
  lines_all: 7,
  by_work_all: [
    { work_id: 'vergil.aeneid', author: 'Vergil', work: 'Aeneid', era: 'Augustan', year: -19, count: 3 },
    { work_id: 'lucan.bellum_civile', author: 'Lucan', work: 'Civil_War', era: 'Early Imperial', year: 65, count: 2 },
    { work_id: 'statius.thebaid', author: 'Statius', work: 'Thebaid', era: 'Imperial', year: 92, count: 1 },
    { work_id: 'ennius.annales', author: 'Ennius', work: 'Annales', era: 'Republic', year: -170, count: 1 },
    { work_id: 'anon.undated', author: 'Anonymous', work: 'Undated', era: 'Unknown', year: 9999, count: 1 },
  ],
  results: [
    { author: 'Vergil', work: 'Aeneid', era: 'Augustan', year: -19, locus: '1.1', text: 'arma virumque cano Troiae', matched_words: ['arma', 'virumque'] },
    { author: 'Vergil', work: 'Aeneid', era: 'Augustan', year: -19, locus: '2.5', text: 'Arma viri, ferte arma', matched_words: ['arma', 'viri'] },
    { author: 'Lucan', work: 'Civil_War', era: 'Early Imperial', year: 65, locus: '1.7', text: 'arma virum que', matched_words: ['arma', 'virum'] },
    { author: 'Statius', work: 'Thebaid', era: 'Imperial', year: 92, locus: '1.1', text: 'fraternas acies arma', matched_words: ['arma'] },
  ],
};
