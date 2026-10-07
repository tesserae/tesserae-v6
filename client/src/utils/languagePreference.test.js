import { describe, it, expect, beforeEach } from 'vitest';
import { getStartSetting, setStartSetting, rememberLanguage, startLanguage, START_LAST } from './languagePreference';

beforeEach(() => { window.localStorage.clear(); });

describe('language preference', () => {
  it('has no preference on a first visit', () => {
    expect(getStartSetting()).toBe(START_LAST);
    expect(startLanguage()).toBeNull();
  });

  it('opens in the language used last by default', () => {
    rememberLanguage('fa');
    expect(startLanguage()).toBe('fa');
    rememberLanguage('grc');
    expect(startLanguage()).toBe('grc');
  });

  it('a fixed start language wins over the last one used', () => {
    setStartSetting('la');
    rememberLanguage('fa');
    expect(startLanguage()).toBe('la');
    setStartSetting(START_LAST);
    expect(startLanguage()).toBe('fa');
  });

  it('respects what the page can show', () => {
    rememberLanguage('cross');
    expect(startLanguage(['la', 'grc'])).toBeNull();
    expect(startLanguage()).toBe('cross');
  });

  it('survives storage that throws', () => {
    const real = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      configurable: true, get() { throw new Error('blocked'); } });
    try {
      expect(startLanguage()).toBeNull();
      expect(() => rememberLanguage('fa')).not.toThrow();
      expect(() => setStartSetting('la')).not.toThrow();
    } finally {
      Object.defineProperty(window, 'localStorage', { configurable: true, value: real });
    }
  });
});
