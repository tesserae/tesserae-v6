import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import DocumentsSearchFilters from '../DocumentsSearchFilters';
import useDocumentsSearch from '../useDocumentsSearch';
import { resetDocumentFilterOptions } from '../useDocumentFilterOptions';

const PLACES = [
  { value: 'Rusellae', label: 'Rusellae (Roselle)', modern: 'Roselle', count: 155 },
  { value: 'Russi', label: 'Russi', modern: '', count: 3 },
];

let calls;
beforeEach(() => {
  resetDocumentFilterOptions();
  calls = [];
  global.fetch = vi.fn(async (url) => {
    calls.push(String(url));
    if (String(url).startsWith('/api/documents/places')) {
      return { ok: true, json: async () => ({ places: PLACES, total: 2 }) };
    }
    return { ok: true, json: async () => ({ region_counts: [], filters: {} }) };
  });
});
afterEach(() => { delete global.fetch; });

function Harness({ onParams }) {
  const h = useDocumentsSearch({ documentsEnabled: true, defaultCollection: 'documents' });
  const [, force] = useState(0);
  return (
    <div>
      <DocumentsSearchFilters
        options={[{ key: 'documents', label: 'Inscriptions and papyri' }]}
        collection={h.collection} setCollection={h.setCollection}
        dateFrom={h.dateFrom} setDateFrom={h.setDateFrom} dateTo={h.dateTo} setDateTo={h.setDateTo}
        docRegion={h.docRegion} setDocRegion={h.setDocRegion}
        docPlace={h.docPlace} setDocPlace={h.setDocPlace}
        language="la"
        docTextType={h.docTextType} setDocTextType={h.setDocTextType}
        docMaterial={h.docMaterial} setDocMaterial={h.setDocMaterial}
        docSource={h.docSource} setDocSource={h.setDocSource}
        excludeRestored={h.excludeRestored} setExcludeRestored={h.setExcludeRestored}
        hideFormulas={h.hideFormulas} setHideFormulas={h.setHideFormulas}
      />
      <button onClick={() => { onParams(h.addCollectionParams({})); force(1); }}>params</button>
    </div>
  );
}

const placeCalls = () => calls.filter(u => u.startsWith('/api/documents/places'));

describe('Place control', () => {
  it('asks for suggestions after two letters, in the search language, up to twelve', async () => {
    render(<Harness onParams={() => {}} />);
    const box = screen.getByLabelText('Place');
    await userEvent.type(box, 'r');
    expect(placeCalls()).toHaveLength(0);
    await userEvent.type(box, 'u');
    await waitFor(() => expect(screen.getByRole('option', { name: /Rusellae \(Roselle\)/ })).toBeTruthy());
    expect(placeCalls().at(-1)).toBe('/api/documents/places?q=ru&limit=12&language=la');
    expect(screen.getByRole('option', { name: /Russi/ })).toBeTruthy();
    expect(screen.getByText('155')).toBeTruthy();
  });

  it('choosing a suggestion fills the box and sends doc_place; clearing removes it', async () => {
    const seen = [];
    render(<Harness onParams={p => seen.push(p)} />);
    const box = screen.getByLabelText('Place');
    await userEvent.type(box, 'rus');
    const option = await screen.findByRole('option', { name: /Rusellae \(Roselle\)/ });
    await userEvent.click(option.querySelector('button'));
    expect(box.value).toBe('Rusellae');
    expect(screen.queryByRole('listbox')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'params' }));
    expect(seen[0].doc_place).toBe('Rusellae');
    await userEvent.clear(box);
    await userEvent.click(screen.getByRole('button', { name: 'params' }));
    expect(seen[1].doc_place).toBeUndefined();
  });

  it('sends typed text as it stands', async () => {
    const seen = [];
    render(<Harness onParams={p => seen.push(p)} />);
    await userEvent.type(screen.getByLabelText('Place'), ' Cosa ');
    await userEvent.click(screen.getByRole('button', { name: 'params' }));
    expect(seen[0].doc_place).toBe('Cosa');
  });
});
