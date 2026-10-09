import { useState } from 'react';
import { getSessionValue, setSessionValue } from '../utils/storage';

/**
 * The documents trial flag: `?documents=1` in the URL switches it on and
 * remembers that for the rest of the visit (sessionStorage), the same
 * pattern LineSearch.jsx, CorpusBrowser.jsx and ReaderPage.jsx each wrote
 * for themselves. New callers (Navigation.jsx, the Inscriptions & Papyri
 * page) use this shared hook instead of a fourth copy.
 *
 * This does not check the SERVER switch (`documents_enabled` from
 * /api/languages) -- callers that need that still fetch it themselves, as
 * LineSearch.jsx's `documentsEnabled` state does.
 */
export default function useDocumentsTrial() {
  const [documentsTrial] = useState(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('documents') === '1';
    if (fromUrl) setSessionValue('documents_trial', '1');
    return fromUrl || getSessionValue('documents_trial', '0') === '1';
  });
  return documentsTrial;
}
