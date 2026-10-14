#!/usr/bin/env bash
# Content scan of a built public bundle (2026-10-11). The builder selects files
# by an allow-list and refuses forbidden names, but neither reads file contents.
# This step unpacks the archive into a scratch folder and searches every file.
#
#   scan_bundle_secrets.sh ARCHIVE.tar.zst [SCRATCH_DIR]
#
# Tier 1 (the build fails): a private-key header, our settings variable names,
# a database connection string, the shapes of well-known API keys, or a file
# named like a settings file, key, dump or credential.
# Tier 2 (reported for a human to read, never fails): ordinary words that can
# also name secrets ("secret:", "token:", "password:", "passphrase", "Bearer").
# On the 2026-10-11 full bundle tier 2 matched 34 files, all ordinary prose
# (Jerome, the Bible, Shakespeare, Frontinus's watchwords, a Coptic translation).
set -uo pipefail
A=${1:?archive}; D=${2:-$(mktemp -d /tmp/bundle-scan.XXXXXX)}
mkdir -p "$D" && tar --zstd -xf "$A" -C "$D" || { echo "SCAN: cannot unpack $A"; exit 2; }
T1='BEGIN [A-Z ]*PRIVATE KEY|SESSION_SECRET|ADMIN_PASSWORD|DATABASE_URL|postgres(ql)?://|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}'
T2='api[_-]?key|apikey|Bearer [A-Za-z0-9_-]{20,}|passphrase|password[[:space:]]*[:=]|passwd[[:space:]]*[:=]|secret[[:space:]]*[:=]|token[[:space:]]*[:=]'
echo "SCAN: $(find "$D" -type f | wc -l) files unpacked from $(basename "$A")"
# MANIFEST.tsv holds hashes, whose hex can spell a key prefix by chance; it is
# checked only for the key-header and connection-string patterns.
t1=$( { grep -rIlE "$T1" "$D" --exclude=MANIFEST.tsv; grep -lE 'BEGIN [A-Z ]*PRIVATE KEY|postgres(ql)?://|SESSION_SECRET|ADMIN_PASSWORD' "$D/MANIFEST.tsv"; \
       find "$D" -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.npy' \) -print0 | xargs -0 grep -laE 'BEGIN [A-Z ]*PRIVATE KEY|SESSION_SECRET|ADMIN_PASSWORD|postgres(ql)?://' ; } 2>/dev/null | sed "s#^$D/##" | sort -u)
names=$(find "$D" -type f \( -iname '*.env' -o -iname '.env*' -o -iname '*.pem' -o -iname '*.key' -o -iname '*secret*' -o -iname '*passw*' -o -iname '*credential*' -o -iname '*.sql' -o -iname '*passphrase*' \) | sed "s#^$D/##")
t2=$(grep -rIlE "$T2" "$D" 2>/dev/null | sed "s#^$D/##" | sort -u)
rm -rf "$D"
echo "SCAN tier 2 (ordinary words that can name secrets; read, do not act): $(printf '%s\n' "$t2" | grep -c .) files"
printf '%s\n' "$t2" | grep . | sed 's/^/  /'
if [[ -n "$t1" || -n "$names" ]]; then
  echo "SCAN FAILED: tier 1 content or file names"; printf '%s\n' "$t1" "$names" | grep . | sed 's/^/  /'; exit 1
fi
echo "SCAN OK: no tier 1 content, no file named like a settings file, key, dump or credential"
