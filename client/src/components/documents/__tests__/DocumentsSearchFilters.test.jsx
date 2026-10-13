import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import DocumentsSearchFilters from '../DocumentsSearchFilters';
import useDocumentsSearch from '../useDocumentsSearch';
import { buildOptions, resetDocumentFilterOptions } from '../useDocumentFilterOptions';

const BROWSE = {
  region_counts: [
    { value: 'Latium', count: 500 }, { value: 'Dalmatia', count: 300 },
    { value: 'Tiny', count: 5 }, { value: 'unknown', count: 900 }, { value: 'Unknown nome', count: 800 },
  ],
  filters: {
    text_types: [
      { value: 'epitaph', count: 400 }, { value: 'Epitaph', count: 100 },
      { value: 'honorific inscription', count: 50 }, { value: 'Honorific inscription.', count: 30 },
      { value: 'curiosity', count: 3 }, { value: 'other', count: 700 },
    ],
    materials: [{ value: 'marble', count: 1000 }, { value: 'Marble', count: 20 }],
  },
};

beforeEach(() => {
  resetDocumentFilterOptions();
  global.fetch = vi.fn(async () => ({ ok: true, json: async () => BROWSE }));
});
afterEach(() => { delete global.fetch; });

function Harness({ onParams }) {
  const h = useDocumentsSearch({ documentsEnabled: true, defaultCollection: 'documents' });
  const [, force] = useState(0);
  return (
    <div>
      <DocumentsSearchFilters
        options={[{ key: 'documents', label: 'Documents' }, { key: 'both', label: 'Both' }]}
        collection={h.collection} setCollection={h.setCollection}
        dateFrom={h.dateFrom} setDateFrom={h.setDateFrom} dateTo={h.dateTo} setDateTo={h.setDateTo}
        docKind={h.docKind} setDocKind={h.setDocKind}
        docRegion={h.docRegion} setDocRegion={h.setDocRegion}
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

describe('buildOptions', () => {
  it('merges case and trailing-punctuation variants, drops small and unknown values', () => {
    const o = buildOptions(BROWSE.filters.text_types);
    expect(o.map(x => [x.label, x.count])).toEqual([['Epitaph', 500], ['Honorific inscription', 80]]);
  });
});

describe('DocumentsSearchFilters drop-downs', () => {
  it('renders fetched options with Any first and counts, merged and trimmed', async () => {
    render(<Harness onParams={() => {}} />);
    await waitFor(() => expect(screen.getByRole('option', { name: 'Epitaph (500)' })).toBeTruthy());
    const textType = screen.getByLabelText('Text type');
    const names = within(textType).getAllByRole('option').map(o => o.textContent);
    expect(names).toEqual(['Any', 'Epitaph (500)', 'Honorific inscription (80)']);
    const region = within(screen.getByLabelText('Region')).getAllByRole('option').map(o => o.textContent);
    expect(region).toEqual(['Any', 'Latium (500)', 'Dalmatia (300)']);
    const material = within(screen.getByLabelText('Material')).getAllByRole('option').map(o => o.textContent);
    expect(material).toEqual(['Any', 'Marble (1,020)']);
    const source = within(screen.getByLabelText('Source')).getAllByRole('option').map(o => o.textContent);
    expect(source[0]).toBe('Any');
    expect(source).toContain('Epigraphic Database Roma');
    expect(source).toContain('Papyri (papyri.info)');
    expect(source).toContain('I.Sicily');
  });

  it('sends the chosen values, and kind', async () => {
    const seen = [];
    render(<Harness onParams={p => seen.push(p)} />);
    await waitFor(() => expect(screen.getByRole('option', { name: 'Epitaph (500)' })).toBeTruthy());
    await userEvent.selectOptions(screen.getByLabelText('Text type'), 'Epitaph');
    await userEvent.selectOptions(screen.getByLabelText('Region'), 'Latium');
    await userEvent.selectOptions(screen.getByLabelText('Material'), 'Marble');
    await userEvent.selectOptions(screen.getByLabelText('Source'), 'papyri');
    await userEvent.selectOptions(screen.getByLabelText('Kind'), 'papyri');
    await userEvent.click(screen.getByRole('button', { name: 'params' }));
    expect(seen[0]).toMatchObject({
      text_type: 'Epitaph', region: 'Latium', material: 'Marble', source: 'papyri', kind: 'papyri',
    });
  });

  it('Kind offers Inscriptions, Papyri, Both and sends nothing for Both', async () => {
    const seen = [];
    render(<Harness onParams={p => seen.push(p)} />);
    const names = within(screen.getByLabelText('Kind')).getAllByRole('option').map(o => o.textContent);
    expect(names).toEqual(['Inscriptions', 'Papyri', 'Both']);
    await userEvent.click(screen.getByRole('button', { name: 'params' }));
    expect(seen[0].kind).toBeUndefined();
  });
});
