#!/bin/bash
cd /home/ncoffee/tesserae-v6-dev
echo "Scheduled overnight rebuild. Waiting until 1:00 AM EDT..."
echo "Current time: $(date)"

target=$(date -d "tomorrow 01:00" +%s 2>/dev/null || date -d "01:00" +%s)
now=$(date +%s)
if [ $target -le $now ]; then
    target=$(date -d "tomorrow 01:00" +%s)
fi
wait_seconds=$((target - now))
echo "Sleeping $wait_seconds seconds (until $(date -d @$target))..."
sleep $wait_seconds

echo ""
echo "========================================="
echo "Starting overnight rebuild at $(date)"
echo "========================================="
source venv/bin/activate

echo ""
echo "=== Phase 1: Greek lemma caches + index (660 texts) ==="
python scripts/rebuild_greek_lemma_caches.py 2>&1 | tee /tmp/greek_rebuild.log

echo ""
echo "=== Phase 2: Persian inverted index (19 poets, 936K verses) ==="
python scripts/build_inverted_index.py --language fa --force 2>&1 | tee /tmp/persian_rebuild.log

echo ""
echo "=== Phase 3: Rebuild Urdu-Persian dictionary from lemmatized indexes ==="
python scripts/rebuild_urdu_persian_dict.py 2>&1 | tee /tmp/urdu_persian_dict.log

echo ""
echo "=== Phase 4: Clear search caches ==="
rm cache/*.json 2>/dev/null
echo "Caches cleared"

echo ""
echo "========================================="
echo "Rebuild complete at $(date)"
echo "========================================="

echo "Restarting dev server..."
pkill -f "python.*main.py" 2>/dev/null
sleep 2
source venv/bin/activate && set -a && source .env && set +a
nohup python3 main.py > /tmp/tesserae_dev.log 2>&1 &
echo "Server restarted. PID: $!"
