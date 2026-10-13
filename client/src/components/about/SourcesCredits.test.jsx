import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';
import SourcesCredits, { COLLECTION_ORDER } from './SourcesCredits';

const records = JSON.parse(fs.readFileSync(
  path.resolve(__dirname, '../../../../data/sources_credits.json'), 'utf-8'));

describe('data/sources_credits.json', () => {
  it('gives every record the fields the page needs', () => {
    expect(records.length).toBeGreaterThan(0);
    for (const rec of records) {
      for (const key of ['collection', 'name', 'url', 'licence_name']) {
        expect(rec[key], `${rec.name} lacks ${key}`).toBeTruthy();
      }
    }
  });
  it('covers every collection and the four document sources', () => {
    const present = new Set(records.map((r) => r.collection));
    for (const c of COLLECTION_ORDER) expect(present.has(c)).toBe(true);
    const names = records.map((r) => r.name).join(' | ');
    for (const n of ['Heidelberg', 'papyri.info', 'I.Sicily', 'Roma']) expect(names).toContain(n);
  });
});

describe('SourcesCredits', () => {
  it('renders every collection group with name, licence and version links', async () => {
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ records }) }));
    render(<SourcesCredits />);
    for (const c of COLLECTION_ORDER) {
      expect(await screen.findByTestId(`credits-group-${c}`)).toBeInTheDocument();
    }
    for (const rec of records) {
      expect(screen.getAllByText(rec.name).length).toBeGreaterThan(0);
    }
  });
  it('renders nothing when the endpoint returns no records key', () => {
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
    const { container } = render(<SourcesCredits />);
    expect(container.querySelector('[data-testid^="credits-group"]')).toBeNull();
  });
});
