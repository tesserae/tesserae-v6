#!/bin/bash
# Encode the non-restricted description blobs on one campus GPU (research/threads/GPU_JOB_RECIPE.md). Prints the job name.
set -euo pipefail
W=/home/ncoffee/tesserae-backups/coptic_windows_2026-10-28
PROD=/var/www/tesseraev6_flask
SUF=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
JOB=cop-win-20261028-$SUF
mkdir -p $PROD/public_data/jobs/$JOB
cp $W/gpu_blobs.jsonl.gz $PROD/public_data/jobs/$JOB/blobs.jsonl.gz
cp $W/gpu/encode_job.py $PROD/public_data/jobs/$JOB/
cd $PROD
TOKEN=$(venv/bin/python scripts/jobs/new_upload_token.py $JOB)
~/bin/runai-login >/dev/null
~/bin/runai-cli training standard submit $JOB -p tesserae -i vllm/vllm-openai:latest \
  --gpu-devices-request 1 --cpu-memory-request 48G --cpu-memory-limit 48G --large-shm \
  --preemptibility non-preemptible \
  -e JOB_BASE=https://tesserae.caset.buffalo.edu/tesserae-data/jobs/$JOB \
  -e JOB_UPLOAD=https://tesserae.caset.buffalo.edu/api/jobs/upload/$JOB \
  -e JOB_TOKEN=$TOKEN -e JOB_PART=50000 \
  --command -- bash -c "cd /tmp && pip install -q sentence-transformers 2>&1 | tail -1; curl -sO \$JOB_BASE/encode_job.py && python3 encode_job.py" >/dev/null
echo "$JOB"
