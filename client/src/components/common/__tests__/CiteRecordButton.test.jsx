import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CiteRecordButton from '../CiteRecordButton';
import CiteAll from '../CiteAll';
import { resetEditions } from '../../../utils/citations';

const REC = {
  type: 'article', title: 'Mutiny and Madness', authors: ['A. J. Woodman'], year: '2006', venue: 'Arethusa',
  volume: '39', issue: '2', doi: '10.1353/are.2006.0014',
};
const REC2 = { type: 'thesis', title: 'The Hunt', authors: ['Alyson Wright'], year: '1996', venue: 'Durham e-Theses' };

let blobs;
let clicked;
beforeEach(() => {
  resetEditions();
  blobs = [];
  clicked = [];
  URL.createObjectURL = vi.fn((b) => { blobs.push(b); return 'blob:x'; });
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function click() { clicked.push(this.download); });
});
afterEach(() => { vi.restoreAllMocks(); });

const readBlob = (b) => new Promise((res) => { const f = new FileReader(); f.onload = () => res(f.result); f.readAsText(b); });

function mockClipboard() {
  const writeText = vi.fn(async () => {});
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
  return writeText;
}

describe('CiteRecordButton', () => {
  it('opens a box with the reference and the four actions, and closes on Escape', async () => {
    const user = userEvent.setup();
    render(<CiteRecordButton record={REC} />);
    expect(screen.queryByRole('dialog')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Cite' }));
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(screen.getByLabelText('Reference').value).toContain('Woodman, A. J. 2006.');
    for (const n of ['Copy', 'Copy RIS', 'RIS file', 'BibTeX']) expect(screen.getByRole('button', { name: n })).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Copy' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cite' }));
  });

  it('closes on a click elsewhere and on scroll', async () => {
    const user = userEvent.setup();
    render(<div><CiteRecordButton record={REC} /><p>elsewhere</p></div>);
    await user.click(screen.getByRole('button', { name: 'Cite' }));
    await user.click(screen.getByText('elsewhere'));
    expect(screen.queryByRole('dialog')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Cite' }));
    fireEvent.scroll(window);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('keeps one box open at a time', async () => {
    const user = userEvent.setup();
    render(<div><CiteRecordButton record={REC} /><CiteRecordButton record={REC2} /></div>);
    const [a, b] = screen.getAllByRole('button', { name: 'Cite' });
    await user.click(a);
    await user.click(b);
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
    expect(screen.getByLabelText('Reference').value).toContain('Wright, Alyson');
  });

  it('copies the line and the RIS, and shows copied', async () => {
    const user = userEvent.setup();
    const writeText = mockClipboard();
    render(<CiteRecordButton record={REC} />);
    await user.click(screen.getByRole('button', { name: 'Cite' }));
    await user.click(screen.getByRole('button', { name: 'Copy' }));
    expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining('"Mutiny and Madness."'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'copied' })).toBeTruthy());
    expect(screen.getByRole('button', { name: 'Copy RIS' }).title).toMatch(/Import from Clipboard/);
    await user.click(screen.getByRole('button', { name: 'Copy RIS' }));
    expect(writeText).toHaveBeenLastCalledWith(expect.stringMatching(/^TY {2}- JOUR\n/));
  });

  it('downloads the RIS and the BibTeX files', async () => {
    const user = userEvent.setup();
    render(<CiteRecordButton record={REC} />);
    await user.click(screen.getByRole('button', { name: 'Cite' }));
    await user.click(screen.getByRole('button', { name: 'RIS file' }));
    await user.click(screen.getByRole('button', { name: 'BibTeX' }));
    expect(clicked).toEqual(['woodman2006mutiny.ris', 'woodman2006mutiny.bib']);
    expect(await readBlob(blobs[0])).toContain('TY  - JOUR');
    expect(await readBlob(blobs[1])).toContain('@article{woodman2006mutiny,');
  });

  it('looks up the edition of a commentary note when the box opens', async () => {
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ commentaries: [{ commentator: 'Servius', edition: 'A. B, eds., Title (Leipzig: Teubner, 1878)' }] }) }));
    const user = userEvent.setup();
    render(<CiteRecordButton record={{ type: 'commentary', commentator: 'Servius', work: 'vergil.aeneid', ref_start: '1.1' }} />);
    await user.click(screen.getByRole('button', { name: 'Cite' }));
    await waitFor(() => expect(screen.getByLabelText('Reference').value).toContain('Leipzig: Teubner'));
  });
});

describe('CiteAll', () => {
  it('is absent under two records', () => {
    const { container, rerender } = render(<CiteAll records={[REC]} name="x" />);
    expect(container.textContent).toBe('');
    rerender(<CiteAll records={[]} name="x" />);
    expect(container.textContent).toBe('');
  });

  it('downloads one file holding every record, named from the question', async () => {
    const user = userEvent.setup();
    render(<CiteAll records={[REC, REC2]} name="Dido in love / Vergil" />);
    await user.click(screen.getByRole('button', { name: 'RIS' }));
    await waitFor(() => expect(clicked).toEqual(['Dido_in_love_Vergil.ris']));
    const ris = await readBlob(blobs[0]);
    expect(ris.match(/ER {2}- /g)).toHaveLength(2);
    await user.click(screen.getByRole('button', { name: 'BibTeX' }));
    await waitFor(() => expect(clicked[1]).toBe('Dido_in_love_Vergil.bib'));
    const bib = await readBlob(blobs[1]);
    expect(bib).toContain('@article{woodman2006mutiny,');
    expect(bib).toContain('@phdthesis{wright1996hunt,');
  });
});
