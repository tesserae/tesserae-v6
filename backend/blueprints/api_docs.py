"""
Tesserae V6 - API Documentation Blueprint
Serves public API documentation at /api/docs
"""
from flask import Blueprint, jsonify, render_template_string

api_docs_bp = Blueprint('api_docs', __name__)

API_DOCUMENTATION = {
    "title": "Tesserae V6 API",
    "version": "6.0",
    "description": "Public API for the Tesserae intertextual analysis platform. Access text parallels, corpus data, and visualization endpoints.",
    "base_url": "/api",
    "endpoints": {
        "Search": [
            {
                "method": "POST",
                "path": "/search",
                "description": "Run intertextual search between two texts",
                "parameters": {
                    "source": "string - Source text ID",
                    "target": "string - Target text ID",
                    "language": "string - Language code (la, grc, en)",
                    "source_language": "string - Source text language (for cross-lingual)",
                    "target_language": "string - Target text language (for cross-lingual)",
                    "settings": {
                        "match_type": "string - Match algorithm: lemma, exact, sound, edit_distance, semantic, semantic_cross, dictionary_cross",
                        "min_matches": "integer - Minimum matching words (default: 2)",
                        "stoplist_basis": "string - Stoplist source: source_target, source, target, corpus",
                        "source_unit_type": "string - Unit type: line, phrase",
                        "target_unit_type": "string - Unit type: line, phrase",
                        "max_distance": "integer - Maximum word distance (default: 10)",
                        "max_results": "integer - Maximum results to return"
                    }
                },
                "returns": "Array of matched text parallels with scores"
            },
            {
                "method": "POST",
                "path": "/search/line",
                "description": "Search for a specific line across the corpus",
                "parameters": {
                    "text": "string - Text to search for",
                    "language": "string - Language code",
                    "match_type": "string - Match algorithm",
                    "target_text_id": "string - Optional specific target text"
                },
                "returns": "Array of matching lines with scores"
            },
            {
                "method": "POST",
                "path": "/search/string",
                "description": "Full-text string search across corpus",
                "parameters": {
                    "query": "string - Search query",
                    "language": "string - Language code"
                },
                "returns": "Array of matching passages"
            }
        ],
        "Corpus": [
            {
                "method": "GET",
                "path": "/texts/<language>",
                "description": "Get list of all texts in a language",
                "parameters": {
                    "language": "string (URL param) - Language code: la, grc, en"
                },
                "returns": "Array of text metadata (id, author, work, era)"
            },
            {
                "method": "GET",
                "path": "/text/<language>/<text_id>",
                "description": "Get full content of a specific text",
                "parameters": {
                    "language": "string (URL param) - Language code",
                    "text_id": "string (URL param) - Text filename"
                },
                "returns": "Text content with line-by-line data"
            },
            {
                "method": "GET",
                "path": "/authors/<language>",
                "description": "Get list of authors with their works",
                "parameters": {
                    "language": "string (URL param) - Language code"
                },
                "returns": "Array of authors with works and era information"
            },
            {
                "method": "GET",
                "path": "/texts/hierarchy/<language>",
                "description": "Get hierarchical structure of texts grouped by author",
                "parameters": {
                    "language": "string (URL param) - Language code"
                },
                "returns": "Nested structure of authors and their works"
            },
            {
                "method": "GET",
                "path": "/author-dates",
                "description": "Get author date/era information for all authors",
                "returns": "Object mapping author names to date/era metadata"
            }
        ],
        "Authentication & User": [
            {
                "method": "GET",
                "path": "/auth/user",
                "description": "Get current authenticated user information",
                "auth": "Requires session authentication",
                "returns": "User profile data or null if not authenticated"
            },
            {
                "method": "GET",
                "path": "/auth/profile",
                "description": "Get user profile with ORCID and preferences",
                "auth": "Requires session authentication",
                "returns": "User profile including ORCID, display name, and settings"
            },
            {
                "method": "POST",
                "path": "/auth/orcid/link",
                "description": "Link ORCID identifier to user profile",
                "auth": "Requires session authentication",
                "parameters": {
                    "orcid": "string - ORCID identifier (format: 0000-0000-0000-0000)"
                },
                "returns": "Updated profile with linked ORCID"
            },
            {
                "method": "POST",
                "path": "/auth/orcid/unlink",
                "description": "Remove ORCID link from user profile",
                "auth": "Requires session authentication",
                "returns": "Updated profile without ORCID"
            },
            {
                "method": "GET",
                "path": "/auth/saved-searches",
                "description": "Get user's saved search configurations",
                "auth": "Requires session authentication",
                "returns": "Array of saved search objects"
            },
            {
                "method": "POST",
                "path": "/auth/saved-searches",
                "description": "Save a new search configuration",
                "auth": "Requires session authentication",
                "parameters": {
                    "name": "string - Search name",
                    "source_text_id": "string - Source text ID",
                    "target_text_id": "string - Target text ID",
                    "settings": "object - Search settings"
                },
                "returns": "Created saved search with ID"
            },
            {
                "method": "DELETE",
                "path": "/auth/saved-searches/<id>",
                "description": "Delete a saved search",
                "auth": "Requires session authentication",
                "returns": "Success message"
            }
        ],
        "Utility": [
            {
                "method": "GET",
                "path": "/health",
                "description": "Health check endpoint for monitoring",
                "returns": "Status object with ok/error state"
            },
            {
                "method": "POST",
                "path": "/check-meter",
                "description": "Analyze metrical scansion of Latin poetry",
                "parameters": {
                    "text": "string - Latin text to scan",
                    "meter": "string - Expected meter type (hexameter, pentameter, etc.)"
                },
                "returns": "Scansion analysis with syllable breakdown"
            }
        ],
        "Hapax & Rare Words": [
            {
                "method": "POST",
                "path": "/hapax/search",
                "description": "Find rare words (hapax legomena) shared between texts",
                "parameters": {
                    "source_text_id": "string - Source text ID",
                    "target_text_id": "string - Target text ID",
                    "language": "string - Language code",
                    "max_frequency": "integer - Maximum corpus frequency (default: 1)"
                },
                "returns": "Array of shared rare words with locations"
            },
            {
                "method": "GET",
                "path": "/hapax/rare-words/<language>",
                "description": "Browse rare words across the corpus",
                "parameters": {
                    "language": "string (URL param) - Language code",
                    "max_frequency": "integer - Maximum frequency threshold",
                    "page": "integer - Page number",
                    "per_page": "integer - Results per page"
                },
                "returns": "Paginated list of rare words with occurrences"
            }
        ],
        "Batch Processing & Visualization": [
            {
                "method": "GET",
                "path": "/batch/jobs",
                "description": "List all batch processing jobs",
                "parameters": {
                    "page": "integer - Page number (default: 1)",
                    "per_page": "integer - Results per page (default: 20)",
                    "status": "string - Filter by status: pending, running, completed, failed"
                },
                "returns": "Paginated list of batch jobs with progress"
            },
            {
                "method": "GET",
                "path": "/batch/jobs/<job_id>",
                "description": "Get details of a specific batch job",
                "parameters": {
                    "job_id": "integer (URL param) - Job ID"
                },
                "returns": "Job details including thresholds, progress, and connection count"
            },
            {
                "method": "POST",
                "path": "/batch/jobs",
                "description": "Create a new batch job (admin only)",
                "auth": "Requires X-Admin-Password header",
                "parameters": {
                    "name": "string - Job name (required)",
                    "description": "string - Job description",
                    "job_type": "string - Job type: composite, lemma, semantic, sound",
                    "language": "string - Language code",
                    "thresholds": "object - Custom thresholds for composite scoring"
                },
                "returns": "Created job ID and status"
            },
            {
                "method": "DELETE",
                "path": "/batch/jobs/<job_id>",
                "description": "Delete a batch job (admin only)",
                "auth": "Requires X-Admin-Password header",
                "returns": "Success message"
            },
            {
                "method": "GET",
                "path": "/batch/connections",
                "description": "Query pre-computed text connections for network visualization",
                "parameters": {
                    "language": "string - Language code (default: la)",
                    "min_strength": "float - Minimum connection strength",
                    "min_tier": "string - Minimum confidence: gold, silver, bronze",
                    "source_era": "string - Filter by source text era",
                    "target_era": "string - Filter by target text era",
                    "author": "string - Filter by author name (partial match)",
                    "batch_job_id": "integer - Filter by batch job",
                    "page": "integer - Page number (default: 1)",
                    "per_page": "integer - Results per page (default: 100, max: 1000)"
                },
                "returns": "Paginated list of text connections with parallel counts"
            },
            {
                "method": "GET",
                "path": "/batch/connections/<connection_id>/parallels",
                "description": "Get individual parallels for a text connection (drill-down)",
                "parameters": {
                    "connection_id": "integer (URL param) - Connection ID",
                    "tier": "string - Filter by confidence tier: GOLD, SILVER, BRONZE",
                    "min_score": "float - Minimum composite score",
                    "limit": "integer - Maximum results (default: 100)"
                },
                "returns": "List of individual parallels with source/target text"
            },
            {
                "method": "GET",
                "path": "/batch/network/nodes",
                "description": "Get aggregated node data for network graph visualization",
                "parameters": {
                    "language": "string - Language code (default: la)",
                    "type": "string - Node type: author, work (default: author)",
                    "batch_job_id": "integer - Filter by batch job"
                },
                "returns": "List of nodes with in-degree, out-degree, and era metadata"
            },
            {
                "method": "GET",
                "path": "/batch/era-flow",
                "description": "Get era-to-era flow data for Sankey diagram",
                "parameters": {
                    "language": "string - Language code (default: la)",
                    "min_connections": "integer - Minimum connections to include (default: 1)",
                    "batch_job_id": "integer - Filter by batch job"
                },
                "returns": "List of era pairs with flow strength and counts"
            },
            {
                "method": "GET",
                "path": "/batch/centrality",
                "description": "Get centrality rankings for works or authors",
                "parameters": {
                    "language": "string - Language code (default: la)",
                    "type": "string - Ranking type: cited (in-degree), citing (out-degree)",
                    "entity": "string - Entity type: work, author (default: work)",
                    "limit": "integer - Number of results (default: 50)",
                    "batch_job_id": "integer - Filter by batch job"
                },
                "returns": "Ranked list of most cited/citing works or authors"
            }
        ],
        "Intertext Repository": [
            {
                "method": "GET",
                "path": "/intertexts",
                "description": "Browse public intertext repository",
                "parameters": {
                    "page": "integer - Page number",
                    "per_page": "integer - Results per page",
                    "language": "string - Filter by language",
                    "source_author": "string - Filter by source author",
                    "target_author": "string - Filter by target author"
                },
                "returns": "Paginated list of curated intertexts"
            },
            {
                "method": "POST",
                "path": "/intertexts",
                "description": "Submit a new intertext to the repository",
                "auth": "Requires user authentication",
                "parameters": {
                    "source_text_id": "string",
                    "source_reference": "string",
                    "source_snippet": "string",
                    "target_text_id": "string",
                    "target_reference": "string",
                    "target_snippet": "string",
                    "matched_lemmas": "array",
                    "score": "float",
                    "notes": "string"
                },
                "returns": "Created intertext ID"
            }
        ],
        "Downloads": [
            {
                "method": "GET",
                "path": "/downloads/results/<format>",
                "description": "Export search results",
                "parameters": {
                    "format": "string (URL param) - Export format: csv, json, xml"
                },
                "returns": "Downloadable file with search results"
            }
        ]
    },
    "scoring": {
        "description": "Composite scoring for high-confidence parallel detection",
        "signals": [
            {
                "name": "Lemma",
                "threshold": "≥7 matching lemmas",
                "description": "Dictionary-normalized word matching"
            },
            {
                "name": "Semantic",
                "threshold": "≥0.7 cosine similarity",
                "description": "Neural embedding similarity (SPhilBERTa for Latin/Greek, MiniLM for English)"
            },
            {
                "name": "Sound",
                "threshold": "≥0.6 phonetic similarity",
                "description": "Phonetic transcription matching"
            }
        ],
        "confidence_tiers": [
            {"tier": "GOLD", "signals": 3, "description": "All three signals confirm the parallel"},
            {"tier": "SILVER", "signals": 2, "description": "Two signals confirm the parallel"},
            {"tier": "BRONZE", "signals": 1, "description": "One signal confirms the parallel"}
        ]
    },
    "eras": [
        "Archaic",
        "Classical", 
        "Hellenistic",
        "Republic",
        "Augustan",
        "Early Imperial",
        "Later Imperial",
        "Late Antique",
        "Early Medieval"
    ]
}


@api_docs_bp.route('/docs', methods=['GET'])
def get_api_docs_html():
    """Render API documentation as HTML page"""
    html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tesserae V6 API Documentation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .endpoint { transition: all 0.2s; }
        .endpoint:hover { transform: translateX(4px); }
        pre { white-space: pre-wrap; word-wrap: break-word; }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
    <div class="max-w-5xl mx-auto px-4 py-8">
        <header class="mb-12">
            <h1 class="text-4xl font-bold text-amber-400 mb-2">{{ docs.title }}</h1>
            <p class="text-gray-400">Version {{ docs.version }}</p>
            <p class="text-gray-300 mt-4">{{ docs.description }}</p>
            <p class="text-gray-500 mt-2">Base URL: <code class="bg-gray-800 px-2 py-1 rounded">{{ docs.base_url }}</code></p>
            <div class="mt-4">
                <a href="/api/docs.json" class="text-amber-400 hover:text-amber-300">Download JSON specification →</a>
            </div>
        </header>
        
        {% for category, endpoints in docs.endpoints.items() %}
        <section class="mb-10">
            <h2 class="text-2xl font-semibold text-amber-300 mb-4 border-b border-gray-700 pb-2">{{ category }}</h2>
            {% for endpoint in endpoints %}
            <div class="endpoint bg-gray-800 rounded-lg p-4 mb-4">
                <div class="flex items-center gap-3 mb-2">
                    <span class="px-2 py-1 rounded text-sm font-mono {% if endpoint.method == 'GET' %}bg-green-700{% elif endpoint.method == 'POST' %}bg-blue-700{% elif endpoint.method == 'DELETE' %}bg-red-700{% else %}bg-gray-700{% endif %}">
                        {{ endpoint.method }}
                    </span>
                    <code class="text-amber-200">{{ endpoint.path }}</code>
                    {% if endpoint.auth %}
                    <span class="px-2 py-1 bg-yellow-700 rounded text-xs">🔒 Auth Required</span>
                    {% endif %}
                </div>
                <p class="text-gray-300 mb-3">{{ endpoint.description }}</p>
                
                {% if endpoint.parameters %}
                <div class="mt-3">
                    <h4 class="text-sm font-semibold text-gray-400 mb-2">Parameters:</h4>
                    <div class="bg-gray-900 rounded p-3 text-sm">
                        {% if endpoint.parameters is mapping %}
                            {% for key, value in endpoint.parameters.items() %}
                                {% if value is mapping %}
                                <div class="mb-2">
                                    <code class="text-amber-300">{{ key }}</code>:
                                    <div class="ml-4">
                                    {% for subkey, subvalue in value.items() %}
                                        <div><code class="text-gray-400">{{ subkey }}</code>: <span class="text-gray-300">{{ subvalue }}</span></div>
                                    {% endfor %}
                                    </div>
                                </div>
                                {% else %}
                                <div class="mb-1"><code class="text-amber-300">{{ key }}</code>: <span class="text-gray-300">{{ value }}</span></div>
                                {% endif %}
                            {% endfor %}
                        {% endif %}
                    </div>
                </div>
                {% endif %}
                
                {% if endpoint.returns %}
                <div class="mt-3">
                    <h4 class="text-sm font-semibold text-gray-400 mb-1">Returns:</h4>
                    <p class="text-gray-300 text-sm">{{ endpoint.returns }}</p>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </section>
        {% endfor %}
        
        <section class="mb-10">
            <h2 class="text-2xl font-semibold text-amber-300 mb-4 border-b border-gray-700 pb-2">Composite Scoring</h2>
            <p class="text-gray-300 mb-4">{{ docs.scoring.description }}</p>
            
            <h3 class="text-lg font-semibold text-gray-300 mb-2">Signal Thresholds</h3>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                {% for signal in docs.scoring.signals %}
                <div class="bg-gray-800 rounded-lg p-4">
                    <h4 class="font-semibold text-amber-200">{{ signal.name }}</h4>
                    <p class="text-sm text-amber-400">{{ signal.threshold }}</p>
                    <p class="text-sm text-gray-400 mt-1">{{ signal.description }}</p>
                </div>
                {% endfor %}
            </div>
            
            <h3 class="text-lg font-semibold text-gray-300 mb-2">Confidence Tiers</h3>
            <div class="space-y-2">
                {% for tier in docs.scoring.confidence_tiers %}
                <div class="flex items-center gap-3">
                    <span class="px-3 py-1 rounded font-semibold {% if tier.tier == 'GOLD' %}bg-yellow-600{% elif tier.tier == 'SILVER' %}bg-gray-500{% else %}bg-amber-800{% endif %}">
                        {{ tier.tier }}
                    </span>
                    <span class="text-gray-300">{{ tier.signals }} signal(s) — {{ tier.description }}</span>
                </div>
                {% endfor %}
            </div>
        </section>
        
        <section class="mb-10">
            <h2 class="text-2xl font-semibold text-amber-300 mb-4 border-b border-gray-700 pb-2">Era Classifications</h2>
            <div class="flex flex-wrap gap-2">
                {% for era in docs.eras %}
                <span class="px-3 py-1 bg-gray-800 rounded text-gray-300">{{ era }}</span>
                {% endfor %}
            </div>
        </section>
        
        <footer class="text-gray-500 text-sm border-t border-gray-700 pt-6 mt-12">
            <p>Tesserae V6 — Intertextual Analysis Platform</p>
            <p>For support, visit <a href="/help" class="text-amber-400 hover:text-amber-300">Help & Support</a></p>
        </footer>
    </div>
</body>
</html>
'''
    return render_template_string(html_template, docs=API_DOCUMENTATION)


@api_docs_bp.route('/docs.json', methods=['GET'])
def get_api_docs_json():
    """Return API documentation as JSON"""
    return jsonify(API_DOCUMENTATION)
