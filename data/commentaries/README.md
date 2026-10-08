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

## Adding more

Further commentaries can be installed by placing more files in this same
format into `data/commentaries/` on the server; no code change is
needed, since `commentary_at()` reads every file in the directory by its
work id regardless of who installed it.
