#!/usr/bin/env bash
# Production run of the thirty-seven work renames (research/corpus list of
# 2026-10-18: 36 Greek-titled works and Ferdowsi's Shahnameh).
#
# Usage (after the pull request is merged, deployed, and the text files pulled):
#   scripts/corpus/rename_batch_2026-10-18.sh LOGFILE            # dry run of every row
#   scripts/corpus/rename_batch_2026-10-18.sh LOGFILE --apply    # dry run, then apply, per row
#
# For each row it runs rename_work.py twice (dry run, then --apply) and stops at the
# first non-zero exit. Without --apply it runs the dry runs only and writes nothing.
# Run it through ~/bin/tess-job, with a backup of every store taken first.
# ROOT defaults to the production checkout; override with TESSERAE_ROOT.
set -u
export PYTHONUTF8=1 LC_ALL=C.UTF-8
LOG="${1:?usage: $0 LOGFILE [--apply]}"
MODE="${2:-}"
ROOT="${TESSERAE_ROOT:-/var/www/tesseraev6_flask}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-/home/ncoffee/tesserae-v6-dev/venv/bin/python}"
TOOL="$REPO/scripts/corpus/rename_work.py"

# language <TAB> old id <TAB> new id <TAB> display title
read -r -d '' ROWS <<'TSV'
grc	aelian.ἀποσπασμάτια	aelian.fragmenta	Fragmenta
grc	aelius_herodianus.περι_καθολικης_προσῳδιας	aelius_herodianus.de_prosodia_catholica	De prosodia catholica
grc	aeschines_sp.ἐπιστολαί	aeschines_sp.epistulae	Epistulae
grc	aesop.αισώπειων_μύθων_συναγωγή	aesop.fabularum_collectio	Fabularum collectio
grc	alcidamas.ὀδυσσεύς	alcidamas.odysseus	Odysseus
grc	alcidamas.περὶ_σοφιστῶν	alcidamas.de_sophistis	De sophistis
grc	antisthenes.αἴας	antisthenes.aiax	Aiax
grc	antisthenes.ὀδυσσεύς	antisthenes.odysseus	Odysseus
grc	apollonius_dyscolus.περὶ_ἀντωνυμίας	apollonius_dyscolus.de_pronominibus	De pronominibus
grc	aristotle.αριστοτέλους_φυσικά_προβλήματα_κατ_εἶδος_συναγώγης	aristotle.problemata	Problemata
grc	aristotle.ἐκ_τοῦ_περὶ_ἀκουστῶν	aristotle.de_audibilibus	De audibilibus
grc	aristotle.μηχανικά	aristotle.mechanica	Mechanica
grc	aristotle.περί_χρωμάτων	aristotle.de_coloribus	De coloribus
grc	aristotle.φυσιογνωμονικά	aristotle.physiognomonica	Physiognomonica
grc	claudius_ptolemaeus.μαθηματικὴ_σύνταξις	claudius_ptolemaeus.syntaxis_mathematica	Syntaxis mathematica (Almagest)
grc	cleonides.εἰσαγωγὴ_ἁρμονική	cleonides.introductio_harmonica	Introductio harmonica
grc	diogenianus_of_heraclea.παροιμίαι_δημώδεις_ἐκ_τῆς_διογενιανοῦ_συναγωγῆς_e_	diogenianus_of_heraclea.paroemiae	Paroemiae
grc	galen.περὶ_τῶν_ἐν_ταῖς_τροφαῖς_δυνάμεων	galen.de_alimentorum_facultatibus	De alimentorum facultatibus
grc	gorgias_of_leontini.ἑλένης_ἐγκώμιον	gorgias_of_leontini.helenae_encomium	Helenae encomium
grc	gorgias_of_leontini.ὑπέρ_παλαμήδους_ἀπολογία	gorgias_of_leontini.palamedis_defensio	Palamedis defensio
grc	hermogenes.περὶ_τῶν_στάσεων	hermogenes.de_statibus	De statibus
grc	herodianus.συμπόσιον	herodianus.symposium	Symposium
grc	nicomachus_of_gerasa.ἀριθμητικὴ_εἰσαγωγή	nicomachus_of_gerasa.introductio_arithmetica	Introductio arithmetica
grc	nicomachus_of_gerasa.ἐγχειρίδιον_ἁρμονικῆς	nicomachus_of_gerasa.harmonices_enchiridion	Harmonices enchiridion
grc	plutarch.παροιμίαι_αἷς_ἀλεξανδρεῖς_ἐχρῶντο	plutarch.proverbia_alexandrinorum	Proverbia Alexandrinorum
grc	pseudolucian.ἀλκυών	pseudolucian.halcyon	Halcyon
grc	pseudolucian.δημοσθένους_ἐγκώμιον	pseudolucian.demosthenis_encomium	Demosthenis encomium
grc	pseudolucian.ἔρωτες	pseudolucian.amores	Amores
grc	pseudolucian.κυνικός	pseudolucian.cynicus	Cynicus
grc	pseudolucian.λούκιος_ἢ_ὄνος	pseudolucian.asinus	Asinus
grc	pseudolucian.φιλόπατρις_ἢ_διδασκόμενος	pseudolucian.philopatris	Philopatris
grc	pseudolucian.χαρίδημος_ἢ_περὶ_κάλλους	pseudolucian.charidemus	Charidemus
grc	theophrastus.περί_ὀσμών	theophrastus.de_odoribus	De odoribus
grc	theophrastus.περὶ_φυτῶν_αἰτιῶν	theophrastus.de_causis_plantarum	De causis plantarum
grc	tryphon_i_grammaticus.περὶ_τρόπων	tryphon_i_grammaticus.de_tropis	De tropis
grc	zenobius_sophista.ἐπιτομὴ_ἐκ_τῶν_ταρραίου_καὶ_διδύμου_παροιμιῶν_συντ	zenobius_sophista.epitome_proverbiorum	Epitome proverbiorum
fa	ferdowsi.diwan	ferdowsi.shahnameh	Shahnameh
TSV

run() {
  echo "+ $*" | tee -a "$LOG"
  "$@" 2>&1 | tee -a "$LOG"
  local rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    echo "STOP: exit $rc from: $*" | tee -a "$LOG"
    exit "$rc"
  fi
}

echo "== rename batch 2026-10-18 started $(date) root=$ROOT mode=${MODE:-dry-run}" | tee -a "$LOG"
while IFS=$'\t' read -r lang old new title; do
  [ -z "$lang" ] && continue
  extra=()
  case "$old" in
    antisthenes.*) extra=(--old-tag "antisthenes." --new-tag "$new") ;;
  esac
  echo "== $lang $old -> $new ($title)" | tee -a "$LOG"
  run "$PY" "$TOOL" --root "$ROOT" --language "$lang" --old "$old" --new "$new" "${extra[@]}"
  if [ "$MODE" = "--apply" ]; then
    run "$PY" "$TOOL" --root "$ROOT" --language "$lang" --old "$old" --new "$new" "${extra[@]}" --apply
  fi
done <<< "$ROWS"
echo "== all rows done $(date)" | tee -a "$LOG"

cat <<'CHECKLIST' | tee -a "$LOG"

Follow-up steps (not run by this script), as in the Thucydides record:
  [ ] Passage index: rename_work_in_passage_index.py in leaf mode per work if the
      rename tool did not move it (title changes), then the lockstep check
      (ids, descriptions, vectors, window_texts counts in step; no old id left).
  [ ] data/passage_index/works_by_language.json: replace each old id by hand
      (the tool does not update it), with a dated backup.
  [ ] Reuse table work columns (cache/reuse_pairs/grc.db and fa.db): UPDATE
      line_counts.work, pairs.work_a, pairs.work_b on a copy, integrity check,
      swap in with a dated backup. Confirm the columns in backend/reuse_table.py.
  [ ] Citation indexes by hand (citations.db, citations_muse.db, toolkit sources):
      UPDATE citations SET work_id, with backups.
  [ ] scripts/build_desc_fts.py, scripts/corpus/build_desc_vocab.py,
      scripts/corpus/build_window_names.py (to a .new file, swapped in);
      touch tesseraev6_flask.wsgi after each.
  [ ] Lockstep check, one Similar Passages request, one Theme Search request,
      one Greek Line Search; "arma virum" returns Ovid, Quintilian, Seneca.
  [ ] scripts/review/golden_api.py: re-record the requests the rename alters.
  [ ] Connections map (scripts/build_connections_map.py, cap 10G) and density
      cache (scripts/precompute_passage_density.py --language all).
  [ ] curl .../api/languages after the wsgi touch.
CHECKLIST
