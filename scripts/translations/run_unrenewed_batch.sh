#!/bin/bash
# Part F of the 2026-10-24 translation batch: every aligner, the opening repairs and the merges,
# in the order that was run. Staging lives in ~/tesserae-backups/tr_f_2026-10-24 (scans in its
# sub-folders, results in final/). Nothing here installs anything.
# Run it as: ~/bin/tess-job --fg partF 4 bash scripts/translations/run_unrenewed_batch.sh
set -euo pipefail
PY=${PY:-/home/ncoffee/tesserae-v6-dev/venv/bin/python}
S=${STAGING:-$HOME/tesserae-backups/tr_f_2026-10-24}
T=${TESSERAE_TEXTS:-/var/www/tesseraev6_flask/texts}
PROD=${PROD_TRANSLATIONS:-/var/www/tesseraev6_flask/data/translations}
D=scripts/translations
mkdir -p "$S/final/standalone" "$S/final/partial" "$S/final/separate" "$S/final/merged"

for a in nonnus pliny_elder josephus_antiquities dionysius_cary sextus minor_latin_poets prudentius_thomson silius_duff2 \
         ptolemy_tetrabiblos pausanias republic_shorey ennius_warmington; do
  echo "== align_$a"; $PY -I $D/align_$a.py || true
done

# the first page of a book carries no running header: recover the opening lines by position
$PY -I $D/repair_book_openings.py --json "$S/final/standalone/grc__nonnus_of_panopolis.dionysiaca.json" \
  --tess $T/grc/nonnus_of_panopolis.dionysiaca.tess --src "$S/nonnus02.txt" --src "$S/nonnus03.txt" --out "$S/rep.json"
mv "$S/rep.json" "$S/final/standalone/grc__nonnus_of_panopolis.dionysiaca.json"
for w in grattius.cynegetica calpurnius_siculus.eclogae; do
  $PY -I $D/repair_book_openings.py --json "$S/final/standalone/la__$w.json" --tess $T/la/$w.tess \
    --src "$S/mlp/mlp1.txt" --out "$S/rep.json"
  mv "$S/rep.json" "$S/final/standalone/la__$w.json"
done
$PY -I $D/repair_book_openings.py --json "$S/final/separate/la__silius_italicus.punica.json" \
  --tess $T/la/silius_italicus.punica.tess --src "$S/sil/s2.txt" --out "$S/rep.json"
mv "$S/rep.json" "$S/final/separate/la__silius_italicus.punica.json"

# the volumes' own headings (Duff's ARGUMENT of each book, the English title of a poem) are not translation
$PY -I $D/strip_book_summaries.py silius "$S/final/separate/la__silius_italicus.punica.json"
$PY -I $D/strip_book_summaries.py prudentius "$S/final/standalone/la__prudentius.peristephanon.json"

# lay the partial and separate alignments over the installed files, keeping both translators
for f in grc__flavius_josephus.antiquitates_judaicae la__pliny_the_elder.naturalis_historia; do
  $PY -I $D/merge_unit_sources.py "$PROD/$f.json" "$S/final/partial/$f.json" "$S/final/merged/$f.json"
done
$PY -I $D/merge_unit_sources.py "$PROD/la__silius_italicus.punica.json" \
  "$S/final/separate/la__silius_italicus.punica.json" "$S/final/merged/la__silius_italicus.punica.json"

(cd "$S/final" && find . -name '*.json' | sort | xargs sha256sum > SHA256SUMS.txt)
echo done
