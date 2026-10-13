import { describe, expect, it } from 'vitest';
import { decodeEntities } from './htmlEntities';

describe('decodeEntities', () => {
  it('decodes an ampersand', () => {
    expect(decodeEntities('Boston: Ginn &amp; Co., 1900')).toBe('Boston: Ginn & Co., 1900');
  });
  it('decodes a numeric apostrophe', () => {
    expect(decodeEntities('Virgil&#39;s Aeneid')).toBe("Virgil's Aeneid");
  });
  it('leaves a plain string and angle-bracket entities alone', () => {
    expect(decodeEntities('Teubner, 1900')).toBe('Teubner, 1900');
    expect(decodeEntities('a &lt;b&gt;')).toBe('a &lt;b&gt;');
  });
});
