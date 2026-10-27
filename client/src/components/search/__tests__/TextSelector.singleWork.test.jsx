import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import TextSelector from '../TextSelector';

const hierarchy = [
  { author_key: 'acts', works: [{ work: 'Pilate', sections: [{ label: '(Complete)', file: 'acts.pilate.tess' }] }] },
  { author_key: 'lucan', works: [{ work: 'Bellum Civile', sections: [
    { label: '(Complete)', file: 'lucan.bellum_civile.tess' },
    { label: 'Book 1', file: 'lucan.bellum_civile.part.1.tess' },
  ] }] },
];

const renderFor = (author, selectedText = '') => {
  const setSelectedText = vi.fn();
  render(
    <TextSelector label="Target" language="cop" authors={[]} selectedAuthor={author}
      setSelectedAuthor={() => {}} selectedText={selectedText} setSelectedText={setSelectedText}
      hierarchy={hierarchy} fetchTexts={() => Promise.resolve({ texts: [] })} />
  );
  return setSelectedText;
};

describe('TextSelector chooses an author\'s only work', () => {
  it('fills in the work when the author has a single choice', () => {
    expect(renderFor('acts')).toHaveBeenCalledWith('acts.pilate.tess');
  });
  it('leaves the choice to the visitor when there are several', () => {
    expect(renderFor('lucan')).not.toHaveBeenCalled();
  });
  it('does not replace a work already chosen', () => {
    expect(renderFor('acts', 'other.tess')).not.toHaveBeenCalled();
  });
});
