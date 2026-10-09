/**
 * Documents section of Browse Corpus (behind the documents trial): drills
 * GET /api/documents/browse's facet tree (kind -> region -> century) plus
 * the flat filters down to a paged document list, each opening the
 * existing document Reader view at /document.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DocumentsBrowser from '../DocumentsBrowser';

const BASE_RESPONSE = {
  kind_counts: [
    { value: 'inscriptions', label: 'Inscriptions (Latin, Greek)', count: 4 },
    { value: 'papyri', label: 'Papyri and ostraca', count: 2 },
  ],
  region_counts: [
    { value: 'Dalmatia', count: 2 },
    { value: 'Sicilia', count: 1 },
  ],
  century_counts: [
    { label: '2nd century AD', count: 1 },
    { label: 'Undated', count: 1 },
  ],
  filters: {
    text_types: [{ value: 'epitaph', count: 2 }],
    materials: [{ value: 'marble', count: 2 }],
    objects: [{ value: 'stele', count: 1 }],
    languages: [{ value: 'la', count: 2 }],
  },
  documents: [
    {
      doc_id: 'edh:A1', kind: 'inscriptions', region: 'Dalmatia',
      century: '2nd century AD', date_label: '101 AD - 150 AD',
      text_type: 'epitaph', material: 'marble', object_type: 'stele',
      language: 'la', title: 'CIL III 0001', first_line: 'D M Aurelia',
    },
  ],
  total: 4,
  page: 1,
  page_size: 50,
};

function mockFetch(responses) {
  global.fetch = vi.fn(async (url) => {
    const u = String(url);
    if (u.startsWith('/api/documents/browse')) {
      const resp = responses(u) || BASE_RESPONSE;
      return { ok: true, status: 200, json: async () => resp };
    }
    return { ok: false, status: 404, json: async () => ({ error: 'not found' }) };
  });
}

afterEach(() => {
  delete global.fetch;
});

describe('DocumentsBrowser', () => {
  it('renders kind counts and the document list from the API', async () => {
    mockFetch(() => BASE_RESPONSE);
    render(<DocumentsBrowser documentsTrial={false} />);
    await waitFor(() => expect(screen.getByText(/Inscriptions \(Latin, Greek\)/)).toBeTruthy());
    expect(screen.getByText(/Papyri and ostraca/)).toBeTruthy();
    expect(screen.getByText('CIL III 0001')).toBeTruthy();
    expect(screen.getByText('D M Aurelia')).toBeTruthy();
  });

  it('clicking a region re-fetches with region as a filter and resets to page 1', async () => {
    let lastUrl = null;
    mockFetch((u) => { lastUrl = u; return BASE_RESPONSE; });
    render(<DocumentsBrowser documentsTrial={false} />);
    await waitFor(() => expect(screen.getByText('Dalmatia')).toBeTruthy());

    fireEvent.click(screen.getByText('Dalmatia'));
    await waitFor(() => expect(lastUrl).toContain('region=Dalmatia'));
    expect(lastUrl).toContain('page=1');
  });

  it('clicking a kind clears any region/century selection', async () => {
    let lastUrl = null;
    mockFetch((u) => { lastUrl = u; return BASE_RESPONSE; });
    render(<DocumentsBrowser documentsTrial={false} />);
    await waitFor(() => expect(screen.getByText('Dalmatia')).toBeTruthy());

    fireEvent.click(screen.getByText('Dalmatia'));
    await waitFor(() => expect(lastUrl).toContain('region=Dalmatia'));

    fireEvent.click(screen.getByText(/Papyri and ostraca/));
    await waitFor(() => expect(lastUrl).toContain('kind=papyri'));
    expect(lastUrl).not.toContain('region=');
  });

  it('a document link carries the documents=1 trial flag when the trial is active', async () => {
    mockFetch(() => BASE_RESPONSE);
    render(<DocumentsBrowser documentsTrial={true} />);
    await waitFor(() => expect(screen.getByText('CIL III 0001')).toBeTruthy());
    const link = screen.getByText('CIL III 0001').closest('a');
    expect(link.getAttribute('href')).toContain('doc=edh%3AA1');
    expect(link.getAttribute('href')).toContain('documents=1');
  });

  it('selecting a text type filter re-fetches with that filter', async () => {
    let lastUrl = null;
    mockFetch((u) => { lastUrl = u; return BASE_RESPONSE; });
    render(<DocumentsBrowser documentsTrial={false} />);
    await waitFor(() => expect(screen.getByLabelText('Text type')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Text type'), { target: { value: 'epitaph' } });
    await waitFor(() => expect(lastUrl).toContain('text_type=epitaph'));
    expect(lastUrl).toContain('page=1');
  });

  it('shows "No documents match this selection" for an empty page', async () => {
    mockFetch(() => ({ ...BASE_RESPONSE, documents: [], total: 0 }));
    render(<DocumentsBrowser documentsTrial={false} />);
    await waitFor(() => expect(screen.getByText('No documents match this selection.')).toBeTruthy());
  });
});
