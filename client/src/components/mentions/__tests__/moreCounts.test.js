import { describe, it, expect } from 'vitest';
import { moreCounts } from '../MentionsPage';

describe('moreCounts', () => {
  it('names adjective lines and documents for a place with no direct mention', () => {
    expect(moreCounts({ adjective_lines: 3, document_counts: { la: 6 } }))
      .toBe('named by its adjective in 3 lines · 6 inscriptions and papyri');
    expect(moreCounts({ adjective_lines: 1 })).toBe('named by its adjective in 1 line');
    expect(moreCounts({})).toBe('');
  });
});
