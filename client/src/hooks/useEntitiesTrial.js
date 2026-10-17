/**
 * Whether the Mentions trial (?entities=1) is on for this visit. Copies the
 * mechanism of the documents and scholarship trial switches: the address
 * parameter is written to sessionStorage the first time it is seen, so the
 * flag holds for the rest of the visit on every page, and nothing is saved
 * beyond it. Without the parameter, and without the flag from earlier in the
 * visit, the Mentions tab and page do not exist for the visitor.
 *
 * Read on demand (not through the collections store) because the switch is
 * not a collection: it has no profile, no setting and no saved choice.
 */
export const ENTITIES_KEY = 'tesserae_entities_trial';

export function entitiesTrialOn() {
  let ss = null;
  try { ss = window.sessionStorage; } catch { return false; }
  try {
    if (new URLSearchParams(window.location.search).get('entities') === '1') ss.setItem(ENTITIES_KEY, '1');
    return ss.getItem(ENTITIES_KEY) === '1';
  } catch {
    return false;
  }
}

export default function useEntitiesTrial() {
  return entitiesTrialOn();
}
