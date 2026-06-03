import '@testing-library/jest-dom'

/**
 * Mock window.matchMedia for jsdom (used by responsive components).
 * Returns a MediaQueryList that defaults to not matching.
 */
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})
