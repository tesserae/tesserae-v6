/**
 * Stage 3b-3's document Reader view: GET /api/documents/<doc_id>, rendered
 * at /document?doc=...&lang=...&q=...&type=..., with a back link that
 * carries the originating query back to Line Search.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

import DocumentView from '../DocumentView';

const documentPayload = {
  doc_id: 'edh:HD047322',
  language: 'la',
  text_id: 'edh__roma.tess',
  lines: [
    { ref: 'edh:HD047322', text: 'D M Aurelia', tokens: ['D', 'M', 'Aurelia'],
      restored_indices: [0], fragment_indices: [] },
  ],
  credit: {
    licence_name: 'CC BY-SA 4.0', licence_url: 'https://creativecommons.org/licenses/by-sa/4.0/',
    source_name: 'Epigraphic Database Heidelberg', source_url: 'https://edh.example.org/HD047322',
    principal_edition: 'AE 2001, 2169.',
  },
  date_not_before: 101, date_not_after: 300,
  ancient_place: null, modern_place: 'Rome', region: 'Roma', pleiades_id: '423025',
  text_type_label: 'funerary inscription', object_type_label: 'stele', material_label: 'marble',
  display: {
    museum: 'Rome, Mus. Capitolino', inventory: 'inv. 42', dimensions: '30 x 20 cm',
    translation: 'To the departed spirits of Aurelia.',
    apparatus: 'l. 1 AVRELIA : lege AVRELIAE',
    commentary: 'A standard funerary dedication.',
    image_url: ['https://example.org/a.jpg', 'https://example.org/b.jpg'],
  },
};

function setUrl(search) {
  window.history.pushState({}, '', `/document${search}`);
}

function mockFetchOk(payload) {
  global.fetch = vi.fn(async (url) => {
    if (String(url).startsWith('/api/documents/')) {
      return { ok: true, status: 200, json: async () => payload };
    }
    return { ok: false, status: 404, json: async () => ({ error: 'not found' }) };
  });
}

afterEach(() => {
  delete global.fetch;
  window.history.pushState({}, '', '/');
});

describe('DocumentView', () => {
  it('fetches the document by id and language from the URL', async () => {
    setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma');
    mockFetchOk(documentPayload);
    render(<DocumentView />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/documents/edh%3AHD047322?language=la'));
  });

  it('shows the principal edition as the title, date/place with a Pleiades link, and the type labels', async () => {
    setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma');
    mockFetchOk(documentPayload);
    render(<DocumentView />);
    await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
    expect(document.body.textContent).toMatch(/101 AD.*300 AD/);
    expect(document.body.textContent).toContain('Rome');
    const pleiades = screen.getByRole('link', { name: 'Pleiades' });
    expect(pleiades).toHaveAttribute('href', 'https://pleiades.stoa.org/places/423025');
    expect(screen.getByText('funerary inscription')).toBeTruthy();
    expect(screen.getByText('marble')).toBeTruthy();
  });

  it('marks the restored token in the text', async () => {
    setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma');
    mockFetchOk(documentPayload);
    render(<DocumentView />);
    await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
    const restored = document.querySelector('.decoration-dotted');
    expect(restored).toBeTruthy();
    expect(restored.textContent).toBe('D');
  });

  it('shows museum, inventory, dimensions, translation, and the credit with licence link', async () => {
    setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma');
    mockFetchOk(documentPayload);
    render(<DocumentView />);
    await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
    expect(document.body.textContent).toContain('Rome, Mus. Capitolino');
    expect(document.body.textContent).toContain('inv. 42');
    expect(document.body.textContent).toContain('30 x 20 cm');
    expect(document.body.textContent).toContain('To the departed spirits of Aurelia.');
    const sourceLink = screen.getByRole('link', { name: 'Epigraphic Database Heidelberg' });
    expect(sourceLink).toHaveAttribute('href', 'https://edh.example.org/HD047322');
    const licenceLink = screen.getByRole('link', { name: 'CC BY-SA 4.0' });
    expect(licenceLink).toHaveAttribute('href', 'https://creativecommons.org/licenses/by-sa/4.0/');
  });

  it('keeps apparatus and commentary collapsed behind their own <details>', async () => {
    setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma');
    mockFetchOk(documentPayload);
    render(<DocumentView />);
    await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
    const apparatusDetails = screen.getByText('Apparatus').closest('details');
    expect(apparatusDetails).toBeTruthy();
    expect(apparatusDetails.open).toBe(false);
    const commentaryDetails = screen.getByText('Commentary').closest('details');
    expect(commentaryDetails).toBeTruthy();
    expect(commentaryDetails.open).toBe(false);
  });

  it('lists every image link with a host label and the address as href and title', async () => {
    setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma');
    mockFetchOk(documentPayload);
    render(<DocumentView />);
    await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
    expect(screen.getAllByRole('link', { name: 'Link at example.org' }).length).toBe(2);
    expect(screen.getAllByTitle(/^https:\/\/example\.org\/[ab]\.jpg$/).length).toBe(2);
  });

  it('names the institution, and omits links to dead hosts with a note', async () => {
    setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma');
    mockFetchOk({
      ...documentPayload,
      display: {
        ...documentPayload.display,
        image_url: [
          'https://edh.ub.uni-heidelberg.de/edh/foto/F034014',
          'http://www.edr-edr.it/foto_epigrafi/immagini_uso/7/007012.jpg',
          'https://lupa.at/16121',
          'https://access.bl.uk/item/viewer/ark:/81055/vdc_1',
          'ISic000001.jpg',
        ],
      },
    });
    render(<DocumentView />);
    await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
    expect(screen.getByRole('link', { name: 'Photo F034014 at Epigraphic Database Heidelberg' })
      .getAttribute('href')).toBe('https://edh.ub.uni-heidelberg.de/edh/foto/F034014');
    expect(screen.getByRole('link', { name: 'Image at Epigraphic Database Roma' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Record at Ubi Erat Lupa' })).toBeTruthy();
    expect(screen.queryByText(/access\.bl\.uk/)).toBeNull();
    expect(screen.getByText(/2 image links omitted \(the host no longer serves them\)/)).toBeTruthy();
  });

  it('the back link returns to Line Search with the query, language and type intact', async () => {
    setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma');
    mockFetchOk(documentPayload);
    render(<DocumentView />);
    await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
    const back = screen.getByRole('link', { name: /back to search results/ });
    const params = new URLSearchParams(back.getAttribute('href').split('?')[1]);
    expect(params.get('lang')).toBe('la');
    expect(params.get('q')).toBe('dis manibus');
    expect(params.get('type')).toBe('lemma');
  });

  it('carries the documents=1 trial flag on the back link when present in the URL', async () => {
    setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma&documents=1');
    mockFetchOk(documentPayload);
    render(<DocumentView />);
    await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
    const back = screen.getByRole('link', { name: /back to search results/ });
    const params = new URLSearchParams(back.getAttribute('href').split('?')[1]);
    expect(params.get('documents')).toBe('1');
  });

  // Opened from the Inscriptions & Papyri page's own documentViewUrl
  // (from=inscriptions-papyri): the back link returns there instead of
  // to Line Search, with every query param that page sent carried along
  // verbatim (minus doc/from, the two fields specific to opening this
  // view) rather than a hand-picked subset.
  describe('opened with from=inscriptions-papyri', () => {
    it('the back link points at /inscriptions-papyri, not /line-search', async () => {
      setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma&from=inscriptions-papyri&documents=1');
      mockFetchOk(documentPayload);
      render(<DocumentView />);
      await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
      const back = screen.getByRole('link', { name: /back to search results/ });
      expect(back.getAttribute('href').split('?')[0]).toBe('/inscriptions-papyri');
    });

    it('carries every filter param from the opening URL, minus doc and from', async () => {
      setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma&collection=both&sort=oldest'
        + '&region=Roma&date_from=100&date_to=300&from=inscriptions-papyri&documents=1');
      mockFetchOk(documentPayload);
      render(<DocumentView />);
      await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
      const back = screen.getByRole('link', { name: /back to search results/ });
      const params = new URLSearchParams(back.getAttribute('href').split('?')[1]);
      expect(params.get('q')).toBe('dis manibus');
      expect(params.get('collection')).toBe('both');
      expect(params.get('sort')).toBe('oldest');
      expect(params.get('region')).toBe('Roma');
      expect(params.get('date_from')).toBe('100');
      expect(params.get('date_to')).toBe('300');
      expect(params.get('documents')).toBe('1');
      expect(params.has('doc')).toBe(false);
      expect(params.has('from')).toBe(false);
    });

    it('without from, still returns to /line-search (every link predating this field)', async () => {
      setUrl('?doc=edh:HD047322&lang=la&q=dis+manibus&type=lemma');
      mockFetchOk(documentPayload);
      render(<DocumentView />);
      await waitFor(() => expect(screen.getByText('AE 2001, 2169.')).toBeTruthy());
      const back = screen.getByRole('link', { name: /back to search results/ });
      expect(back.getAttribute('href').split('?')[0]).toBe('/line-search');
    });
  });

  it('shows a not-found message on a 404 without throwing', async () => {
    setUrl('?doc=edh:NOPE&lang=la&q=x&type=lemma');
    global.fetch = vi.fn(async () => ({ ok: false, status: 404, json: async () => ({ error: 'not found' }) }));
    render(<DocumentView />);
    await waitFor(() => expect(screen.getByText('Document not found.')).toBeTruthy());
  });
});
