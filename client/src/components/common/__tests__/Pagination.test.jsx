import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Pagination, { getPageWindow, ELLIPSIS } from '../Pagination';

const defaults = {
  currentPage: 1,
  totalPages: 5,
  totalResults: 237,
  pageSize: 50,
  onPageChange: () => {},
  onPageSizeChange: () => {},
};

const renderPagination = (props = {}) =>
  render(<Pagination {...defaults} {...props} />);

const pageButton = (n) => screen.getByRole('button', { name: `Go to page ${n}` });

describe('Pagination — page-size selector', () => {
  it('offers exactly four options', () => {
    renderPagination();
    const options = within(screen.getByRole('combobox')).getAllByRole('option');
    expect(options).toHaveLength(4);
  });

  it('offers exactly the values 10, 20, 50 and 100', () => {
    renderPagination();
    const values = within(screen.getByRole('combobox'))
      .getAllByRole('option')
      .map((o) => o.value);
    expect(values).toEqual(['10', '20', '50', '100']);
  });

  it('offers no option above 100', () => {
    renderPagination();
    const values = within(screen.getByRole('combobox'))
      .getAllByRole('option')
      .map((o) => Number(o.value));
    expect(Math.max(...values)).toBe(100);
    values.forEach((v) => expect(v).toBeLessThanOrEqual(100));
  });

  it('reports the chosen size as a number, not a string', async () => {
    const onPageSizeChange = vi.fn();
    renderPagination({ onPageSizeChange });
    await userEvent.selectOptions(screen.getByRole('combobox'), '20');
    expect(onPageSizeChange).toHaveBeenCalledWith(20);
    expect(typeof onPageSizeChange.mock.calls[0][0]).toBe('number');
  });

  it('has an accessible label', () => {
    renderPagination();
    expect(screen.getByLabelText('Show')).toBe(screen.getByRole('combobox'));
  });
});

describe('Pagination — result summary', () => {
  it('reads "Showing 1–50 of 237 results" on page 1', () => {
    renderPagination();
    expect(screen.getByText('Showing 1–50 of 237 results')).toBeInTheDocument();
  });

  it('reads "Showing 51–100 of 237 results" on page 2', () => {
    renderPagination({ currentPage: 2 });
    expect(screen.getByText('Showing 51–100 of 237 results')).toBeInTheDocument();
  });

  it('reads "Showing 201–237 of 237 results" on the last page', () => {
    renderPagination({ currentPage: 5 });
    expect(screen.getByText('Showing 201–237 of 237 results')).toBeInTheDocument();
  });

  it('announces politely for assistive technology', () => {
    renderPagination();
    expect(screen.getByText('Showing 1–50 of 237 results'))
      .toHaveAttribute('aria-live', 'polite');
  });

  it('uses a caller-supplied item label', () => {
    renderPagination({ itemLabel: 'rare words' });
    expect(screen.getByText('Showing 1–50 of 237 rare words')).toBeInTheDocument();
  });
});

describe('Pagination — navigation', () => {
  it('disables Previous on the first page', () => {
    renderPagination({ currentPage: 1 });
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled();
  });

  it('disables Next on the last page', () => {
    renderPagination({ currentPage: 5 });
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled();
  });

  it('marks the active page with aria-current', () => {
    renderPagination({ currentPage: 3 });
    expect(pageButton(3)).toHaveAttribute('aria-current', 'page');
    expect(pageButton(2)).not.toHaveAttribute('aria-current');
  });

  it('reports the requested page number when a number is clicked', async () => {
    const onPageChange = vi.fn();
    renderPagination({ onPageChange });
    await userEvent.click(pageButton(3));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it('reports the neighbouring page for Previous and Next', async () => {
    const onPageChange = vi.fn();
    renderPagination({ currentPage: 3, onPageChange });
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(onPageChange).toHaveBeenCalledWith(4);
    await userEvent.click(screen.getByRole('button', { name: 'Previous' }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('labels the navigation region', () => {
    renderPagination();
    expect(screen.getByRole('navigation', { name: 'Search results pagination' }))
      .toBeInTheDocument();
  });

  it('disables every control when disabled is set', () => {
    renderPagination({ currentPage: 3, disabled: true });
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    expect(pageButton(2)).toBeDisabled();
    expect(screen.getByRole('combobox')).toBeDisabled();
  });
});

describe('Pagination — visibility rules', () => {
  it('hides navigation but keeps the selector and summary on a single page', () => {
    renderPagination({ totalResults: 30, totalPages: 1, pageSize: 50 });
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getByText('Showing 1–30 of 30 results')).toBeInTheDocument();
  });

  it('shows navigation as soon as the total exceeds the page size', () => {
    renderPagination({ totalResults: 51, totalPages: 2, pageSize: 50 });
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });

  it('renders nothing at all for zero results', () => {
    const { container } = renderPagination({ totalResults: 0, totalPages: 1 });
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
  });

  it('renders nothing for the nav variant when there is only one page', () => {
    const { container } = renderPagination({
      variant: 'nav', totalResults: 30, totalPages: 1, pageSize: 50,
    });
    expect(container).toBeEmptyDOMElement();
  });

  it('renders navigation only — no selector or summary — for the nav variant', () => {
    renderPagination({ variant: 'nav' });
    expect(screen.getByRole('navigation')).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
  });
});

describe('getPageWindow — compact windowing', () => {
  it('lists every page when there are seven or fewer', () => {
    expect(getPageWindow(1, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(getPageWindow(4, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it('keeps at most seven slots for large page counts', () => {
    [1, 5, 10, 47, 100].forEach((page) => {
      expect(getPageWindow(page, 100)).toHaveLength(7);
    });
  });

  it('anchors to the start near the beginning', () => {
    expect(getPageWindow(2, 100)).toEqual([1, 2, 3, 4, 5, ELLIPSIS, 100]);
  });

  it('anchors to the end near the last page', () => {
    expect(getPageWindow(99, 100)).toEqual([1, ELLIPSIS, 96, 97, 98, 99, 100]);
  });

  it('centres on the active page in the middle', () => {
    expect(getPageWindow(50, 100)).toEqual([1, ELLIPSIS, 49, 50, 51, ELLIPSIS, 100]);
  });

  it('always includes the first and last page', () => {
    [1, 5, 50, 96, 100].forEach((page) => {
      const win = getPageWindow(page, 100);
      expect(win[0]).toBe(1);
      expect(win[win.length - 1]).toBe(100);
    });
  });

  it('renders ellipses as non-interactive, hidden text', () => {
    renderPagination({ currentPage: 50, totalPages: 100, totalResults: 5000 });
    const nav = screen.getByRole('navigation');
    const ellipses = within(nav).getAllByText(ELLIPSIS);
    expect(ellipses.length).toBeGreaterThan(0);
    ellipses.forEach((el) => {
      expect(el.tagName).toBe('SPAN');
      expect(el).toHaveAttribute('aria-hidden', 'true');
    });
  });

  it('does not render hundreds of buttons for a large page count', () => {
    renderPagination({ currentPage: 50, totalPages: 100, totalResults: 5000 });
    const nav = screen.getByRole('navigation');
    // 5 numbered pages + Previous + Next
    expect(within(nav).getAllByRole('button')).toHaveLength(7);
  });
});
