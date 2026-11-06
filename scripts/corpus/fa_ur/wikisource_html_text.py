#!/usr/bin/env python3
"""Turn Wikisource parser HTML (wikisource_fetch.py output) into paragraphs.

Standard library only. Drops the page header and navigation, page-number marks,
footnote references and reference lists, tables of contents, edit links and
anything marked noprint. Block elements (p, div, dd, dt, li, tr, h1 to h6, br)
end a paragraph. Returns a list of (kind, text) with kind 'h' for headings.
"""

import html
import re
from html.parser import HTMLParser

BLOCK = {"p", "div", "dd", "dt", "dl", "li", "ul", "ol", "tr", "table", "br", "blockquote", "center"}
HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_CLASS = re.compile(
    r"(^|\s)(noprint|ws-noexport|mw-editsection|reference|references|toc|pagenum|ws-pagenum|"
    r"prp-pagequality-\d|prp-page-qualityheader|mw-empty-elt|navbox|hatnote|metadata|"
    r"magnify|thumb|sisitem|sisicon|header-mainblock|mw-references-wrap)(\s|$)"
)
SKIP_ID = {"headerContainer", "plainSister", "ws-data", "toc", "footer", "footerContainer"}
SKIP_TAGS = {"script", "style", "sup", "noscript", "img"}
VOID = {"br", "img", "hr", "meta", "link", "input", "wbr"}


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []  # (kind, text)
        self.cur = []
        self.kind = "p"
        self.stack = []  # (tag, skip)
        self.skip_depth = 0

    def flush(self):
        t = re.sub(r"\s+", " ", "".join(self.cur)).strip()
        if t:
            self.out.append((self.kind, t))
        self.cur = []
        self.kind = "p"

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        skip = (
            tag in SKIP_TAGS
            or (a.get("class") and SKIP_CLASS.search(a["class"]))
            or a.get("id") in SKIP_ID
            or "display:none" in (a.get("style") or "").replace(" ", "")
        )
        if tag in VOID:
            if tag == "br" and not self.skip_depth:
                self.flush()
            return
        self.stack.append((tag, bool(skip)))
        if skip:
            self.skip_depth += 1
            return
        if tag in BLOCK or tag in HEAD:
            self.flush()
        if tag in HEAD:
            self.kind = "h"

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        # pop to the matching open tag
        while self.stack:
            t, skip = self.stack.pop()
            if skip:
                self.skip_depth -= 1
            if t == tag:
                break
        if not self.skip_depth and (tag in BLOCK or tag in HEAD):
            self.flush()

    def handle_data(self, data):
        if not self.skip_depth:
            self.cur.append(data)


def paragraphs(raw_html):
    p = P()
    p.feed(raw_html)
    p.flush()
    return [(k, html.unescape(t)) for k, t in p.out]
