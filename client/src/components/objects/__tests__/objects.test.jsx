/**
 * The Objects page: list with search and filters, one object, the Collections
 * gate, and the Objects option of Theme Search (its own list, never the passages).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ObjectsPage from '../ObjectsPage';
import ObjectList from '../ObjectList';
import ObjectCard from '../ObjectCard';
import ThemeSearchPage from '../../passages/ThemeSearchPage';
import { objectDate, accession } from '../objectsFormat';
import { PROFILES, COLLECTIONS, PAGE_NEEDS, profileSwitches } from '../../../collections/collectionsConfig';
import { setProfile, setCollection } from '../../../collections/collectionsStore';

const OBJ = {
  id: 'cma:1966.114', museum: 'cleveland', museum_name: 'Cleveland Museum of Art',
  title: 'White-Ground Lekythos (Oil Vessel)', object_type: 'Ceramic', culture: 'Greek, Attic',
  date_text: 'c. 500-490 BCE', date_start: -500, date_end: -490, material: 'ceramic', place_text: null,
  description: 'Known as white-ground because of the white clay slip applied as a surface for painting.',
  short_text: 'Label text', inscription_text: 'Graffito on underside of foot',
  image_url: 'https://openaccess-cdn.clevelandart.org/1966.114/1966.114_web.jpg',
  object_url: 'https://clevelandart.org/art/1966.114', licence: 'CC0',
  credit: 'Cleveland Museum of Art, Leonard C. Hanna Jr. Fund. Catalogue record and image CC0.',
};
const OBJ2 = { ...OBJ, id: 'aic:1900.001', museum: 'chicago', museum_name: 'Art Institute of Chicago',
  title: 'Volute Krater (Mixing Bowl)', date_text: '350-340 BCE', date_start: -350, date_end: -340,
  image_url: null, object_url: 'https://www.artic.edu/artworks/11111', licence: 'Catalogue record CC0, description CC BY 4.0',
  credit: 'Art Institute of Chicago, Memorial Fund. Catalogue record CC0, description CC BY 4.0.' };

const LIST = {
  available: true, total: 2, page: 1, per_page: 24, sort: 'date', objects: [OBJ, OBJ2],
  facets: {
    museum: [{ value: 'cleveland', count: 1 }, { value: 'chicago', count: 1 }],
    object_type: [{ value: 'Ceramic', count: 1 }],
    culture: [{ value: 'Greek, Attic', count: 1 }],
    material: [{ value: 'ceramic', count: 1 }],
  },
};
const THEME = {
  available: true, query: 'oil for the dead', label: 'Ranked by how close each museum description is in meaning to your words.',
  results: [{ ...OBJ, score: 0.83, snippet: 'Known as white-ground because of the white clay slip.' }],
};

function mockApi(listOverride, themeOverride) {
  const calls = [];
  global.fetch = vi.fn(async (url) => {
    const u = String(url);
    calls.push(u);
    let body = {};
    if (u.startsWith('/api/objects/theme')) body = themeOverride || THEME;
    else if (u.startsWith('/api/objects/')) body = { object: OBJ };
    else if (u.startsWith('/api/objects')) body = listOverride || LIST;
    else if (u.startsWith('/api/languages')) body = { languages: [] };
    return { ok: true, status: 200, json: async () => body };
  });
  return calls;
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/objects');
  setProfile('archaeological');
});
afterEach(() => { cleanup(); delete global.fetch; window.history.replaceState({}, '', '/'); });

describe('collections wiring', () => {
  it('Objects is available, with its blurb, and needed by the objects page', () => {
    const c = COLLECTIONS.find((x) => x.id === 'objects');
    expect(c.available).toBe(true);
    expect(c.blurb).toBe('Museum objects with catalogue descriptions');
    expect(PAGE_NEEDS.objects).toEqual(['objects']);
  });
  it('the Archaeological and Everything profiles have objects on, Literary and Historical off', () => {
    expect(PROFILES.find((p) => p.id === 'everything').on).toContain('objects');
    expect(profileSwitches('everything').objects).toBe(true);
    expect(profileSwitches('archaeological').objects).toBe(true);
    expect(profileSwitches('literary').objects).toBe(false);
    expect(profileSwitches('historical').objects).toBe(false);
  });
  it('formats dates and accession numbers', () => {
    expect(objectDate({ date_text: 'about 150 CE', date_start: 130 })).toBe('about 150 CE');
    expect(objectDate({ date_start: -18, date_end: -17 })).toBe('18 to 17 BCE');
    expect(objectDate({})).toBe('undated');
    expect(accession({ id: 'cma:1966.114' })).toBe('1966.114');
  });
  it('a direct link lands on Search when Objects is off', async () => {
    mockApi();
    setProfile('literary');
    const setPageType = vi.fn();
    render(<ObjectsPage setPageType={setPageType} />);
    await waitFor(() => expect(setPageType).toHaveBeenCalledWith('search'));
    expect(screen.queryByText('Objects')).toBeNull();
  });
});

describe('the list', () => {
  it('shows each object with museum, accession, date, description, credit, object page link and image', async () => {
    mockApi();
    render(<ObjectsPage setPageType={() => {}} />);
    expect(await screen.findByText('White-Ground Lekythos (Oil Vessel)')).toBeTruthy();
    expect(screen.getByTestId('objects-total').textContent).toContain('2 objects');
    expect(screen.getByText(/Cleveland Museum of Art · 1966.114/)).toBeTruthy();
    expect(screen.getByText(/Art Institute of Chicago · 1900.001/)).toBeTruthy();
    expect(screen.getAllByText(/Known as white-ground/).length).toBe(2);
    expect(screen.getByText(/description CC BY 4.0/)).toBeTruthy();
    const links = screen.getAllByRole('link', { name: 'Object page' });
    expect(links[0].getAttribute('href')).toBe(OBJ.object_url);
    expect(screen.getAllByRole('img').length).toBe(1);  // the Chicago record has no free image
    expect(screen.getByRole('img').getAttribute('src')).toBe(OBJ.image_url);
  });

  it('sends the search, filters and dates to the API', async () => {
    const calls = mockApi();
    render(<ObjectList openObject={() => {}} />);
    await screen.findByText('Volute Krater (Mixing Bowl)');
    await userEvent.type(screen.getByLabelText(/Search titles/), 'lekythos');
    await userEvent.type(screen.getByLabelText('From'), '600');
    await userEvent.type(screen.getByLabelText('To'), '300');
    await userEvent.selectOptions(screen.getByLabelText('To era'), 'BCE');
    await userEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(calls.some((c) => c.includes('q=lekythos') && c.includes('date_from=-600') && c.includes('date_to=-300'))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText('Museum'), 'chicago');
    await waitFor(() => expect(calls.some((c) => c.includes('museum=chicago'))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText('Object type'), 'Ceramic');
    await waitFor(() => expect(calls.some((c) => c.includes('object_type=Ceramic'))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText('Culture'), 'Greek, Attic');
    await waitFor(() => expect(calls.some((c) => c.includes('culture=Greek%2C+Attic'))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText('Material'), 'ceramic');
    await waitFor(() => expect(calls.some((c) => c.includes('material=ceramic'))).toBe(true));
    expect(screen.getByRole('option', { name: 'Cleveland Museum of Art (1)' })).toBeTruthy();
  });

  it('pages, and says so when nothing is installed or nothing matches', async () => {
    const calls = mockApi({ ...LIST, total: 100 });
    render(<ObjectList openObject={() => {}} />);
    await screen.findByText('Page 1 of 5');
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(calls.some((c) => c.includes('page=2'))).toBe(true));
    cleanup();
    mockApi({ available: false, objects: [], total: 0, facets: {} });
    render(<ObjectList openObject={() => {}} />);
    expect(await screen.findByText(/not installed on this server/)).toBeTruthy();
    cleanup();
    mockApi({ ...LIST, objects: [], total: 0 });
    render(<ObjectList openObject={() => {}} />);
    expect(await screen.findByText(/No object matches/)).toBeTruthy();
  });
});

describe('one object', () => {
  it('opens /objects/<id> with the full description, label, inscription and licence', async () => {
    window.history.replaceState({}, '', '/objects/cma%3A1966.114');
    const calls = mockApi();
    render(<ObjectsPage setPageType={() => {}} />);
    expect(await screen.findByText('Label text')).toBeTruthy();
    expect(calls[0]).toBe('/api/objects/cma%3A1966.114');
    expect(screen.getByText('Graffito on underside of foot')).toBeTruthy();
    expect(screen.getByText('CC0')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'All objects' })).toBeTruthy();
  });

  it('shows a long description in full on its own page and cut in a list', () => {
    const long = { ...OBJ, description: 'word '.repeat(300).trim() };
    const { unmount } = render(<ObjectCard object={long} />);
    expect(screen.getByTestId('object-description').textContent.endsWith('...')).toBe(true);
    unmount();
    render(<ObjectCard object={long} full />);
    expect(screen.getByTestId('object-description').textContent.endsWith('...')).toBe(false);
  });
});

describe('Theme Search', () => {
  async function run(text) {
    fireEvent.change(screen.getByPlaceholderText(/a warrior arms himself/), { target: { value: text } });
    fireEvent.click(screen.getByRole('button', { name: /^search/i }));
  }

  it('offers no Objects choice unless the collection is on', () => {
    mockApi();
    setProfile('historical');
    render(<ThemeSearchPage />);
    expect(screen.queryByRole('checkbox', { name: 'Objects' })).toBeNull();
  });

  it('searches the object descriptions on their own, never the passages', async () => {
    const calls = mockApi();
    setProfile('historical');
    setCollection('objects', true);
    render(<ThemeSearchPage />);
    await userEvent.click(screen.getByRole('checkbox', { name: 'Objects' }));
    await run('oil for the dead');
    await screen.findByText('Known as white-ground because of the white clay slip.');
    expect(calls.some((c) => c.startsWith('/api/objects/theme?q=oil%20for%20the%20dead'))).toBe(true);
    expect(calls.some((c) => c.startsWith('/api/passages/theme-search'))).toBe(false);
    expect(screen.getByTestId('theme-objects-label').textContent).toMatch(/Ranked by how close/);
    await userEvent.click(screen.getByRole('checkbox', { name: 'Objects' }));
    expect(screen.queryByTestId('theme-objects')).toBeNull();
  });

  it('keeps Coins and Objects apart: choosing one clears the other', async () => {
    mockApi();
    setProfile('archaeological');
    render(<ThemeSearchPage />);
    await userEvent.click(screen.getByRole('checkbox', { name: 'Coins' }));
    expect(screen.getByRole('checkbox', { name: 'Coins' }).checked).toBe(true);
    await userEvent.click(screen.getByRole('checkbox', { name: 'Objects' }));
    expect(screen.getByRole('checkbox', { name: 'Objects' }).checked).toBe(true);
    expect(screen.getByRole('checkbox', { name: 'Coins' }).checked).toBe(false);
  });
});
