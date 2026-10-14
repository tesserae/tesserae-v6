"""Which user agents are automated clients, for the visit counts.

One list, used wherever visits are counted, so the figures agree.
"""

BOT_SUBSTRINGS = (
    'bot', 'crawl', 'spider', 'slurp', 'python-requests', 'python-urllib',
    'curl/', 'wget', 'go-http', 'headlesschrome', 'facebookexternalhit',
    'bytespider', 'gptbot', 'claudebot', 'amazonbot', 'petalbot',
    'semrushbot', 'ahrefsbot', 'scrapy', 'httpx', 'axios', 'node-fetch',
    'okhttp', 'java/', 'masscan', 'zgrab', 'censys', 'nuclei',
)


def is_bot(user_agent):
    """True when the user agent is empty, "-", or contains a known bot marker."""
    ua = (user_agent or '').strip().lower()
    if ua in ('', '-'):
        return True
    return any(s in ua for s in BOT_SUBSTRINGS)
