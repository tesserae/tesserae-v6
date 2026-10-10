import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import StartHere from '../StartHere';
import Header from '../../layout/Header';
import { FRONT_DOOR_CHOICES } from '../frontDoor';

const QUESTION = 'What are you trying to do?';

beforeEach(() => {
  window.localStorage.clear();
  window.history.pushState({}, '', '/');
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
});

describe('StartHere', () => {
  it('shows on a first visit with six answers', () => {
    render(<StartHere />);
    expect(screen.getByText(QUESTION)).toBeTruthy();
    expect(screen.getAllByRole('link')).toHaveLength(6);
  });

  it('hides after an answer and remembers it', () => {
    render(<StartHere onChoose={() => {}} />);
    fireEvent.click(screen.getAllByRole('link')[0]);
    expect(screen.queryByText(QUESTION)).toBeNull();
    expect(window.localStorage.getItem('tesserae_front_door')).toBe('seen');
  });

  it('hides after "Skip this" and remembers it', () => {
    render(<StartHere />);
    fireEvent.click(screen.getByRole('button', { name: 'Skip this' }));
    expect(screen.queryByText(QUESTION)).toBeNull();
    expect(window.localStorage.getItem('tesserae_front_door')).toBe('seen');
  });

  it('does not show when it has been seen', () => {
    window.localStorage.setItem('tesserae_front_door', 'seen');
    render(<StartHere />);
    expect(screen.queryByText(QUESTION)).toBeNull();
  });

  it('does not show when the address carries a search', () => {
    window.history.pushState({}, '', '/?tab=line');
    render(<StartHere />);
    expect(screen.queryByText(QUESTION)).toBeNull();
  });

  it('treats a storage error as seen', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied'); });
    render(<StartHere />);
    expect(screen.queryByText(QUESTION)).toBeNull();
    spy.mockRestore();
  });

  it('each answer leads to its href', () => {
    const chosen = vi.fn();
    render(<StartHere onChoose={chosen} />);
    FRONT_DOOR_CHOICES.forEach((choice) => {
      expect(screen.getByText(choice.label).closest('a').getAttribute('href')).toBe(choice.href);
    });
    fireEvent.click(screen.getByText(FRONT_DOOR_CHOICES[3].label));
    expect(chosen).toHaveBeenCalledWith(FRONT_DOOR_CHOICES[3]);
  });

  it('the header link shows it again', () => {
    window.localStorage.setItem('tesserae_front_door', 'seen');
    render(<><Header user={null} setUser={() => {}} onLogoClick={() => {}} /><StartHere /></>);
    expect(screen.queryByText(QUESTION)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Start here' }));
    expect(screen.getByText(QUESTION)).toBeTruthy();
  });
});
