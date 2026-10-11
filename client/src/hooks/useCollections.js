import { createContext, createElement, useCallback, useContext, useMemo, useSyncExternalStore } from 'react';
import { getSnapshot, subscribe, setCollection, setProfile, setView } from '../collections/collectionsStore';
import { COLLECTION_IDS } from '../collections/collectionsConfig';

const ScopeContext = createContext(null);

/**
 * A page or focus view's own overrides, e.g.
 * <CollectionsScope overrides={{ scholarship: false }}>. They apply to
 * everything inside and are never saved.
 */
export function CollectionsScope({ overrides, children }) {
  const parent = useContext(ScopeContext);
  const merged = useMemo(() => ({ ...(parent || {}), ...(overrides || {}) }), [parent, overrides]);
  return createElement(ScopeContext.Provider, { value: merged }, children);
}

/**
 * The visitor's collections: `isOn(id)`, `anyOn([ids])`, the current
 * `profile` ('custom' when the switches match none), the profile's `layout`
 * hints, and setters. Components ask this, never read storage themselves.
 */
export default function useCollections() {
  const snap = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const scope = useContext(ScopeContext);
  const on = useMemo(() => {
    const o = { ...snap.on };
    if (scope) COLLECTION_IDS.forEach((id) => { if (typeof scope[id] === 'boolean') o[id] = scope[id]; });
    return o;
  }, [snap, scope]);
  const isOn = useCallback((id) => !!on[id], [on]);
  const anyOn = useCallback((ids) => !ids || ids.length === 0 || ids.some((id) => !!on[id]), [on]);
  return { on, isOn, anyOn, profile: snap.profile, layout: snap.layout, view: snap.view, setCollection, setProfile, setView };
}
