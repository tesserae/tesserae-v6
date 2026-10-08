import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CiteButton from '../CiteButton';

const finding = { source: { work: 'vergil.aeneid', ref: '1.1', text: 'arma virumque cano' }, target: { work: 'lucan.bellum_civile', ref: '1.1', text: 'bella per Emathios' } };

describe('CiteButton card-level report link', () => {
  it('shows "Report a problem" beside Cite when asked', () => {
    render(<CiteButton finding={finding} showReportLink />);
    expect(screen.getByRole('button', { name: /Report a problem/ })).toBeTruthy();
  });
  it('shows no card-level link by default', () => {
    render(<CiteButton finding={finding} />);
    expect(screen.queryByRole('button', { name: /Report a problem/ })).toBeNull();
  });
});
