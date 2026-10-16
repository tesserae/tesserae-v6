import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import ScholarshipSourcesPage from '../ScholarshipSourcesPage';
import HelpPage from '../HelpPage';
import { pageForPath } from '../../../hooks/useRoute';
import { mockResponse } from '../../../test/mockResponse';

afterEach(() => { delete global.fetch; window.history.replaceState({}, '', '/'); });

const ABOUT = {
  commentaries: [{
    language: 'la', language_name: 'Latin',
    commentaries: [{ commentator: 'Servius', title: 'In Aeneidos', edition: 'Thilo', works: ['vergil.aeneid'], notes: 1200,
      license: 'Public domain', source: 'https://example.org/servius' }],
  }],
  journals: [
    { id: 'ejc', name: 'JSTOR Early Journal Content', description: 'Journals before 1923.',
      terms: 'Public domain, full text indexed and quoted by the sentence.', available: true,
      journals: [{ journal: 'Hermes', year_from: 1866, year_to: 1869, articles: 177, articles_with_citations: 80, citations: 514 }],
      totals: { articles: 177, articles_with_citations: 80, citations: 514 } },
    { id: 'muse', name: 'Project MUSE', description: 'Journals on Project MUSE.',
      terms: 'Licensed text, indexed for citations.', available: true,
      journals: [{ journal: 'Classical Journal', year_from: 2007, year_to: 2026, articles: 771, articles_with_citations: 331, citations: 3577 }],
      totals: { articles: 771, articles_with_citations: 331, citations: 3577 } },
  ],
  online: { note: 'Only open metadata is read.', services: [{ name: 'OpenAlex', text: 'Titles and abstracts.' }] },
  methods: [{ id: 'recognition', title: 'How a citation is recognized', text: '58 of 60 cite the passage.' }],
  updated: { commentaries: 1791424634, indexes: { ejc: 1792132550, muse: 1792130012 } },
};

describe('ScholarshipSourcesPage', () => {
  it('renders the four sections from the response', async () => {
    global.fetch = vi.fn(() => Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(ABOUT) })));
    render(<ScholarshipSourcesPage />);
    expect(await screen.findByRole('heading', { name: 'Commentaries held' })).toHaveAttribute('id', 'commentaries');
    expect(screen.getByRole('heading', { name: 'Journal citation indexes' })).toHaveAttribute('id', 'journals');
    expect(screen.getByRole('heading', { name: 'Online services consulted live' })).toHaveAttribute('id', 'online');
    expect(screen.getByRole('heading', { name: 'Methods' })).toHaveAttribute('id', 'methods');
    // The gap between the two indexes is computed from their year spans.
    expect(screen.getByRole('heading', { name: 'What is not here, and where to look' })).toHaveAttribute('id', 'beyond');
    expect(within(screen.getByTestId('beyond')).getByText(/stop at 1869 and resume in 2007\. Between 1870 and 2006/)).toBeTruthy();
    expect(within(screen.getByTestId('beyond')).getByText(/From 2007 on the index holds Classical Journal/)).toBeTruthy();
    expect(screen.getByRole('heading', { level: 1, name: 'Scholarship: sources and methods' })).toBeTruthy();
    const ejc = screen.getByTestId('index-ejc');
    expect(within(ejc).getByText('Hermes')).toBeTruthy();
    expect(within(ejc).getByText('1866 to 1869')).toBeTruthy();
    expect(within(ejc).getByText(/Public domain, full text indexed/)).toBeTruthy();
    expect(within(screen.getByTestId('index-muse')).getByText('Classical Journal')).toBeTruthy();
    expect(within(screen.getByTestId('commentaries-la')).getByText('Servius')).toBeTruthy();
    expect(screen.getByText('OpenAlex.')).toBeTruthy();
    expect(screen.getByText('58 of 60 cite the passage.')).toBeTruthy();
    expect(screen.getAllByText(/Last updated 2026-/).length).toBeGreaterThan(0);
  });

  it('says so when the list cannot be loaded', async () => {
    global.fetch = vi.fn(() => Promise.resolve(mockResponse({ ok: false, status: 500, json: () => Promise.resolve({}) })));
    render(<ScholarshipSourcesPage />);
    expect(await screen.findByText(/could not be loaded/)).toBeTruthy();
  });
});

describe('Help page', () => {
  it('links the Scholarship section to the sources page', async () => {
    global.fetch = vi.fn(() => Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({ languages: [] }) })));
    render(<HelpPage initialSection="reader" initialAnchor="scholarship-sources" onSectionConsumed={() => {}} />);
    // Two links since 2026-10-16: the methods, and what is not held.
    const links = await screen.findAllByTestId('about-these-sources');
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/scholarship-sources#methods', '/scholarship-sources#beyond']);
  });
});

describe('route', () => {
  it('opens /scholarship-sources as its own page', () => {
    expect(pageForPath('/scholarship-sources')).toBe('scholarship-sources');
  });
});
