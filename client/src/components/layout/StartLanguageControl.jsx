import { useState } from 'react';
import { getStartSetting, setStartSetting, START_LAST } from '../../utils/languagePreference';

/**
 * "Open in": which language the site opens in on a new visit (2026-10-07).
 * The default reopens the language used last; choosing a language fixes it,
 * for a reader who visits others but always wants to start in, say, Latin.
 * Stored only in this browser (utils/languagePreference.js).
 */
export default function StartLanguageControl({ languages, className = '' }) {
  const [setting, setSetting] = useState(getStartSetting);
  const onChange = (e) => {
    setStartSetting(e.target.value);
    setSetting(e.target.value);
  };
  return (
    <label className={`flex items-center gap-1.5 text-xs text-gray-500 whitespace-nowrap ${className}`}
           title="Kept in this browser only. A link that names a language still opens in it.">
      Open in
      <select
        value={setting}
        onChange={onChange}
        aria-label="Language the site opens in"
        className="border border-gray-200 rounded px-1.5 py-0.5 text-xs text-gray-700 bg-white"
      >
        <option value={START_LAST}>the language I used last</option>
        {languages.map((l) => (
          <option key={l.code} value={l.code}>{l.label}</option>
        ))}
      </select>
    </label>
  );
}
