import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import useCollections, { CollectionsScope } from '../useCollections';
import useDocumentsTrial from '../useDocumentsTrial';
import { captureUrlOverrides, STORAGE_KEY } from '../../collections/collectionsStore';
import { PROFILES, COLLECTION_IDS } from '../../collections/collectionsConfig';

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/');
});
afterEach(() => window.history.replaceState({}, '', '/'));

describe('profiles', () => {
  it('starts a first-time visitor on Literary: literature only', () => {
    const { result } = renderHook(() => useCollections());
    expect(result.current.profile).toBe('literary');
    expect(COLLECTION_IDS.filter((id) => result.current.isOn(id))).toEqual(['literature']);
    expect(result.current.anyOn(['inscriptions', 'papyri'])).toBe(false);
  });

  it.each(PROFILES.map((p) => [p.id, p.on]))('profile %s sets exactly its collections', (id, on) => {
    const { result } = renderHook(() => useCollections());
    act(() => result.current.setProfile(id));
    expect(result.current.profile).toBe(id);
    COLLECTION_IDS.forEach((c) => expect(result.current.isOn(c)).toBe(on.includes(c)));
  });

  it('reports custom when switches match no profile', () => {
    const { result } = renderHook(() => useCollections());
    act(() => result.current.setCollection('papyri', true));
    expect(result.current.profile).toBe('custom');
  });
});

describe('persistence', () => {
  it('saves the choice to localStorage and restores it', () => {
    const first = renderHook(() => useCollections());
    act(() => first.result.current.setProfile('historical'));
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY)).profile).toBe('historical');
    first.unmount();
    const second = renderHook(() => useCollections());
    expect(second.result.current.profile).toBe('historical');
    expect(second.result.current.isOn('scholarship')).toBe(true);
  });

  it('ignores a corrupt saved value', () => {
    window.localStorage.setItem(STORAGE_KEY, '{nope');
    const { result } = renderHook(() => useCollections());
    expect(result.current.profile).toBe('literary');
  });
});

describe('URL switches', () => {
  it('?documents=1 turns inscriptions and papyri on for the visit without saving', () => {
    window.history.replaceState({}, '', '/?documents=1');
    captureUrlOverrides();
    window.history.replaceState({}, '', '/');
    const { result } = renderHook(() => useCollections());
    expect(result.current.isOn('inscriptions')).toBe(true);
    expect(result.current.isOn('papyri')).toBe(true);
    expect(result.current.isOn('scholarship')).toBe(false);
    expect(window.sessionStorage.getItem('tesserae_documents_trial')).toBe('1');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('?scholarship=1 turns scholarship on', () => {
    window.history.replaceState({}, '', '/?scholarship=1');
    const { result } = renderHook(() => useCollections());
    expect(result.current.isOn('scholarship')).toBe(true);
    expect(result.current.isOn('papyri')).toBe(false);
  });

  it('the old session keys still count', () => {
    window.sessionStorage.setItem('tesserae_documents_trial', '1');
    expect(renderHook(() => useDocumentsTrial()).result.current).toBe(true);
  });

  it('?profile= and ?collections= override the saved choice for the visit', () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ profile: 'everything' }));
    window.history.replaceState({}, '', '/?profile=literary');
    expect(renderHook(() => useCollections()).result.current.profile).toBe('literary');
    window.sessionStorage.clear();
    window.history.replaceState({}, '', '/?collections=papyri,scholarship');
    const { result } = renderHook(() => useCollections());
    expect(result.current.isOn('papyri')).toBe(true);
    expect(result.current.isOn('literature')).toBe(false);
  });

  it('a deliberate choice replaces the visit overrides', () => {
    window.sessionStorage.setItem('tesserae_documents_trial', '1');
    const { result } = renderHook(() => useCollections());
    act(() => result.current.setProfile('literary'));
    expect(result.current.isOn('papyri')).toBe(false);
  });
});

describe('scope overrides', () => {
  it('a page or focus view can override without saving', () => {
    const wrapper = ({ children }) => (
      <CollectionsScope overrides={{ scholarship: true }}>{children}</CollectionsScope>
    );
    const { result } = renderHook(() => useCollections(), { wrapper });
    expect(result.current.isOn('scholarship')).toBe(true);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
