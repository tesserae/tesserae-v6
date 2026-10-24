#!/bin/bash
# The Shahnameh with its stories, and Warner's public-domain translation aligned to it.
# Built 2026-10-23 on copies; nothing here touches /var/www. Run each step as its own tess-job.
#
# Inputs (all downloaded into $B, a scratch folder; nothing is committed):
#   $B/downloads/ganjoor_meta/   fetch_cats.py then fetch_poems.py   (api.ganjoor.net: 61 reigns, 857 stories, 99,220 verses)
#   $B/downloads/warner/volN.txt the OCR text (_djvu.txt) of archive.org items shahnama01firduoft ... shahnama09firduoft
#                                (University of Toronto scans of the nine volumes, 1905 to 1925)
# Steps 1 to 3 build the restructured text from the text now on the site (OLD_TESS):
#   build_seq.py      the Ganjoor verses in one sequence            -> $B/ganjoor_seq.json
#   cmp_fuzzy.py      line-by-line comparison with OLD_TESS         -> $B/fuzzy_align.json
#   build_structure.py  tags <ferdowsi.shahnameh.S.C.H>, the old-to-new map and the story list
#                                                                    -> $B/ferdowsi.shahnameh.new.tess, old_to_new_refs.json, stories_raw.json
# The text itself stays OLD_TESS's (orthography and all); only the tags change.
# Then the pipeline below: parse Warner's table of contents, find the headings, cut the volumes into
# sections, match stories to sections, align within each match, learn a word list, repeat twice.
# At the end: titles_prepare.py, build_stories_json.py (stories.json, old_to_new_refs.json).
set -e -o pipefail
B=${1:?scratch folder}; R=$(cd "$(dirname "$0")/../../.." && pwd)
PY=${PY:-$R/venv/bin/python}; J=~/bin/tess-job; S=$R/scripts/translations/shahnameh_warner; A=$R/scripts/translations/align_shahnameh_warner.py
$J --fg sh-toc 2 $PY -I $S/parse_toc.py $B
$J --fg sh-loc 3 $PY -I $S/locate_sections.py $B
$J --fg sh-seg 2 $PY -I $S/segment_warner.py $B
$J --fg sh-m0 3 $PY -I $S/match_stories.py $B 0.12 0.30 0.10 0.06 12 "" 1.6 0.5 0.06
$J --fg sh-a0 3 $PY -I $A --work $B --tess $B/ferdowsi.shahnameh.new.tess --out-dir $B/outputs
cp $B/outputs/fa__ferdowsi.shahnameh.json $B/pass1.json
$J --fg sh-l1 3 $PY -I $S/induce_lexicon.py --tess $B/ferdowsi.shahnameh.new.tess --translation $B/pass1.json --out $B/lexicon1.json
$J --fg sh-m1 3 $PY -I $S/match_stories.py $B 0.12 0.30 0.10 0.06 12 $B/lexicon1.json 1.6 0.5 0.06
$J --fg sh-a1 4 $PY -I $A --work $B --tess $B/ferdowsi.shahnameh.new.tess --out-dir $B/outputs --lexicon $B/lexicon1.json
cp $B/outputs/fa__ferdowsi.shahnameh.json $B/pass2.json
$J --fg sh-l2 3 $PY -I $S/induce_lexicon.py --tess $B/ferdowsi.shahnameh.new.tess --translation $B/pass2.json --out $B/lexicon2.json
$J --fg sh-m2 3 $PY -I $S/match_stories.py $B 0.12 0.30 0.10 0.06 12 $B/lexicon2.json 1.6 0.5 0.06
$J --fg sh-a2 4 $PY -I $A --work $B --tess $B/ferdowsi.shahnameh.new.tess --out-dir $B/outputs --lexicon $B/lexicon2.json
$J --fg sh-t1 1 $PY -I $S/titles_prepare.py $B
$J --fg sh-t2 1 $PY -I $S/build_stories_json.py $B $B/outputs
