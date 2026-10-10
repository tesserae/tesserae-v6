"""Connector parity manifest.

Maps every PUBLIC Tesserae API route (as filtered by tests/test_mcp_parity.py)
to either the connector tool(s) in backend/blueprints/mcp_http.py TOOLS that
cover it, or to SITE_ONLY with a one-line reason the connector doesn't need
it. Written 2026-09-10 against the route set on main at that date.

THE POINT of this file: tests/test_mcp_parity.py fails when a public route
exists that appears in neither this manifest nor the exclusion list a route
walk applies. That means whoever adds a new public API route must, in the
same PR, add a line here saying what the connector does about it -- either
name the tool that already covers it, name a new tool, or write down why a
browser-only feature (a chart, a file export, a login-gated action) doesn't
need one. The alternative -- the connector silently drifting behind the site,
discovered only when someone compares them by hand -- is what this replaces
(five such gaps were found by hand on 2026-09-10; see PROGRESS on
feat/connector-parity).

Entry shapes:
    {"tools": ["tool_name", ...]}                  -- covered, optionally +"note"
    {"site_only": True, "reason": "..."}            -- not exposed, and why

Keys are Flask rule strings exactly as they appear in app.url_map (e.g.
'/api/texts', '/api/text/<path:text_id>'), matching str(rule).
"""

MANIFEST = {
    # -- Covered by a connector tool -------------------------------------------------
    # The backend PR (adding /api/scholarship) lands these same two routes as
    # placeholder site_only entries, since it does not touch this file's
    # tools. This PR is what makes the tools real: find_scholarship and
    # get_commentary are defined in mcp_http.py TOOLS unconditionally (so
    # this manifest and the parity tests stay consistent either way) but
    # hidden from tools/list and refused by tools/call unless
    # TESSERAE_SCHOLARSHIP_TOOLS=1 is set; see _visible_tools() there.
    '/api/scholarship': {
        'tools': ['find_scholarship'],
    },
    '/api/scholarship/commentary': {
        'tools': ['get_commentary'],
    },
    '/api/scholarship/sources': {
        'site_only': True,
        'reason': 'Credits list for the Sources page (every commentator, edition, licence); the notes themselves come through get_commentary.',
    },
    '/api/scholarship/translate': {
        'site_only': True,
        'reason': "A machine translation of one commentary note for the Reader's tab; an agent reads the Latin from get_commentary.",
    },
    '/api/languages': {
        'tools': ['get_languages'],
    },
    '/api/corpus-version': {
        'site_only': True,
        'reason': 'The date stamp for the Cite popup; connector tools already return corpus_version with their counts.',
    },
    '/api/texts': {
        'tools': ['list_texts'],
    },
    '/api/authors': {
        'tools': ['list_texts'],
        'note': ("Author-grouped view of the same per-language text listing "
                "list_texts already exposes flat, with id/author/work/title."),
    },
    '/api/line-search': {
        'tools': ['line_search'],
    },
    '/api/documents/<doc_id>': {
        'site_only': True,
        'reason': ('Document Reader view (stage 3b-3): website trial behind '
                    '?documents=1, not yet exposed to the connector.'),
    },
    '/api/events': {
        'site_only': True,
        'reason': ('Events page (battles, sieges, treaties) in testing: reads '
                    'an offline dossier database; not yet exposed to the connector.'),
    },
    '/api/events/<event_id>': {
        'site_only': True,
        'reason': ('Event focus view in testing: one dossier from the offline '
                    'dossier database; not yet exposed to the connector.'),
    },
    '/api/coins': {
        'site_only': True,
        'reason': ('Coins page (OCRE and CRRO type records) in testing: reads an '
                    'offline database; not yet exposed to the connector.'),
    },
    '/api/coins/facets': {
        'site_only': True,
        'reason': ('Filter values and counts for the Coins page in testing; not yet '
                    'exposed to the connector.'),
    },
    '/api/coins/for-passage': {
        'site_only': True,
        'reason': ('Reader Coins tab in testing: related coin imagery and name links for a '
                    'passage; not yet exposed to the connector.'),
    },
    '/api/coins/theme': {
        'site_only': True,
        'reason': ('Coins option of Theme Search in testing: coin descriptions nearest a '
                    'free-text query; not yet exposed to the connector.'),
    },
    '/api/coins/<path:coin_id>': {
        'site_only': True,
        'reason': ('One coin type for the Coins page in testing; not yet exposed to '
                    'the connector.'),
    },
    '/api/objects': {
        'site_only': True,
        'reason': ('Objects page (museum catalogue descriptions) in testing: reads an '
                    'offline database; not yet exposed to the connector.'),
    },
    '/api/objects/facets': {
        'site_only': True,
        'reason': ('Filter values and counts for the Objects page in testing; not yet '
                    'exposed to the connector.'),
    },
    '/api/objects/theme': {
        'site_only': True,
        'reason': ('Objects option of Theme Search in testing: object descriptions nearest a '
                    'free-text query; not yet exposed to the connector.'),
    },
    '/api/objects/<path:object_id>': {
        'site_only': True,
        'reason': ('One object for the Objects page in testing; not yet exposed to '
                    'the connector.'),
    },
    '/api/documents/<doc_id>/scholarship': {
        'site_only': True,
        'reason': ('Journal sentences and commentary notes citing one document, for the '
                    'document page: licensed scholarship shown as citation, excerpt and link '
                    'on the site; not exposed to the connector.'),
    },
    '/api/documents/browse': {
        'site_only': True,
        'reason': ('Documents section of Browse Corpus: facet tree (kind, '
                    'region, century) for the website trial behind '
                    '?documents=1, not yet exposed to the connector.'),
    },
    '/api/wildcard-search': {
        'tools': ['string_search'],
    },
    '/api/passages/theme-search': {
        'tools': ['theme_search'],
    },
    '/api/passages/lines': {
        'tools': ['get_passage'],
    },
    '/api/passages/similar': {
        'tools': ['similar_passages'],
    },
    '/api/passages/compare': {
        'tools': ['theme_compare'],
    },
    '/api/passages/pair-lift': {
        'tools': ['theme_pair_lift'],
    },
    '/api/passages/translation': {
        'tools': ['get_passage'],
        'note': "get_passage(translation=true) calls this route for the fetched lines' refs.",
    },
    '/api/translation': {
        'tools': ['get_passage'],
        'note': "Same view function as /api/passages/translation (dual route registration).",
    },
    '/api/rare-bigram-search': {
        'tools': ['rare_pairs', 'compare_texts'],
    },
    '/api/hapax-search': {
        'tools': ['rare_words', 'compare_texts'],
    },
    '/api/fusion-search': {
        'tools': ['fusion_search', 'compare_texts', 'evidence_summary'],
        'note': ("The GET poll route all three tools share (fusion_search calls it "
                "directly; compare_texts and evidence_summary reuse its cached path)."),
    },
    '/api/text-descriptions': {
        'tools': ['describe_text'],
    },
    '/api/author-dates': {
        'tools': ['describe_text'],
    },
    '/api/feature-request': {
        'tools': ['submit_feature_request'],
        'note': ("Requests workflow (2026-10-08): the same route and tool also file "
                "result-problem/text-correction/suggestion, the three entry points added "
                "on the website. submit_feature_request's type/title/problem/desired/"
                "example/context/contact fields already pass through unchanged."),
    },
    # Listed here even though the route-walk's own segment rule excludes anything
    # with a 'requests' or 'feedback' path segment: a human reading this file for
    # "did the requests workflow get a parity decision" should find one instead of
    # concluding it was missed.
    '/api/requests': {
        'site_only': True,
        'reason': ("Public mirror of the GitHub issues /api/feature-request files (the "
                  "Requests page): a read-only listing with short public summaries, not "
                  "something an agent asks about on a caller's behalf."),
    },
    '/api/provenance': {
        'tools': ['describe_text'],
        'note': ("describe_text's 'source' field is spec'd to read backend/text_sources.json "
                "(the Sources-page dataset, matched on author+work) rather than this route's "
                "backend/text_provenance.json (a separate, smaller per-import-batch record "
                "keyed cleanly by filename). Both answer 'where did this text come from'; "
                "only the former is wired in. Folding provenance.json in as a fallback would "
                "raise describe_text's coverage -- flagged, not done, in the parity report."),
    },
    '/api/usage/page': {
        'site_only': True,
        'reason': ('The browser records which pages one visit opened, for the admin panel\'s '
                   'paths section; a connector client has no pages to record.'),
    },
    '/api/sources-credits': {
        'site_only': True,
        'reason': ('Site copy for the Text Credits page (one record per source, licence and '
                   'version); a connector client reads each text\'s own credit through describe_text.'),
    },
    '/api/text-credits': {
        'tools': ['describe_text'],
        'note': ("describe_text exposes one text's Sources-page entry from the same "
                "text_sources.json this route paginates/searches across all texts."),
    },
    # Listed even though the route-walk's own suffix rule excludes it (it ends
    # in -poll): unlike every OTHER *-poll route, this is cross_language's ONLY
    # endpoint, not a secondary poll variant alongside a primary POST route (the
    # gap fusion-search avoids by not carrying the suffix at all). Named here so
    # the reverse tools->routes check does not report cross_language as an
    # orphan tool.
    '/api/crosslingual-search-poll': {
        'tools': ['cross_language'],
    },

    # -- SITE_ONLY: visual / chart / network -----------------------------------------
    '/api/comparison-chart': {
        'site_only': True,
        'reason': 'Renders a PNG/SVG chart image; visual, not representable as tool output.',
    },
    '/api/comparison-history-chart': {
        'site_only': True,
        'reason': 'Chart image (timeline of a comparison); visual.',
    },
    '/api/comparison-map-chart': {
        'site_only': True,
        'reason': 'Chart image (connection map of a comparison); visual.',
    },
    '/api/batch/centrality': {
        'site_only': True,
        'reason': 'Precomputed network-centrality data for the corpus Network page; visual.',
    },
    '/api/batch/compute-connections': {
        'site_only': True,
        'reason': 'Triggers the heavy batch job that builds the Network page graph.',
    },
    '/api/batch/connections': {
        'site_only': True,
        'reason': 'Precomputed network edges for the Network page; visual.',
    },
    '/api/batch/connections/<int:connection_id>/parallels': {
        'site_only': True,
        'reason': ("Drill-down parallels for one Network-page edge; reachable only via a "
                  "connection_id from browsing that graph, which no tool exposes."),
    },
    '/api/batch/era-flow': {
        'site_only': True,
        'reason': 'Era-to-era flow chart data for the Network page; visual.',
    },
    '/api/batch/network/nodes': {
        'site_only': True,
        'reason': 'Network graph node list for the Network page; visual.',
    },
    '/api/lexical-density': {
        'site_only': True,
        'reason': "Reader's lexical-density metric for a passage; a visual reading aid.",
    },
    '/api/passages/lexical-density': {
        'site_only': True,
        'reason': 'Same handler as /api/lexical-density (dual route registration).',
    },
    '/api/passages/density': {
        'site_only': True,
        'reason': "Per-window connection counts that feed the Reader's margin gutter; visual.",
    },
    '/api/reuse/line': {
        'site_only': True,
        'reason': ("Lines from other works that verbatim-repeat one specific line, for the "
                  "Reader's Reuse tab; a corpus-wide table keyed to a single line/ref the "
                  "Reader is showing, not a search a tool caller runs independently. Latin "
                  "only as of 2026-09-19 (cache/reuse_pairs/la.db)."),
    },
    '/api/passages/map': {
        'site_only': True,
        'reason': ('Corpus connections map heatmap matrix (authors/works/centuries/genres) '
                  'for the Theme Search "Map" view; a canvas visualization, not tool output.'),
    },
    '/api/passages/map/cell': {
        'site_only': True,
        'reason': 'Drill-down list behind one connections-map matrix cell; reachable only by clicking the heatmap.',
    },
    '/api/passages/map/pair': {
        'site_only': True,
        'reason': ('Passage pairs behind one connections-map work pair, with Reader deep links; '
                  'reachable only from the map UI, and similar_passages already answers the '
                  'underlying "what resembles this passage" question for a tool caller.'),
    },
    '/api/passages/map/work': {
        'site_only': True,
        'reason': ('One work\'s connections-map row, for the map\'s "start from one work" picker; '
                  'a corpus-browsing aid, not something a tool caller asks for by work id.'),
    },
    '/api/passages/map/books': {
        'site_only': True,
        'reason': ('Books x books heatmap for one connections-map work pair, the third nested-grid '
                  'drill-down level; reachable only by clicking through the map UI.'),
    },
    '/api/rare-word-cloud': {
        'site_only': True,
        'reason': 'Word-cloud visualization data (sizes/weights for rendering); visual.',
    },
    '/api/reuse/marks': {
        'site_only': True,
        'reason': ("Per-line reuse counts for a visible range, feeding the Reader's margin "
                  "'quoted in N works' marks; a rendering aid keyed to what is on screen, "
                  "not something a tool caller asks for independently."),
    },

    # -- SITE_ONLY: produces a file ----------------------------------------------------
    '/api/passages/export': {
        'site_only': True,
        'reason': 'Produces a CSV/JSON file download of a Theme Search run.',
    },
    '/api/intertexts/export': {
        'site_only': True,
        'reason': 'Produces a CSV file download of the public intertext repository.',
    },
    '/api/rare-lemmata-full/export': {
        'site_only': True,
        'reason': 'Produces a CSV file download of the rare-word listing.',
    },

    # -- SITE_ONLY: needs a logged-in scholar ------------------------------------------
    '/api/intertexts': {
        'site_only': True,
        'reason': ("GET lists/POST creates entries in the scholar-curated Saved Parallels "
                  "repository; creating one needs a login, and browsing curated entries is "
                  "a site feature the connector doesn't replicate."),
    },
    '/api/intertexts/<int:intertext_id>': {
        'site_only': True,
        'reason': 'Single saved-parallel entry; same repository as /api/intertexts.',
    },
    '/api/intertexts/expand-lemmas': {
        'site_only': True,
        'reason': 'Form helper for the (login-gated) saved-parallel entry-creation form.',
    },
    '/api/intertexts/stats': {
        'site_only': True,
        'reason': 'Repository dashboard counts for the Saved Parallels page.',
    },

    # -- SITE_ONLY: corpus-wide browsing (the tools need a source+target pair) --------
    '/api/rare-bigrams': {
        'site_only': True,
        'reason': ("Corpus-wide rare-bigram browsing for the Rare Words Explorer; "
                  "rare_pairs needs a source+target text pair."),
    },
    '/api/rare-lemmata': {
        'site_only': True,
        'reason': ("Corpus-wide rare-word browsing (computed); "
                  "rare_words needs a source+target text pair."),
    },
    '/api/rare-lemmata-full': {
        'site_only': True,
        'reason': "Same browsing, from a pre-cached instant-load variant; rare_words needs a pair.",
    },
    '/api/rare-word-locations/<lemma>': {
        'site_only': True,
        'reason': ("Every corpus location of one lemma, for the Rare Words Explorer; "
                  "rare_words answers the two-text version of this question."),
    },
    '/api/lemma-forms/<lemma>': {
        'site_only': True,
        'reason': 'Surface-form lookup helper for the search UI; not exposed as a standalone tool.',
    },

    # -- SITE_ONLY: Tessa, the site's own embedded assistant ---------------------------
    '/api/assistant/analyze': {
        'site_only': True,
        'reason': ("Tessa (the site's local small-model assistant) narrates computed findings "
                  "for browser visitors; a connector caller already narrates over tool results "
                  "itself, and evidence_summary exposes the same computed facts this reads."),
    },
    '/api/assistant/guide': {
        'site_only': True,
        'reason': "Tessa's canned/model Q&A about how to use the site, for browser visitors.",
    },
    '/api/assistant/status': {
        'site_only': True,
        'reason': "Whether Tessa's local model server is up; UI status indicator.",
    },

    # -- SITE_ONLY: legacy / unused / superseded ---------------------------------------
    '/api/corpus-search': {
        'site_only': True,
        'reason': ("Lemma co-occurrence search via the inverted index; unreferenced by the "
                  "current client (client/src/utils/api.js defines searchCorpusForLemmas but "
                  "nothing calls it) and superseded by /line-search, which line_search covers."),
    },
    '/api/line-search-parallel': {
        'site_only': True,
        'reason': ("Alternate single-line-vs-corpus search; unreferenced by the current client "
                  "(the Reader's Verbal Parallels tab uses /api/line-search instead, per its "
                  "own comment) and superseded by /line-search, which line_search covers."),
    },
    '/api/search': {
        'site_only': True,
        'reason': ("Classic single-channel (lemma/exact/sound/edit_distance/...) two-text "
                  "search predating fusion; fusion_search's ten (eleven) channels supersede "
                  "it for the connector's comparison tools."),
    },
    '/api/search-fusion': {
        'site_only': True,
        'reason': ("POST SSE-streaming variant for the browser's live progress bar; "
                  "fusion_search polls GET /fusion-search instead, sharing the same cache."),
    },
    '/api/search-results/<result_id>': {
        'site_only': True,
        'reason': ("Later pages of a browser search that asked for page_size; fusion_search "
                  "already pages its own results with offset/limit on GET /fusion-search."),
    },
    '/api/search-results/<result_id>/export': {
        'site_only': True,
        'reason': "Feeds the results page's CSV/PDF export buttons with every stored row.",
    },

    # -- SITE_ONLY: settings / config / ops --------------------------------------------
    '/api/stoplist': {
        'site_only': True,
        'reason': 'Saves a custom stopword list for the classic search settings panel.',
    },
    '/api/stoplists': {
        'site_only': True,
        'reason': 'Named preset stoplists for the classic search settings panel.',
    },
    '/api/check-meter': {
        'site_only': True,
        'reason': "Whether a text pair suits metrical analysis; toggles the site's use_meter control.",
    },
    '/api/fusion-default-weights': {
        'site_only': True,
        'reason': ("Reference data behind the Advanced settings panel's weight sliders; "
                  "fusion_search's `weights` parameter already documents the channel names."),
    },
    '/api/frequencies/<language>': {
        'site_only': True,
        'reason': 'Top-N corpus word-frequency listing for a stats/dashboard display.',
    },
    '/api/frequencies/recalculate': {
        'site_only': True,
        'reason': 'Triggers a heavy corpus-frequency recomputation job.',
    },
    '/api/corpus-status': {
        'site_only': True,
        'reason': 'Corpus expansion changelog/history for the About page.',
    },
    '/api/stats': {
        'site_only': True,
        'reason': "Corpus text-count dashboard numbers; redundant with list_texts/get_languages.",
    },
    '/api/health': {
        'site_only': True,
        'reason': 'Liveness probe.',
    },
    '/api/version': {
        'site_only': True,
        'reason': 'Build/version info from git, for the footer.',
    },
    '/api/texts/hierarchy': {
        'site_only': True,
        'reason': ("Author -> work -> part tree for the Browse Corpus page; list_texts already "
                  "exposes the flat listing a tool caller needs."),
    },
    '/api/texts/add': {
        'site_only': True,
        'reason': 'Adds a text to the corpus; gated by check_admin_auth internally.',
    },
    '/api/texts/preview': {
        'site_only': True,
        'reason': 'Formatting-preview helper for the (admin-gated) text-add form.',
    },
    '/api/request': {
        'site_only': True,
        'reason': ("Text-request form that accepts a raw file attachment; submit_feature_request "
                  "covers a structured text/feature/bug request without a file, which is the "
                  "part a connector caller can act on."),
    },
    '/api/passages/status': {
        'site_only': True,
        'reason': 'Passage-index availability/size; an operational status display.',
    },
    '/api/passages/translation-full': {
        'site_only': True,
        'reason': ("Whole-work translation in reading order, for the Reader's translation-focus "
                  "view; get_passage(translation=true) covers a specific passage, which fits "
                  "an agent's retrieval need better than an unbounded whole-work dump."),
    },
    '/api/passages/translations': {
        'site_only': True,
        'reason': ("Corpus-browse listing of which works have aligned translations, for Browse "
                  "Corpus badges; get_passage(translation=true) already reports per-passage "
                  "availability, which is what a retrieval-minded caller needs."),
    },
    '/api/passages/works': {
        'site_only': True,
        'reason': ("Corpus-browse listing of which works have passage windows at all, for the "
                  "Browse Corpus Theme Search badge; theme_search and similar_passages already "
                  "report per-query and per-passage coverage, which is what a retrieval-minded "
                  "caller needs."),
    },
    '/api/text/<path:text_id>': {
        'site_only': True,
        'reason': ("Raw whole-work text dump (every unit) for the corpus text viewer; "
                  "get_passage returns bounded excerpts by design, which fits the connector's "
                  "response-size budget where an unbounded whole-work dump would not."),
    },
    '/api/text/<path:text_id>/book-for': {
        'site_only': True,
        'reason': ("Reader navigation: which book file of a whole-file work holds a line, so "
                  "the Reader opens that book; get_passage takes any work id and range directly."),
    },
    '/api/text/<path:text_id>/lines': {
        'site_only': True,
        'reason': ("Older raw line-browsing endpoint for the corpus text viewer, without the "
                  "author/title/citation framing get_passage adds for the ranges a caller asks for."),
    },
}
