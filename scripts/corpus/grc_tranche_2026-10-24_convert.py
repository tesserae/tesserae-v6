#!/usr/bin/env python3
"""Convert the Greek tranche of 2026-10-24 from the staged TEI to .tess.

    grc_tranche_2026-10-24_convert.py SRC_DIR OUT_DIR [--only NAME ...]

SRC_DIR holds the two repositories as downloaded (canonical-greekLit and
First1KGreek, each with its data/ folder). Each row of WORKS names the file,
the output stem (author.work) and the citation tag. Runs
perseus_greek_tei_to_tess.py once per row and prints its summary.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CGL, F1K = 'canonical-greekLit/data', 'First1KGreek/data'

# (stem, source file under SRC_DIR, tag, whether to split by top-level division)
WORKS = [
    ('diogenes_laertius.vitae_philosophorum', f'{CGL}/tlg0004/tlg001/tlg0004.tlg001.perseus-grc2.xml', 'diog. laert.', True),
    ('plotinus.enneades', f'{F1K}/tlg2000/tlg001/tlg2000.tlg001.1st1K-grc1.xml', 'plot. enn.', True),
    ('dio_chrysostom.orationes', f'{CGL}/tlg0612/tlg001/tlg0612.tlg001.perseus-grc2.xml', 'dio chrys. or.', True),
    ('heliodorus.aethiopica', f'{F1K}/tlg0658/tlg001/tlg0658.tlg001.perseus-grc1.xml', 'heliod. aeth.', True),
    ('longus.daphnis_et_chloe', f'{CGL}/tlg0561/tlg001/tlg0561.tlg001.perseus-grc2.xml', 'longus', True),
    ('xenophon_of_ephesus.ephesiaca', f'{CGL}/tlg0641/tlg001/tlg0641.tlg001.perseus-grc2.xml', 'xen. eph.', True),
    ('socrates_scholasticus.historia_ecclesiastica', f'{F1K}/tlg2057/tlg002/tlg2057.tlg002.1st1K-grc1.xml', 'socr. hist. eccl.', True),
    ('sozomen.historia_ecclesiastica', f'{F1K}/tlg2048/tlg001/tlg2048.tlg001.1st1K-grc1.xml', 'soz. hist. eccl.', True),
    ('theodoret.historia_ecclesiastica', f'{F1K}/tlg4089/tlg003/tlg4089.tlg003.opp-grc1.xml', 'thdt. hist. eccl.', True),
    ('philostorgius.historia_ecclesiastica', f'{F1K}/tlg2058/tlg001/tlg2058.tlg001.1st1K-grc1.xml', 'philostorg. hist. eccl.', True),
    ('anna_comnena.alexias', f'{F1K}/tlg2703/tlg001/tlg2703.tlg001.1st1K-grc1.xml', 'anna comn. alex.', True),
    ('nicander.theriaca', f'{F1K}/tlg0022/tlg001/tlg0022.tlg001.1st1K-grc1.xml', 'nic. th.', False),
    ('nicander.alexipharmaca', f'{F1K}/tlg0022/tlg002/tlg0022.tlg002.1st1K-grc1.xml', 'nic. al.', False),
    ('origen.contra_celsum', f'{F1K}/tlg2042/tlg001/tlg2042.tlg001.perseus-grc1.xml', 'orig. cels.', True),
    ('origen.commentarii_in_evangelium_joannis', f'{F1K}/tlg2042/tlg005/tlg2042.tlg005.1st1K-grc1.xml', 'orig. comm. in joh.', True),
    ('ignatius.epistulae', f'{F1K}/tlg1443/tlg001/tlg1443.tlg001.1st1K-grc1.xml', 'ign.', True),
    ('clement_of_rome.epistula_i_ad_corinthios', f'{F1K}/tlg1271/tlg001/tlg1271.tlg001.1st1K-grc1.xml', '1 clem.', False),
    ('clement_of_rome.epistula_ii_ad_corinthios', f'{F1K}/tlg1271/tlg002/tlg1271.tlg002.1st1K-grc1.xml', '2 clem.', False),
    ('didache.didache', f'{F1K}/tlg1311/tlg001/tlg1311.tlg001.1st1K-grc1.xml', 'did.', False),
    ('hermas.pastor', f'{F1K}/tlg1419/tlg001/tlg1419.tlg001.1st1K-grc1.xml', 'herm.', True),
    ('justin_martyr.apologia_i', f'{F1K}/tlg0645/tlg001/tlg0645.tlg001.1st1K-grc1.xml', 'just. 1 apol.', False),
    ('justin_martyr.apologia_ii', f'{F1K}/tlg0645/tlg002/tlg0645.tlg002.perseus-grc2.xml', 'just. 2 apol.', False),
    ('justin_martyr.dialogus_cum_tryphone', f'{F1K}/tlg0645/tlg003/tlg0645.tlg003.perseus-grc2.xml', 'just. dial.', False),
    ('athenagoras.legatio', f'{F1K}/tlg1205/tlg001/tlg1205.tlg001.perseus-grc2.xml', 'athenag. leg.', False),
    ('athenagoras.de_resurrectione', f'{F1K}/tlg1205/tlg002/tlg1205.tlg002.perseus-grc2.xml', 'athenag. res.', False),
    ('theophilus_of_antioch.ad_autolycum', f'{F1K}/tlg1725/tlg001/tlg1725.tlg001.perseus-grc2.xml', 'theoph. autol.', True),
    ('tatian.oratio_ad_graecos', f'{F1K}/tlg1766/tlg001/tlg1766.tlg001.perseus-grc1.xml', 'tat. orat.', False),
    ('athanasius.de_incarnatione', f'{F1K}/tlg2035/tlg002/tlg2035.tlg002.1st1K-grc1.xml', 'ath. inc.', False),
    ('athanasius.contra_arianos_i', f'{F1K}/tlg2035/tlg130/tlg2035.tlg130.1st1K-grc1.xml', 'ath. c. ar. 1', False),
    ('athanasius.contra_arianos_ii', f'{F1K}/tlg2035/tlg131/tlg2035.tlg131.1st1K-grc1.xml', 'ath. c. ar. 2', False),
    ('athanasius.contra_arianos_iii', f'{F1K}/tlg2035/tlg132/tlg2035.tlg132.1st1K-grc1.xml', 'ath. c. ar. 3', False),
    ('athanasius.contra_arianos_iv', f'{F1K}/tlg2035/tlg117/tlg2035.tlg117.1st1K-grc1.xml', 'ath. c. ar. 4', False),
    ('john_of_damascus.barlaam_et_ioasaph', f'{CGL}/tlg2934/tlg066/tlg2934.tlg066.perseus-grc2.xml', 'barl. ioas.', True),
    ('enoch.apocalypsis_enochi', f'{F1K}/tlg1463/tlg001/tlg1463.tlg001.1st1K-grc1.xml', 'enoch', False),
]
for n, name, tag in [
        ('001', 'encomium_constantii', 'jul. enc. const.'), ('002', 'encomium_eusebiae', 'jul. enc. eus.'),
        ('003', 'de_gestis_imperatoris', 'jul. gest. imp.'), ('004', 'consolatio_de_discessu_salustii', 'jul. cons.'),
        ('005', 'ad_atheniensis', 'jul. ad ath.'), ('006', 'ad_themistium', 'jul. ad them.'),
        ('007', 'ad_heraclium_cynicum', 'jul. ad heracl.'), ('008', 'in_matrem_deorum', 'jul. matr.'),
        ('009', 'contra_cynicos_ineruditos', 'jul. cyn.'), ('010', 'caesares', 'jul. caes.'),
        ('011', 'in_regem_solem', 'jul. sol.'), ('012', 'misopogon', 'jul. mis.'),
        ('013', 'epistulae', 'jul. ep.'), ('017', 'contra_galilaeos', 'jul. gal.')]:
    WORKS.append((f'julian.{name}', f'{CGL}/tlg2003/tlg{n}/tlg2003.tlg{n}.perseus-grc2.xml', tag, False))

# Irenaeus (tlg1447.tlg001, Harvey 1857) is left out: Harvey's critical notes
# stand inside the running text of the file, with Latin sigla and numerals.
# Hermas ends at Similitude 9.30.2: the Greek manuscript stops there and
# Lake's text continues in Latin, which the OCR read as Greek letters.
# Dio: Orations 1 to 80 only. The TEI also holds an "appendix1" fragment and the
# numbered pieces 84 to 88 (fragments and spurious pieces), left out. The Perseus
# Greek has no Orations 14 to 18 at all.
EXTRA = {'hermas.pastor': ['--stop-before', '26.30.3'],
         'dio_chrysostom.orationes': ['--drop-top', 'appendix1', '84', '85', '86', '87', '88']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    bad = 0
    for stem, rel, tag, split in WORKS:
        if a.only and stem not in a.only:
            continue
        cmd = [sys.executable, os.path.join(HERE, 'perseus_greek_tei_to_tess.py'),
               os.path.join(a.src, rel), os.path.join(a.out, stem + '.tess'), '--tag', tag]
        if split:
            cmd += ['--parts-dir', a.out]
        cmd += EXTRA.get(stem, [])
        print('==', stem, flush=True)
        r = subprocess.run(cmd)
        if r.returncode:
            bad += 1
            print(f'   exit {r.returncode}', flush=True)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
