import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import OriginalScript from './OriginalScript';
import TransliterationToggle from './TransliterationToggle';
import { setOn } from '../../utils/transliterationSetting';

beforeEach(() => {
  window.localStorage.clear();
});

describe('OriginalScript', () => {
  it('shows the Greek with its language and a transliteration after it', () => {
    const { container } = render(<p><OriginalScript text="How and Wells take τὸ εὖ ζῆν (the good life) [1]." /></p>);
    const greek = container.querySelector('span[lang="grc"]');
    expect(greek).toHaveTextContent('τὸ εὖ ζῆν');
    expect(container).toHaveTextContent('τὸ εὖ ζῆν (to eu zēn) (the good life) [1].');
  });

  it('marks Hebrew right to left and transliterates it', () => {
    const { container } = render(<p><OriginalScript text="the word שָׁלוֹם here" /></p>);
    const he = container.querySelector('span[lang="he"]');
    expect(he).toHaveAttribute('dir', 'rtl');
    expect(container).toHaveTextContent('(shalom)');
  });

  it('hides the transliteration when the setting is off', () => {
    setOn(false);
    const { container } = render(<p><OriginalScript text="τὸ εὖ ζῆν" /></p>);
    expect(container.querySelector('span[lang="grc"]')).toHaveTextContent('τὸ εὖ ζῆν');
    expect(container).not.toHaveTextContent('zēn');
  });

  it('leaves English alone', () => {
    const { container } = render(<p><OriginalScript text="Plain English with no Greek." /></p>);
    expect(container.innerHTML).toBe('<p>Plain English with no Greek.</p>');
  });

  it('the toggle flips the setting and the rendering', () => {
    const { container } = render(<div><TransliterationToggle /><p><OriginalScript text="ζῆν" /></p></div>);
    expect(container).toHaveTextContent('(zēn)');
    fireEvent.click(screen.getByTestId('transliteration-toggle'));
    expect(screen.getByTestId('transliteration-toggle')).toHaveTextContent('Show transliterations');
    expect(container).not.toHaveTextContent('(zēn)');
    expect(window.localStorage.getItem('tesserae:transliterate')).toBe('off');
    act(() => setOn(true));
    expect(container).toHaveTextContent('(zēn)');
  });
});
