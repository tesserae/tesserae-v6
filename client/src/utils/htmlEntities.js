/**
 * Decode the few HTML entities that turn up in stored catalogue strings
 * (for example "Ginn &amp; Co."). Only the named entities that occur in
 * the text-source records and numeric references are handled. Angle
 * brackets are left alone on purpose, so a stray tag fragment stays inert text.
 */
const NAMED = { amp: '&', quot: '"', apos: "'", nbsp: ' ' };

export function decodeEntities(s) {
  if (s === null || s === undefined) return s;
  return String(s).replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, body) => {
    if (body[0] === '#') {
      const code = body[1].toLowerCase() === 'x' ? parseInt(body.slice(2), 16) : parseInt(body.slice(1), 10);
      return Number.isFinite(code) && code > 0 && code < 0x110000 ? String.fromCodePoint(code) : m;
    }
    const v = NAMED[body.toLowerCase()];
    return v === undefined ? m : v;
  });
}
