import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { fixEscapes, CitationHead } from './ScholarshipTab';

describe('Scholarship citation head', () => {
  it('decodes literal escapes in names', () => {
    expect(fixEscapes('Manjavacas Ar\\ue9valo, Enrique')).toBe('Manjavacas Arévalo, Enrique');
    expect(fixEscapes('Ar\\u00e9valo')).toBe('Arévalo');
    expect(fixEscapes('plain')).toBe('plain');
  });
  it('starts with the title when no author is named', () => {
    const { container } = render(<p><CitationHead authors={[]} year="2021" title="Ilias Latina" /></p>);
    expect(container.textContent).toBe('Ilias Latina (2021)');
    expect(container.textContent).not.toMatch(/Unknown/);
  });
  it('keeps authors, year and title in order', () => {
    const { container } = render(<p><CitationHead authors={['A', 'B', 'C', 'D']} year="2015" title="T" others /></p>);
    expect(container.textContent).toBe('A, B, C and others (2015). T');
  });
});
