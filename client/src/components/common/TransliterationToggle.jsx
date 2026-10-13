import { setOn, useTransliteration } from '../../utils/transliterationSetting';

/** The text button that turns the transliterations on the written paragraphs off and on. */
export default function TransliterationToggle() {
  const on = useTransliteration();
  return (
    <button type="button" onClick={() => setOn(!on)} data-testid="transliteration-toggle"
            className="text-xs text-red-700 hover:underline">
      {on ? 'Hide transliterations' : 'Show transliterations'}
    </button>
  );
}
