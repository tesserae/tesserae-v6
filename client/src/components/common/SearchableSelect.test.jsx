/**
 * The type-to-find dropdown: a regular menu that can also be filtered by
 * typing the first letters of a name.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import SearchableSelect from './SearchableSelect';

const LATIN_AUTHORS = [
  { value: 'cicero', label: 'Cicero' },
  { value: 'curtius_rufus', label: 'Curtius Rufus' },
  { value: 'lucretius', label: 'Lucretius' },
  { value: 'securus', label: 'Securus' },
];

function mount(props = {}) {
  const onChange = vi.fn();
  render(
    <SearchableSelect
      value={props.value ?? ''}
      onChange={onChange}
      options={props.options ?? LATIN_AUTHORS}
      ariaLabel={props.ariaLabel ?? 'Author'}
      placeholder={props.placeholder}
      disabled={props.disabled}
    />
  );
  return { onChange };
}

describe('opening the control', () => {
  it('shows the full list, not a filtered one, when clicked open', () => {
    mount();
    const input = screen.getByRole('combobox', { name: 'Author' });
    fireEvent.click(input);
    const listbox = screen.getByRole('listbox', { name: 'Author' });
    const options = within(listbox).getAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual(
      ['Cicero', 'Curtius Rufus', 'Lucretius', 'Securus']
    );
  });

  it('highlights and scrolls the current choice into view', () => {
    const scrolled = [];
    window.HTMLElement.prototype.scrollIntoView = function () { scrolled.push(this.textContent); };
    mount({ value: 'lucretius' });
    fireEvent.click(screen.getByRole('combobox', { name: 'Author' }));
    expect(scrolled).toContain('Lucretius');
    const listbox = screen.getByRole('listbox', { name: 'Author' });
    const current = within(listbox).getByRole('option', { name: 'Lucretius' });
    expect(current).toHaveAttribute('aria-selected', 'true');
  });
});

describe('typing filters, start-of-word matches first', () => {
  it('puts "Curtius Rufus" first for "cur" and still lists "Securus" after it', () => {
    mount();
    const input = screen.getByRole('combobox', { name: 'Author' });
    fireEvent.click(input);
    fireEvent.change(input, { target: { value: 'cur' } });
    const listbox = screen.getByRole('listbox', { name: 'Author' });
    const options = within(listbox).getAllByRole('option').map((o) => o.textContent);
    expect(options[0]).toBe('Curtius Rufus');
    expect(options).toContain('Securus');
    expect(options.indexOf('Curtius Rufus')).toBeLessThan(options.indexOf('Securus'));
    expect(options).not.toContain('Cicero');
    expect(options).not.toContain('Lucretius');
  });
});

describe('diacritics are ignored', () => {
  it('finds "Theocritus" by "theo"', () => {
    mount({ options: [{ value: 'theocritus', label: 'Theocritus' }, { value: 'other', label: 'Other' }] });
    const input = screen.getByRole('combobox', { name: 'Author' });
    fireEvent.click(input);
    fireEvent.change(input, { target: { value: 'theo' } });
    const listbox = screen.getByRole('listbox', { name: 'Author' });
    expect(within(listbox).getAllByRole('option').map((o) => o.textContent)).toEqual(['Theocritus']);
  });

  it('finds "Θεόκριτος" (accented) by "θεο" (bare)', () => {
    mount({ options: [
      { value: 'theocritus_grc', label: 'Θεόκριτος' },
      { value: 'other', label: 'Ἀριστοτέλης' },
    ] });
    const input = screen.getByRole('combobox', { name: 'Author' });
    fireEvent.click(input);
    fireEvent.change(input, { target: { value: 'θεο' } });
    const listbox = screen.getByRole('listbox', { name: 'Author' });
    expect(within(listbox).getAllByRole('option').map((o) => o.textContent))
      .toEqual(['Θεόκριτος']);
  });
});

describe('keyboard behaviour', () => {
  it('Enter chooses the highlighted option', () => {
    const { onChange } = mount();
    const input = screen.getByRole('combobox', { name: 'Author' });
    fireEvent.click(input);
    fireEvent.change(input, { target: { value: 'cur' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith('curtius_rufus');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('ArrowDown then Enter chooses the next option', () => {
    const { onChange } = mount();
    const input = screen.getByRole('combobox', { name: 'Author' });
    fireEvent.click(input);
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith('curtius_rufus');
  });

  it('Escape closes and restores the previous value, discarding the typed filter', () => {
    const { onChange } = mount({ value: 'cicero' });
    const input = screen.getByRole('combobox', { name: 'Author' });
    fireEvent.click(input);
    fireEvent.change(input, { target: { value: 'lucr' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(screen.getByRole('combobox', { name: 'Author' }).value).toBe('Cicero');
  });

  it('Home and End jump to the first and last option', () => {
    const { onChange } = mount();
    const input = screen.getByRole('combobox', { name: 'Author' });
    fireEvent.click(input);
    fireEvent.keyDown(input, { key: 'End' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith('securus');
  });
});

describe('closing without choosing', () => {
  it('keeps the previous value when a click lands outside', () => {
    const { onChange } = mount({ value: 'cicero' });
    const input = screen.getByRole('combobox', { name: 'Author' });
    fireEvent.click(input);
    fireEvent.change(input, { target: { value: 'lucr' } });
    fireEvent.pointerDown(document.body);
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole('combobox', { name: 'Author' }).value).toBe('Cicero');
  });
});

describe('phones', () => {
  it('renders a native select with the same options', () => {
    const { container } = render(
      <SearchableSelect value="cicero" onChange={() => {}} options={LATIN_AUTHORS} ariaLabel="Author" />
    );
    const native = container.querySelector('select.sm\\:hidden');
    expect(native).toBeTruthy();
    expect([...native.options].map((o) => o.textContent)).toEqual(
      ['Cicero', 'Curtius Rufus', 'Lucretius', 'Securus']
    );
    expect(native.value).toBe('cicero');
  });
});
