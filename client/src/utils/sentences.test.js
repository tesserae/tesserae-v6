import { describe, it, expect } from 'vitest';
import { splitSentences, sentencesOf } from './sentences';

// The *_PYTHON lists below were pasted from a one-off run of
// scripts/corpus/prose_windows.py `sentence_spans` over the same texts
// (2026-10-11): the cut points of the passage index's prose windows. The
// Reader's sentences are FINER than those (this corpus writes lowercase after
// a full stop, which the Python rule never cuts before, and the port does not
// cut after "L." or "M."), so the test checks that every Python cut is also a
// cut here, apart from the abbreviation joins, and pins the new counts. The
// difference is harmless: the Similar route maps a sentence to its window by
// character offset, not by cut point.

const pieces = (text) => splitSentences(text).map((p) => text.slice(p.start, p.end));
const starts = (text) => new Set(splitSentences(text).map((p) => p.start));
const pyStarts = (list) => {
  let n = 0;
  return list.map((p) => { const at = n; n += p.length; return at; });
};

const ANNALS11 = "Vrbem Romam a principio reges habuere; libertatem et consulatum L. Brutus instituit. dictaturae ad tempus sumebantur; neque decemviralis potestas ultra biennium, neque tribunorum militum consulare ius diu valuit. non Cinnae, non Sullae longa dominatio; et Pompei Crassique potentia cito in Caesarem, Lepidi atque Antonii arma in Augustum cessere, qui cuncta discordiis civilibus fessa nomine principis sub imperium accepit. sed veteris populi Romani prospera vel adversa claris scriptoribus memorata sunt; temporibusque Augusti dicendis non defuere decora ingenia, donec gliscente adulatione deterrerentur. Tiberii Gaique et Claudii ac Neronis res florentibus ipsis ob metum falsae, postquam occiderant recentibus odiis compositae sunt. inde consilium mihi pauca de Augusto et extrema tradere, mox Tiberii principatum et cetera, sine ira et studio, quorum causas procul habeo.";
const ANNALS11_PYTHON = ["Vrbem Romam a principio reges habuere; libertatem et consulatum L. ", "Brutus instituit. dictaturae ad tempus sumebantur; neque decemviralis potestas ultra biennium, neque tribunorum militum consulare ius diu valuit. non Cinnae, non Sullae longa dominatio; et Pompei Crassique potentia cito in Caesarem, Lepidi atque Antonii arma in Augustum cessere, qui cuncta discordiis civilibus fessa nomine principis sub imperium accepit. sed veteris populi Romani prospera vel adversa claris scriptoribus memorata sunt; temporibusque Augusti dicendis non defuere decora ingenia, donec gliscente adulatione deterrerentur. ", "Tiberii Gaique et Claudii ac Neronis res florentibus ipsis ob metum falsae, postquam occiderant recentibus odiis compositae sunt. inde consilium mihi pauca de Augusto et extrema tradere, mox Tiberii principatum et cetera, sine ira et studio, quorum causas procul habeo."];

const ANNALS13 = "Ceterum Augustus subsidia dominationi Claudium Marcellum sororis filium admodum adulescentem pontificatu et curuli aedilitate, M. Agrippam, ignobilem loco, bonum militia et victoriae socium, geminatis consulatibus extulit, mox defuncto Marcello generum sumpsit; Tiberium Neronem et Claudium Drusum privignos imperatoriis nominibus auxit, integra etiam tum domo sua. nam genitos Agrippa Gaium ac Lucium in familiam Caesarum induxerat, necdum posita puerili praetexta principes iuventutis appellari, destinari consules specie recusantis flagrantissime cupiverat. ut Agrippa vita concessit, Lucium Caesarem euntem ad Hispaniensis exercitus, Gaium remeantem Armenia et vulnere invalidum mors fato propera vel novercae Liviae dolus abstulit, Drusoque pridem extincto Nero solus e privignis erat, illuc cuncta vergere: filius, collega imperii, consors tribuniciae potestatis adsumitur omnisque per exercitus ostentatur, non obscuris, ut antea, matris artibus, sed palam hortatu. nam senem Augustum devinxerat adeo, uti nepotem unicum, Agrippam Postumum, in insulam Planasiam proiecerit, rudem sane bonarum artium et robore corporis stolide ferocem, nullius tamen flagitii conpertum. at hercule Germanicum Druso ortum octo apud Rhenum legionibus inposuit adscirique per adoptionem a Tiberio iussit, quamquam esset in domo Tiberii filius iuvenis, sed quo pluribus munimentis insisteret. bellum ea tempestate nullum nisi adversus Germanos supererat, abolendae magis infamiae ob amissum cum Quintilio  Varo exercitum quam cupidine proferendi imperii aut dignum ob praemium. domi res tranquillae, eadem magistratuum vocabula; iuniores post Actiacam victoriam, etiam senes plerique inter bella civium nati: quotus quisque reliquus qui rem publicam vidisset?";
const ANNALS13_PYTHON = ["Ceterum Augustus subsidia dominationi Claudium Marcellum sororis filium admodum adulescentem pontificatu et curuli aedilitate, M. ", "Agrippam, ignobilem loco, bonum militia et victoriae socium, geminatis consulatibus extulit, mox defuncto Marcello generum sumpsit; ", "Tiberium Neronem et Claudium Drusum privignos imperatoriis nominibus auxit, integra etiam tum domo sua. nam genitos Agrippa Gaium ac Lucium in familiam Caesarum induxerat, necdum posita puerili praetexta principes iuventutis appellari, destinari consules specie recusantis flagrantissime cupiverat. ut Agrippa vita concessit, Lucium Caesarem euntem ad Hispaniensis exercitus, Gaium remeantem Armenia et vulnere invalidum mors fato propera vel novercae Liviae dolus abstulit, Drusoque pridem extincto Nero solus e privignis erat, illuc cuncta vergere: filius, collega imperii, consors tribuniciae potestatis adsumitur omnisque per exercitus ostentatur, non obscuris, ut antea, matris artibus, sed palam hortatu. nam senem Augustum devinxerat adeo, uti nepotem unicum, Agrippam Postumum, in insulam Planasiam proiecerit, rudem sane bonarum artium et robore corporis stolide ferocem, nullius tamen flagitii conpertum. at hercule Germanicum Druso ortum octo apud Rhenum legionibus inposuit adscirique per adoptionem a Tiberio iussit, quamquam esset in domo Tiberii filius iuvenis, sed quo pluribus munimentis insisteret. bellum ea tempestate nullum nisi adversus Germanos supererat, abolendae magis infamiae ob amissum cum Quintilio  Varo exercitum quam cupidine proferendi imperii aut dignum ob praemium. domi res tranquillae, eadem magistratuum vocabula; iuniores post Actiacam victoriam, etiam senes plerique inter bella civium nati: quotus quisque reliquus qui rem publicam vidisset?"];

const THUC122 = "τῆς γὰρ ἐμπορίας οὐκ οὔσης, οὐδ' ἐπιμειγνύντες ἀδεῶς ἀλλήλοις οὔτε κατὰ γῆν οὔτε διὰ θαλάσσης, νεμόμενοί τε τὰ αὑτῶν ἕκαστοι ὅσον ἀποζῆν καὶ περιουσίαν χρημάτων οὐκ ἔχοντες οὐδὲ γῆν φυτεύοντες, ἄδηλον ὂν ὁπότε τις ἐπελθὼν καὶ ἀτειχίστων ἅμα ὄντων ἄλλος ἀφαιρήσεται, τῆς τε καθ' ἡμέραν ἀναγκαίου τροφῆς πανταχοῦ ἂν ἡγούμενοι ἐπικρατεῖν, οὐ χαλεπῶς ἀπανίσταντο, καὶ δι' αὐτὸ οὔτε μεγέθει πόλεων ἴσχυον οὔτε τῇ ἄλλῃ παρασκευῇ.";
const THUC122_PYTHON = ["τῆς γὰρ ἐμπορίας οὐκ οὔσης, οὐδ' ἐπιμειγνύντες ἀδεῶς ἀλλήλοις οὔτε κατὰ γῆν οὔτε διὰ θαλάσσης, νεμόμενοί τε τὰ αὑτῶν ἕκαστοι ὅσον ἀποζῆν καὶ περιουσίαν χρημάτων οὐκ ἔχοντες οὐδὲ γῆν φυτεύοντες, ἄδηλον ὂν ὁπότε τις ἐπελθὼν καὶ ἀτειχίστων ἅμα ὄντων ἄλλος ἀφαιρήσεται, τῆς τε καθ' ἡμέραν ἀναγκαίου τροφῆς πανταχοῦ ἂν ἡγούμενοι ἐπικρατεῖν, οὐ χαλεπῶς ἀπανίσταντο, καὶ δι' αὐτὸ οὔτε μεγέθει πόλεων ἴσχυον οὔτε τῇ ἄλλῃ παρασκευῇ."];

const THUC111 = "Θουκυδίδης Ἀθηναῖος ξυνέγραψε τὸν πόλεμον τῶν Πελοποννησίων καὶ Ἀθηναίων, ὡς ἐπολέμησαν πρὸς ἀλλήλους, ἀρξάμενος εὐθὺς καθισταμένου καὶ ἐλπίσας μέγαν τε ἔσεσθαι καὶ ἀξιολογώτατον τῶν προγεγενημένων, τεκμαιρόμενος ὅτι ἀκμάζοντές τε ᾖσαν ἐς αὐτὸν ἀμφότεροι παρασκευῇ τῇ πάσῃ καὶ τὸ ἄλλο Ἑλληνικὸν ὁρῶν ξυνιστάμενον πρὸς ἑκατέρους, τὸ μὲν εὐθύς, τὸ δὲ καὶ διανοούμενον.";
const THUC111_PYTHON = ["Θουκυδίδης Ἀθηναῖος ξυνέγραψε τὸν πόλεμον τῶν Πελοποννησίων καὶ Ἀθηναίων, ὡς ἐπολέμησαν πρὸς ἀλλήλους, ἀρξάμενος εὐθὺς καθισταμένου καὶ ἐλπίσας μέγαν τε ἔσεσθαι καὶ ἀξιολογώτατον τῶν προγεγενημένων, τεκμαιρόμενος ὅτι ἀκμάζοντές τε ᾖσαν ἐς αὐτὸν ἀμφότεροι παρασκευῇ τῇ πάσῃ καὶ τὸ ἄλλο Ἑλληνικὸν ὁρῶν ξυνιστάμενον πρὸς ἑκατέρους, τὸ μὲν εὐθύς, τὸ δὲ καὶ διανοούμενον."];

describe('splitSentences against the Python cutter', () => {
  it('Thucydides 1.1.1 and 1.2.2: one sentence each, identical', () => {
    expect(pieces(THUC111)).toEqual(THUC111_PYTHON);
    expect(pieces(THUC122)).toEqual(THUC122_PYTHON);
  });

  it('Annals 1.1: six sentences, cut after every full stop, never after "L."', () => {
    const got = pieces(ANNALS11);
    expect(got).toHaveLength(6);
    expect(got[0].endsWith('L. Brutus instituit. ')).toBe(true);
    expect(got[1].startsWith('dictaturae ')).toBe(true);
    expect(got[2].startsWith('non Cinnae')).toBe(true);
    expect(got[3].startsWith('sed veteris')).toBe(true);
    expect(got[4].startsWith('Tiberii Gaique')).toBe(true);
    expect(got[5].startsWith('inde consilium')).toBe(true);
  });

  it('Annals 1.3: eight sentences, none cut after "M."', () => {
    const got = pieces(ANNALS13);
    expect(got).toHaveLength(8);
    expect(got[0].endsWith('generum sumpsit; ')).toBe(true);
    expect(got.some((p) => p.endsWith('M. '))).toBe(false);
  });

  it('every Python cut is a cut here, except the abbreviation joins', () => {
    for (const [text, py, joined] of [[ANNALS11, ANNALS11_PYTHON, [1]], [ANNALS13, ANNALS13_PYTHON, [1]]]) {
      const mine = starts(text);
      pyStarts(py).forEach((at, k) => { if (!joined.includes(k)) expect(mine.has(at)).toBe(true); });
    }
  });

  it('the pieces tile the text exactly and never cut inside a word', () => {
    for (const t of [ANNALS11, ANNALS13, THUC111, THUC122]) {
      const parts = splitSentences(t);
      expect(parts[0].start).toBe(0);
      expect(parts[parts.length - 1].end).toBe(t.length);
      parts.forEach((p, i) => {
        if (i) expect(p.start).toBe(parts[i - 1].end);
        if (i) expect(/\s/.test(t[p.start - 1])).toBe(true);
        expect(/\s/.test(t[p.start])).toBe(false);
      });
      expect(parts.map((p) => t.slice(p.start, p.end)).join('')).toBe(t);
    }
  });
});

describe('abbreviations do not end a sentence', () => {
  it.each([
    ['libertatem et consulatum L. Brutus instituit.', 1],
    ['Ceterum Augustus M. Agrippam extulit.', 1],
    ['Hoc fecit C. Caesar in Gallia.', 1],
    ['Hoc dixit Ti. Nero senatui.', 1],
    ['Hoc dixit Cn. Pompeius senatui.', 1],
    ['Θουκυδίδης Ἀθηναῖος ξυνέγραψε. Ἀρξάμενος εὐθύς.', 2],
    ['Hoc fecit Caesar. Postea Brutus abiit.', 2],
    ['Hoc fecit Caesar. postea brutus abiit.', 2],
    ['Hoc fecit q. fabius cum p. c. et aliis.', 1],
    ['Hoc fecit Cos. Fabius et Coss. Caesar.', 1],
    ['Hoc fecit tr. pl. Gracchus pr. urbanus.', 1],
    ['Ante diem Kal. Ian. et Non. Mart. et Id. Apr. fuit.', 1],
    ['Hoc est non. Id est bonum.', 2],
    ['Hoc dixit. id fecit.', 2],
    ['Quid est? nihil est! sic est.', 3],
    ['Quid est? Nihil est! Sic est; Ita est.', 4],
    ['Sic est; ita est. Hoc est.', 2],
  ])('%s', (text, n) => {
    expect(splitSentences(text)).toHaveLength(n);
  });
});

describe('sentencesOf', () => {
  it('is null for a verse-length unit and for a single long sentence', () => {
    expect(sentencesOf('Arma virumque cano. Troiae qui primus ab oris.')).toBeNull();
    expect(sentencesOf(THUC111)).toBeNull();
  });
  it('gives the pieces of a long unit', () => {
    expect(sentencesOf(ANNALS11)).toHaveLength(6);
  });
});
