# Fonts bundled for PDF export

`NotoSansCoptic-Regular.ttf` — Copyright 2022 The Noto Project Authors,
SIL Open Font License 1.1 (https://scripts.sil.org/OFL). 90 KB.

`NotoNaskhArabic-Variable.ttf` — Copyright 2022 The Noto Project Authors,
SIL Open Font License 1.1. 300 KB. The variable font from google/fonts
(`ofl/notonaskharabic/NotoNaskhArabic[wght].ttf`), whose default instance is
Regular. Used for Persian, Urdu and Arabic passages (added 2026-09-07): DejaVu
Sans has the Arabic letters but none of the Urdu ones (heh goal, yeh barree,
retroflex consonants) or their joined forms, so Urdu lines printed with boxes.
Noto Naskh Arabic carries every presentation form the reshaper produces.
Noto Nastaliq Urdu was tried first and rejected: it has no presentation-form
glyphs at all, so it cannot be used through arabic_reshaper.

## Why it lives here rather than on the machine

It was originally read from `~/.local/share/fonts/`, which worked in
development and would have failed in production without saying so. The web
server runs as `tess-flask`, `/home/ncoffee` is `drwxr-x---`, and `tess-flask`
is not in that group: the font is simply unreadable to it. `theme_pdf` would
have logged a warning, produced a PDF anyway, and drawn every Coptic passage as
empty boxes.

Caught by the automated review on PR #271, which asked whether the WSGI user
could read a path under a home directory. It could not.

The other scripts use DejaVu from `/usr/share/fonts`, which is system-wide and
readable by everyone, so only Coptic needed bundling.
