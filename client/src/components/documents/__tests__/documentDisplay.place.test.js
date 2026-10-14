import { describe, expect, it } from 'vitest';
import { documentPlace, documentLabels } from '../documentDisplay';

describe('the findspot line and the chips of a document', () => {
  it('writes out Hr. as Henchir', () => {
    expect(documentPlace({ modern_place: 'Hr. Oumkif' })).toBe('Henchir Oumkif');
    expect(documentPlace({ ancient_place: 'Thugga', modern_place: 'Hr. Dougga' })).toBe('Thugga');
    expect(documentPlace({})).toBeNull();
  });
  it('leaves out chips that only say unknown', () => {
    expect(documentLabels({ text_type_label: 'unknown', object_type_label: 'unknown', material_label: 'unknown' })).toEqual([]);
    expect(documentLabels({ text_type_label: 'epitaph', object_type_label: 'Unknown', material_label: 'limestone' })).toEqual(['epitaph', 'limestone']);
  });
});
