# Fonts bundled for PDF export

`NotoSansCoptic-Regular.ttf` — Copyright 2022 The Noto Project Authors,
SIL Open Font License 1.1 (https://scripts.sil.org/OFL). 90 KB.

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
