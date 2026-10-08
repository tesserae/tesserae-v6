# Commentaries

Public-domain commentary notes the Reader's Scholarship tab reads at a
line span, via `backend/scholarship.commentary_at()`. One JSON file per
commentator and work (`<commentator>__<work>.json`, or
`<commentator>__<work>.part.<n>.json` for a part), each self-describing
its own edition, source and licence in the file.

## What is here

Servius on Vergil (`servius__vergil.aeneid.json`,
`servius__vergil.eclogues.json`, `servius__vergil.georgics.json`;
14,205 notes). Text: Georgius Thilo and Hermannus Hagen, eds., *Servii
Grammatici qui feruntur in Vergilii carmina commentarii* (Leipzig: B. G.
Teubner, 1878-1902), via the Perseus Digital Library's open-source TEI
distribution. Licence: Creative Commons Attribution-ShareAlike 3.0 United
States (CC BY-SA 3.0 US). Each file carries the exact source URL and
commit.

## What is not here

The preview build (`research/threads/SCHOLARSHIP_PREVIEW_STATE.md`)
installed a much larger catalogue: the rest of the Perseus commentary
collection, Sefaria's Tanakh commentators, Matthew Henry, and several
English literary editions assembled from scanned, OCR'd public-domain
books. That set runs to several hundred megabytes and mixes licences file
by file, so it was not brought into this repository. See
`research/threads/SCHOLARSHIP_PORT_NOTES.md` for where the files live and
how to install them on a server that wants the fuller set; no code change
is needed, since `commentary_at()` reads every file in this directory by
its work id regardless of who installed it.
