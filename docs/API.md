# Tesserae V6 API Reference

Base URL: `/api`

## Authentication

Most endpoints are public. User-specific features require Replit Auth session.

---

## Core Search Endpoints

### POST `/api/search`
Run a parallel phrase search between source and target texts.

**Request Body:**
```json
{
  "source": "vergil.aeneid.part.1",
  "target": "lucan.bellum_civile.part.1",
  "match_type": "lemma",
  "source_unit_type": "line",
  "target_unit_type": "line",
  "stoplist_basis": "corpus",
  "stopwords": 10,
  "min_matches": 2,
  "max_distance": 10,
  "max_results": 500
}
```

**Parameters:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| source | string | required | Source text ID |
| target | string | required | Target text ID |
| match_type | string | "lemma" | Match type: lemma, exact, sound, semantic |
| source_unit_type | string | "line" | Unit type: line, phrase |
| target_unit_type | string | "line" | Unit type: line, phrase |
| stoplist_basis | string | "corpus" | Basis: corpus, source, target, source_target |
| stopwords | int | 10 | Number of stopwords to exclude |
| min_matches | int | 2 | Minimum matching words required |
| max_distance | int | 10 | Maximum distance between matches |
| max_results | int | 500 | Maximum results to return |

**Response:**
```json
{
  "results": [
    {
      "source_line": "<vergil.aeneid 1.1> Arma virumque cano...",
      "target_line": "<lucan.bellum_civile 1.1> Bella per...",
      "score": 8.45,
      "matching_words": ["arma", "bellum"],
      "source_loc": "1.1",
      "target_loc": "1.1"
    }
  ],
  "stats": {
    "elapsed": 1.23,
    "source_lines": 756,
    "target_lines": 830,
    "total_results": 142
  }
}
```

---

### POST `/api/line-search`
Search a single line against the entire corpus.

**Request Body:**
```json
{
  "line": "Arma virumque cano Troiae qui primus ab oris",
  "language": "la",
  "match_type": "lemma",
  "max_results": 100
}
```

**Response:**
```json
{
  "results": [
    {
      "text_id": "ovid.metamorphoses",
      "line": "<ovid.metamorphoses 1.1> In nova fert...",
      "score": 6.2,
      "matching_words": ["arma", "cano"]
    }
  ],
  "stats": {
    "elapsed": 0.45,
    "texts_searched": 1290
  }
}
```

---

### POST `/api/corpus-search`
Search for co-occurring lemmas across the corpus.

**Request Body:**
```json
{
  "lemmas": ["arma", "bellum"],
  "language": "la",
  "max_results": 100
}
```

---

## Hapax (Rare Words) Endpoints

### POST `/api/hapax-search`
Find rare words shared between two texts.

**Request Body:**
```json
{
  "source": "vergil.aeneid.part.1",
  "target": "ovid.metamorphoses.part.1",
  "max_frequency": 10,
  "language": "la"
}
```

---

### POST `/api/rare-bigram-search`
Find unique word pairs shared between texts.

**Request Body:**
```json
{
  "source": "vergil.aeneid.part.1",
  "target": "ovid.metamorphoses.part.1",
  "max_frequency": 5,
  "language": "la"
}
```

---

### GET `/api/rare-lemmata-full`
Browse rare vocabulary across a corpus language in pages.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| language | string | `la`, `grc`, or `en` (default: `la`) |
| max_occurrences | int | Maximum corpus frequency (default: 10) |
| offset | int | Zero-based result offset (default: 0) |
| limit | int | Page size: `25`, `50`, `100`, or `500` (default: 50) |
| sort_by | string | `frequency`, `lemma`, or `author` (default: `frequency`) |
| sort_order | string | `asc` or `desc` (default: `asc`) |

The response includes the requested `words` page and the total number of matching words.

### GET `/api/rare-lemmata-full/export`
Download all rare words matching the language, frequency, and sorting parameters as a CSV file. It accepts `language`, `max_occurrences`, `sort_by`, and `sort_order`; pagination parameters do not apply.

---

## Corpus Endpoints

### GET `/api/texts`
List all texts in the corpus.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| language | string | Filter by language: la, grc, en |

**Response:**
```json
{
  "texts": [
    {
      "id": "vergil.aeneid.part.1",
      "author": "Vergil",
      "title": "Aeneid",
      "language": "la",
      "year": -29
    }
  ]
}
```

### GET `/api/text-credits`
Browse the source credits for corpus texts in pages.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | Case-insensitive author or work filter (default: empty) |
| offset | int | Zero-based result offset (default: 0) |
| limit | int | Page size: `25`, `50`, `100`, or `500` (default: `50`) |

The response contains the requested `entries` page plus `total`, `offset`, and `limit` metadata.

---

### GET `/api/authors`
List all authors with their works.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| language | string | Filter by language |

---

### GET `/api/text/<text_id>`
Get full text content with metadata.

**Response:**
```json
{
  "id": "vergil.aeneid.part.1",
  "author": "Vergil",
  "title": "Aeneid",
  "lines": [
    {"loc": "1.1", "text": "Arma virumque cano..."}
  ],
  "total_lines": 756
}
```

---

### GET `/api/text/<text_id>/lines`
Get lines from a specific range.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| start | int | Starting line number |
| end | int | Ending line number |

---

## Intertext Repository

### GET `/api/intertexts`
List public intertexts from the repository.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| page | int | Page number (default: 1) |
| per_page | int | Results per page: `25`, `50`, `100`, or `500` (default: 50) |
| source_language | string | Filter by source language |
| sort_by | string | `created_at`, `score`, or `scholar_score` (default: `created_at`) |
| sort_order | string | `asc` or `desc` (default: `desc`) |

The response includes `total`, page metadata, and a `summary` for repository counts.

---

### POST `/api/intertexts`
Create a new intertext entry.

**Request Body:**
```json
{
  "source_text": "vergil.aeneid",
  "source_loc": "1.1",
  "source_line": "Arma virumque cano...",
  "target_text": "ovid.metamorphoses",
  "target_loc": "1.1",
  "target_line": "In nova fert animus...",
  "score": 4,
  "notes": "Both opening lines invoke epic themes",
  "is_public": true
}
```

---

### GET `/api/intertexts/my`
Get current user's saved intertexts. Requires authentication. It accepts the same paging, source-language, and sorting parameters as the public list, plus `visibility` (`all`, `shared`, or `private`).

---

### GET `/api/intertexts/export`
Export intertexts as CSV.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| format | string | Export format: csv |
| source_language | string | Filter by source language |
| sort_by | string | `created_at`, `score`, or `scholar_score` |
| sort_order | string | `asc` or `desc` |

### GET `/api/intertexts/my/export`
Export all of the current user's matching saved intertexts as CSV. Requires authentication and accepts `source_language`, `visibility`, `sort_by`, and `sort_order`.

---

## String Search

### POST `/api/wildcard-search`
Search for text patterns with wildcards.

**Request Body:**
```json
{
  "pattern": "arm* vir*",
  "language": "la",
  "case_sensitive": false,
  "max_results": 100
}
```

**Wildcards:**
- `*` - matches any characters
- `?` - matches single character
- `AND`, `OR`, `NOT` - boolean operators

---

## User & Authentication

### GET `/api/auth/user`
Get current authenticated user.

**Response:**
```json
{
  "authenticated": true,
  "user": {
    "id": "user123",
    "name": "Scholar Name",
    "orcid": "0000-0001-2345-6789"
  }
}
```

---

### GET `/api/auth/saved-searches`
Get user's saved searches.

---

### POST `/api/auth/saved-searches`
Save a search configuration.

**Request Body:**
```json
{
  "name": "Vergil-Ovid comparison",
  "source": "vergil.aeneid.part.1",
  "target": "ovid.metamorphoses.part.1",
  "settings": { ... }
}
```

---

### POST `/api/auth/orcid/link`
Link ORCID to user profile.

**Request Body:**
```json
{
  "orcid": "0000-0001-2345-6789"
}
```

---

## Admin Endpoints

All admin endpoints require password authentication via `/api/admin/login`.

### POST `/api/admin/login`
Authenticate as admin.

**Request Body:**
```json
{
  "password": "admin_password"
}
```

---

### GET `/api/admin/requests`
List pending text upload requests.

---

### POST `/api/admin/requests/<id>/approve`
Approve and add a submitted text to the corpus.

---

### POST `/api/frequencies/recalculate`
Recalculate corpus-wide word frequencies.

---

### GET `/api/admin/analytics`
Get usage analytics and statistics.

---

## Utility Endpoints

### GET `/api/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-23T12:00:00Z"
}
```

---

### GET `/api/stats`
Get corpus statistics.

**Response:**
```json
{
  "total_texts": 2100,
  "latin_texts": 1290,
  "greek_texts": 310,
  "english_texts": 500
}
```

---

### GET `/api/stoplists`
Get the current curated stoplists used by the primary matcher and displayed on the Help page. The lists are de-duplicated for display and do not include text-specific Zipf additions.

Each language also carries a `display` list, the same words in reading form and in the same order as `words`. For Greek this is the polytonic (accented) form; the matcher itself filters on the accentless `words`. For Latin and English `display` is identical to `words`.

**Response:**
```json
{
  "stoplists": {
    "la": { "label": "Latin", "words": ["et", "in"], "display": ["et", "in"], "count": 91 },
    "grc": { "label": "Greek", "words": ["και", "δε"], "display": ["καί", "δέ"], "count": 195 },
    "en": { "label": "English", "words": ["the", "be"], "display": ["the", "be"], "count": 189 }
  }
}
```

---

### POST `/api/stoplist`
Generate a stoplist for given texts.

**Request Body:**
```json
{
  "source": "vergil.aeneid.part.1",
  "target": "ovid.metamorphoses.part.1",
  "basis": "corpus",
  "count": 10
}
```

---

## Text Upload & Feedback

### POST `/api/request`
Submit a text for addition to the corpus.

**Request Body (multipart/form-data):**
| Field | Type | Description |
|-------|------|-------------|
| author | string | Author name (required) |
| work | string | Work title (required) |
| language | string | la, grc, or en |
| name | string | Submitter name (optional) |
| email | string | Contact email (optional) |
| notes | string | Additional notes (optional) |
| file | file | .txt or .tess file (optional) |

---

### POST `/api/feedback`
Submit user feedback or bug report.

**Request Body:**
```json
{
  "name": "User Name",
  "email": "user@example.com",
  "type": "suggestion",
  "message": "Feedback content..."
}
```

---

## Cache & Performance

### GET `/api/cache/stats`
Get cache statistics.

### POST `/api/cache/clear`
Clear the results cache (admin only).

---

## Batch Processing

### GET `/api/batch/jobs`
List batch processing jobs.

### POST `/api/batch/jobs`
Create a new batch job for processing multiple text pairs.

### GET `/api/batch/connections`
Get network connections between texts.

### GET `/api/batch/network/nodes`
Get network visualization data.

---

## Feature Weights

### GET `/api/features/weights`
Get current feature weights for scoring.

### POST `/api/features/weights`
Update feature weights.

### POST `/api/features/toggle`
Toggle specific features on/off.

---

## Search Concurrency & Queuing

Heavy searches (fusion, sound, edit distance, semantic, cross-lingual) are protected by a **concurrency gate** that limits how many run simultaneously. This prevents out-of-memory crashes when multiple users search at the same time.

### Streaming endpoints (`/api/search-stream`, `/api/search-fusion`)

When the server is busy, streaming endpoints emit `queued` SSE events before the search begins:

```
data: {"type": "queued", "step": "Search queued — server is busy", "detail": "Server is running 2 searches (max 2)", "wait_time": 4.2, "elapsed": 5.0}
```

The search starts automatically when a slot opens. If no slot opens within 5 minutes, an `error` event is sent.

**SSE event types** (in order):
| Event | When |
|-------|------|
| `queued` | Server is busy, search is waiting for a slot |
| `progress` | Search is running, status updates |
| `intermediate` | (Fusion only) Partial results after each channel |
| `complete` | Final results |
| `error` | Search failed or timed out in queue |

### Non-streaming endpoint (`/api/search`)

When the server is busy, the request blocks until a slot is available. If the queue timeout (5 minutes) is exceeded, a `503 Service Unavailable` response is returned:

```json
{"error": "Server busy: Search queue timeout after 300s: Server is running 2 searches (max 2)"}
```

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `TESSERAE_MAX_HEAVY_SEARCHES` | 2 | Maximum concurrent heavy searches |
| `TESSERAE_MEMORY_THRESHOLD_GB` | 8 | Minimum available RAM (GB) to start a search |
| `TESSERAE_LOCK_DIR` | `/tmp/tesserae_search_slots` | Directory for lock files |

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "error": "Error message description",
  "code": "ERROR_CODE"
}
```

Common HTTP status codes:
- `400` - Bad request (invalid parameters)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not found
- `500` - Server error
