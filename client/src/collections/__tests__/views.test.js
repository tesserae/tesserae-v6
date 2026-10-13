import { describe, expect, it, beforeEach } from 'vitest';
import { VIEWS, viewById, profileById, orderBy } from '../collectionsConfig';
import { FRONT_DOOR_CHOICES } from '../../components/search/frontDoor';
import { READER_TABS } from '../collectionsConfig';
import {
  getSnapshot, getView, setView, setCollection, captureUrlOverrides,
} from '../collectionsStore';

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/');
});

describe('the view data', () => {
  it('has Literature and History, each complete', () => {
    expect(VIEWS.map((v) => v.id)).toEqual(['literature', 'history']);
    const pages = ['search', 'read', 'theme-search', 'ask-a-work', 'inscriptions-papyri', 'events', 'coins', 'objects',
      'browse', 'about', 'help', 'repository', 'downloads'];
    VIEWS.forEach((v) => {
      expect(v.label).toBeTruthy();
      expect(profileById(v.profile)).toBeTruthy();
      expect([...v.menuOrder].sort()).toEqual([...pages].sort());
      expect([...v.readerTabs].sort()).toEqual(READER_TABS.map((t) => t.id).sort());
      expect([...v.startHereOrder].sort()).toEqual(FRONT_DOOR_CHOICES.map((c) => c.id).sort());
      expect(v.searchDefaults.la.source && v.searchDefaults.la.target).toBeTruthy();
      expect(v.searchDefaults.grc.source && v.searchDefaults.grc.target).toBeTruthy();
      expect(v.home.page).toBeTruthy();
    });
  });

  it('gives History Search One Text on the Annals and the history pairs', () => {
    const h = viewById('history');
    expect(h.profile).toBe('everything');
    expect(h.home).toEqual({ page: 'ask-a-work' });
    expect(h.askDefault).toEqual({ lang: 'la', work: 'tacitus.annales' });
    expect(h.menuOrder.slice(0, 3)).toEqual(['ask-a-work', 'read', 'events']);
    expect(h.menuOrder.indexOf('theme-search')).toBeLessThan(h.menuOrder.indexOf('search'));
    expect(h.readerTabs).toEqual(['similar', 'documents', 'coins', 'scholarship', 'reuse', 'verbal', 'translation']);
    expect(h.searchDefaults.la).toEqual({
      source: 'livy.ab_urbe_condita.part.1.books_1-10.tess', target: 'tacitus.annales.part.1.tess',
    });
    expect(h.searchDefaults.grc.target).toBe('thucydides.peleponnesian_war.part.1.tess');
    expect(h.startHereLabels.documents).toBe('Inscriptions, papyri, events and coins');
  });

  it('gives Literature Search One Text first, opening on it, and the literary profile', () => {
    const l = viewById('literature');
    expect(l.profile).toBe('literary');
    expect(l.menuOrder.slice(0, 4)).toEqual(['ask-a-work', 'search', 'read', 'theme-search']);
    expect(l.startHereOrder[0]).toBe('ask');
    expect(l.home).toEqual({ page: 'ask-a-work' });
    expect(l.opensOn).toBe('Search One Text, on the Aeneid');
    expect(l.readerTabs).toEqual(['similar', 'reuse', 'verbal', 'documents', 'scholarship', 'translation', 'coins']);
  });

  it('orders by a list and keeps unnamed items last in their own order', () => {
    expect(orderBy(['a', 'b', 'c', 'd'], ['c', 'a'], (x) => x)).toEqual(['c', 'a', 'b', 'd']);
  });
});

describe('the view store', () => {
  it('defaults to Literature', () => {
    expect(getView()).toBe('literature');
    expect(getSnapshot().view).toBe('literature');
  });

  it('setView saves the choice and applies the profile', () => {
    setView('history');
    expect(window.localStorage.getItem('tesserae_view')).toBe('history');
    expect(getView()).toBe('history');
    expect(getSnapshot().profile).toBe('everything');
    expect(getSnapshot().on.coins).toBe(true);
    setView('literature');
    expect(getSnapshot().profile).toBe('literary');
    expect(getSnapshot().on.coins).toBe(false);
  });

  it('reads ?view=history from the address for the visit without saving it', () => {
    window.history.replaceState({}, '', '/?view=history');
    captureUrlOverrides();
    expect(getView()).toBe('history');
    expect(getSnapshot().profile).toBe('everything');
    expect(window.localStorage.getItem('tesserae_view')).toBeNull();
  });

  it('ignores an unknown view in the address', () => {
    window.history.replaceState({}, '', '/?view=poetry');
    captureUrlOverrides();
    expect(getView()).toBe('literature');
  });

  it('leaves the view alone when a collection is switched by hand', () => {
    setView('history');
    setCollection('coins', false);
    expect(getView()).toBe('history');
    expect(getSnapshot().profile).toBe('custom');
  });

  it('a hand choice of view replaces the address override', () => {
    window.history.replaceState({}, '', '/?view=history');
    captureUrlOverrides();
    setView('literature');
    expect(getView()).toBe('literature');
    expect(window.location.search).toBe('');
  });
});
