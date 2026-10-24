"""Carry the Shahnameh's lemma cache over to the re-tagged text without lemmatizing again.

The re-tagged file keeps every line's text in the same order and changes only
the tags, so the per-line tokens, lemmas and tags of the existing cache are
still right. Lemmatizing 99,218 Persian lines again runs Stanza's neural
pipeline on the CPU for an hour or more. This script rewrites the refs of the
cached units through old_to_new_refs.json and stamps the new file's hash.

Phrase units carry range refs "A-B" and a line_refs list. Some of those ranges
end in "ferdowsi.diwan.N", a leftover of the work's rename, where N is a line
of this file; the trailing number is what is mapped.

Usage: remap_lemma_cache.py OLD_CACHE.json NEW_TESS OLD_TO_NEW.json OUT_CACHE.json
"""

import hashlib
import json
import re
import sys


def new_ref(old, mapping):
    """Map one old ref by its trailing running number."""
    m = re.search(r"(\d+)$", old)
    if not m:
        raise SystemExit(f"ref without a number: {old!r}")
    n = m.group(1)
    if n not in mapping:
        raise SystemExit(f"old line {n} is not in the map ({old!r})")
    return mapping[n]


def main():
    old_cache, new_tess, map_path, out_path = sys.argv[1:5]
    with open(old_cache, encoding="utf-8") as f:
        cache = json.load(f)
    with open(map_path, encoding="utf-8") as f:
        mapping = json.load(f)
    with open(new_tess, "rb") as f:
        new_hash = hashlib.md5(f.read()).hexdigest()  # nosec B324: the cache key, not a security hash
    with open(new_tess, encoding="utf-8") as f:
        tags = [line.split("\t", 1)[0].strip("<>") for line in f if line.strip()]

    lines = cache["units_line"]
    if len(lines) != len(tags):
        raise SystemExit(f"{len(lines)} cached lines but {len(tags)} in the new file")
    for unit, tag in zip(lines, tags):
        mapped = new_ref(unit["ref"], mapping)
        if mapped != tag:
            raise SystemExit(
                f"line order differs: {unit['ref']} -> {mapped}, file has {tag}"
            )
        unit["ref"] = mapped

    for unit in cache.get("units_phrase", []):
        if "-" in unit["ref"]:
            a, b = unit["ref"].split("-", 1)
            unit["ref"] = f"{new_ref(a, mapping)}-{new_ref(b, mapping)}"
        else:
            unit["ref"] = new_ref(unit["ref"], mapping)
        if "line_refs" in unit:
            unit["line_refs"] = [new_ref(r, mapping) for r in unit["line_refs"]]

    cache["file_hash"] = new_hash
    cache["remapped_from"] = old_cache
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    print(
        f"{len(lines)} line units and {len(cache.get('units_phrase', []))} phrase units written to {out_path}, file_hash {new_hash}"
    )


if __name__ == "__main__":
    main()
