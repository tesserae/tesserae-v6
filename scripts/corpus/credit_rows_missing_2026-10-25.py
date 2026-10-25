#!/usr/bin/env python3
"""Close the credit-row gap the coverage checker reported on 2026-10-25.

Fifty texts had no row in backend/text_sources.json under the title the Reader shows. Forty-eight
of them had a row under an older title (a Greek title replaced by a Latin one at the 2026-10-18
rename, a file-name fragment such as "Life | Cyrus" replaced by a display title, a hyphenless
"Asrar E Khudi", the Shahnameh once filed as "Diwan"). Those rows are retitled in place, so the Credits
page does not list a work twice. Two works had no row at all (Spenser's Faerie Queene, the Homeric
Hymns) and get one. Dry run by default.

    python scripts/corpus/credit_rows_missing_2026-10-25.py [--write]
"""
import json
import os
import sys

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    'backend', 'text_sources.json')

# (author, old work) -> (author, new work). The new pair is what get_text_metadata gives the file.
RETITLE = {
    # Greek: the Greek-title rows made for the files before the 2026-10-18 rename
    ('Aelian', 'Ἀποσπασμάτια'): ('Aelian', 'Fragmenta'),
    ('Aelius Herodianus', 'Περι Καθολικης Προσῳδιας'): ('Aelius Herodianus', 'De Prosodia Catholica'),
    ('Aeschines Sp', 'Ἐπιστολαί'): ('Aeschines Sp', 'Epistulae'),
    ('Aesop', 'Αισώπειων Μύθων Συναγωγή'): ('Aesop', 'Fabularum Collectio'),
    ('Alcidamas', 'Περὶ Σοφιστῶν'): ('Alcidamas', 'De Sophistis'),
    ('Antisthenes', 'Αἴας'): ('Antisthenes', 'Aiax'),
    ('Apollonius Dyscolus', 'Περὶ Ἀντωνυμίας'): ('Apollonius Dyscolus', 'De Pronominibus'),
    ('Claudius Ptolemaeus', 'Μαθηματικὴ Σύνταξις'): ('Claudius Ptolemaeus', 'Syntaxis Mathematica'),
    ('Cleonides', 'Εἰσαγωγὴ Ἁρμονική'): ('Cleonides', 'Introductio Harmonica'),
    ('Diogenianus of Heraclea', 'Παροιμίαι Δημώδεις Ἐκ Τῆς Διογενιανοῦ Συναγωγῆς E'):
        ('Diogenianus of Heraclea', 'Paroemiae'),
    ('Galen', 'Περὶ Τῶν Ἐν Ταῖς Τροφαῖς Δυνάμεων'): ('Galen', 'De Alimentorum Facultatibus'),
    ('Gorgias of Leontini', 'Ἑλένης Ἐγκώμιον'): ('Gorgias of Leontini', 'Helenae Encomium'),
    ('Gorgias of Leontini', 'Ὑπέρ Παλαμήδους Ἀπολογία'): ('Gorgias of Leontini', 'Palamedis Defensio'),
    ('Hermogenes', 'Περὶ Τῶν Στάσεων'): ('Hermogenes', 'De Statibus'),
    ('Nicomachus of Gerasa', 'Ἀριθμητικὴ Εἰσαγωγή'): ('Nicomachus of Gerasa', 'Introductio Arithmetica'),
    ('Nicomachus of Gerasa', 'Ἐγχειρίδιον Ἁρμονικῆς'): ('Nicomachus of Gerasa', 'Harmonices Enchiridion'),
    ('Plutarch', 'Παροιμίαι Αἷς Ἀλεξανδρεῖς Ἐχρῶντο'): ('Plutarch', 'Proverbia Alexandrinorum'),
    ('Pseudolucian', 'Δημοσθένους Ἐγκώμιον'): ('Pseudolucian', 'Demosthenis Encomium'),
    ('Pseudolucian', 'Κυνικός'): ('Pseudolucian', 'Cynicus'),
    ('Pseudolucian', 'Λούκιος Ἢ Ὄνος'): ('Pseudolucian', 'Asinus'),
    ('Pseudolucian', 'Ἔρωτες'): ('Pseudolucian', 'Amores'),
    ('Theophrastus', 'Περί Ὀσμών'): ('Theophrastus', 'De Odoribus'),
    ('Tryphon I Grammaticus', 'Περὶ Τρόπων'): ('Tryphon I Grammaticus', 'De Tropis'),
    ('Zenobius Sophista', 'Ἐπιτομὴ Ἐκ Τῶν Ταρραίου Καὶ Διδύμου Παροιμιῶν Συντ'):
        ('Zenobius Sophista', 'Epitome Proverbiorum'),
    # Coptic: rows filed under the file-name fragments, before the 2026-10-18 display titles
    ('Life', 'Aphou'): ('Sahidic Coptic', 'Life of Aphou'),
    ('Life', 'Cyrus'): ('Sahidic Coptic', 'Life of Cyrus'),
    ('Life', 'Eustathius.theopiste'): ('Sahidic Coptic', 'Life of Eustathius and Theopiste'),
    ('Life', 'John.kalybites'): ('Sahidic Coptic', 'Life of John Kalybites'),
    ('Life', 'Longinus.lucius'): ('Sahidic Coptic', 'Life of Longinus and Lucius'),
    ('Life', 'Onnophrius'): ('Sahidic Coptic', 'Life of Onnophrius'),
    ('Life', 'Paul.tamma'): ('Sahidic Coptic', 'Life of Paul of Tamma'),
    ('Life', 'Phib'): ('Sahidic Coptic', 'Life of Phib'),
    ('Life', 'Pisentius'): ('Sahidic Coptic', 'Life of Pisentius'),
    ('Mercurius', 'Mercurius'): ('Sahidic Coptic', 'Encomium and Martyrdom of Mercurius'),
    ('Mysteries', 'John'): ('Sahidic Coptic', 'Mysteries of John the Apostle'),
    ('Pistis', 'Sophia'): ('Sahidic Coptic', 'Pistis Sophia'),
    ('Theodosius', 'Alexandria'): ('Theodosius of Alexandria', 'Encomium on Michael the Archangel'),
    ('Thomas', 'Gospel'): ('Sahidic Coptic', 'Gospel of Thomas'),
    # Persian and Urdu
    ('Ferdowsi', 'Diwan'): ('Ferdowsi', 'Shahnameh'),
    ('Iqbal', 'Armaghan E Hijaz Persian'): ('Iqbal', 'Armaghan-e Hijaz (Persian)'),
    ('Iqbal', 'Asrar E Khudi'): ('Iqbal', 'Asrar-e Khudi'),
    ('Iqbal', 'Payam E Mashriq'): ('Iqbal', 'Payam-e Mashriq'),
    ('Iqbal', 'Rumuz E Bekhudi'): ('Iqbal', 'Rumuz-e Bekhudi'),
    ('Iqbal', 'Zabur E Ajam'): ('Iqbal', 'Zabur-e Ajam'),
    ('Iqbal', 'Armaghan E Hijaz Urdu'): ('Iqbal', 'Armaghan-e Hijaz (Urdu)'),
    ('Iqbal', 'Bal E Jibril'): ('Iqbal', 'Bal-e Jibril'),
    ('Iqbal', 'Bang E Dra'): ('Iqbal', 'Bang-e Dra'),
    ('Iqbal', 'Zarb E Kaleem'): ('Iqbal', 'Zarb-e Kaleem'),
}

# Life of Paul of Tamma: the row said CC-BY 4.0 (from the TEI header of the PATHS-derived file), but the
# corpus annotation of the Coptic SCRIPTORIUM repository (life-paul-tamma, life.paul.tamma_ANNIS) says
# CC BY-NC-SA 4.0, as it does for the other three PATHS lives, and the project's license inventory agrees.
PAUL_TAMMA_LICENSE = 'CC BY-NC-SA 4.0'

NEW_ROWS = [
    {
        'author': 'Spenser',
        'work': 'Faerie Queene',
        'e_source': 'Project Gutenberg',
        'e_source_url': 'https://www.gutenberg.org/ebooks/70717',
        'print_source': ("Spenser's Faerie Queene, ed. J. C. Smith, 2 vols. Oxford: Clarendon Press, 1909 "
                         "(Gutenberg #70717, Books I-III, and #72698, Books IV-VII)."),
        'added_by': 'Tesserae Project',
        'license': 'Public domain in the USA (Project Gutenberg)',
    },
    {
        'author': 'Homer',
        'work': 'Hymns',
        'e_source': 'Perseus Digital Library / Open Greek and Latin (canonical-greekLit, TLG 0013)',
        'e_source_url': 'https://github.com/PerseusDL/canonical-greekLit/tree/master/data/tlg0013',
        'print_source': ('Hugh G. Evelyn-White, ed., Hesiod, the Homeric Hymns and Homerica, Loeb Classical '
                         'Library. London: William Heinemann Ltd. / New York: The Macmillan Co., 1914.'),
        'added_by': 'Tesserae Project',
        'license': ("CC BY-SA 4.0 (license of the Perseus canonical repository; the text's own TEI header "
                    "states none)"),
    },
]


def main():
    write = '--write' in sys.argv
    with open(PATH, encoding='utf-8') as fh:
        rows = json.load(fh)
    todo = dict(RETITLE)
    n_retitled = 0
    for r in rows:
        new = todo.pop((r['author'], r['work']), None)
        if new is None:
            continue
        r['author'], r['work'] = new
        if new == ('Sahidic Coptic', 'Life of Paul of Tamma'):
            r['license'] = PAUL_TAMMA_LICENSE
        n_retitled += 1
    if todo:
        sys.exit('rows not found: %r' % sorted(todo))
    have = {(r['author'], r['work']) for r in rows}
    added = [n for n in NEW_ROWS if (n['author'], n['work']) not in have]
    rows.extend(added)
    print('retitled', n_retitled, 'added', len(added))
    if write:
        with open(PATH, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(rows, indent=2, ensure_ascii=False) + '\n')
        print('written', PATH)


if __name__ == '__main__':
    main()
