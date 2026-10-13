import { greekToLatin, hebrewToLatin, SCRIPT_SPAN, GREEK_START, HEBREW_START, hasOriginalScript } from '../../utils/transliterate';
import { useTransliteration } from '../../utils/transliterationSetting';

/** Text with each Greek or Hebrew span in its own letters, followed by a
 *  transliteration from a fixed table when the reader has them on. Other
 *  text passes through unchanged. */
export default function OriginalScript({ text }) {
  const on = useTransliteration();
  const s = String(text ?? '');
  if (!hasOriginalScript(s)) return s;
  return s.split(SCRIPT_SPAN).map((part, k) => {
    if (HEBREW_START.test(part)) {
      const t = hebrewToLatin(part);
      return (
        <span key={k}>
          <span lang="he" dir="rtl" className="font-greek">{part}</span>
          {on && t !== part && <span className="text-gray-500">{` (${t})`}</span>}
        </span>
      );
    }
    if (GREEK_START.test(part)) {
      const t = greekToLatin(part);
      return (
        <span key={k}>
          <span lang="grc" className="font-greek">{part}</span>
          {on && t !== part && <span className="text-gray-500">{` (${t})`}</span>}
        </span>
      );
    }
    return part;
  });
}
