/**
 * ThinkingIndicator tests — goblin-skeptic check on the DM thinking indicator.
 *
 * The component ALWAYS renders the "Thinking" label + dots in the DOM; it
 * toggles visibility via CSS classes (visible / hidden).  We test the class
 * application, not the CSS animation itself.
 *
 * Covers: visible state, hidden state, default state, aria attributes, and
 * toggle transitions.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { useGameStore } from '../../stores/gameStore'
import ThinkingIndicator from './ThinkingIndicator'

function resetStore(): void {
  useGameStore.setState({
    isThinking: false,
  })
}

beforeEach(() => {
  resetStore()
})

/* ------------------------------------------------------------------ */
/*  Visibility via CSS classes                                         */
/* ------------------------------------------------------------------ */

describe('ThinkingIndicator — visibility', () => {
  it('applies "visible" class when isThinking is true', () => {
    useGameStore.setState({ isThinking: true })
    const { container } = render(<ThinkingIndicator />)
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper.className).toMatch(/visible/)
  })

  it('applies "hidden" class when isThinking is false', () => {
    useGameStore.setState({ isThinking: false })
    const { container } = render(<ThinkingIndicator />)
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper.className).toMatch(/hidden/)
  })

  it('applies "hidden" class by default (isThinking starts false)', () => {
    const { container } = render(<ThinkingIndicator />)
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper.className).toMatch(/hidden/)
  })
})

/* ------------------------------------------------------------------ */
/*  Text is always rendered (CSS only hides it)                        */
/* ------------------------------------------------------------------ */

describe('ThinkingIndicator — text content', () => {
  it('renders "Thinking" label even when hidden', () => {
    useGameStore.setState({ isThinking: false })
    render(<ThinkingIndicator />)
    expect(screen.getByText('Thinking')).toBeInTheDocument()
  })

  it('renders "Thinking" label when visible', () => {
    useGameStore.setState({ isThinking: true })
    render(<ThinkingIndicator />)
    expect(screen.getByText('Thinking')).toBeInTheDocument()
  })

  it('renders three dots', () => {
    useGameStore.setState({ isThinking: true })
    const { container } = render(<ThinkingIndicator />)
    // Find the dots container (has class containing "dots"), then count its children
    const dotsWrapper = container.querySelector('[class*="dots"]')
    expect(dotsWrapper).toBeTruthy()
    expect(dotsWrapper!.children).toHaveLength(3)
  })
})

/* ------------------------------------------------------------------ */
/*  ARIA attributes                                                    */
/* ------------------------------------------------------------------ */

describe('ThinkingIndicator — accessibility', () => {
  it('has role="status" and aria-live="polite"', () => {
    useGameStore.setState({ isThinking: true })
    render(<ThinkingIndicator />)
    const el = screen.getByRole('status')
    expect(el).toHaveAttribute('aria-live', 'polite')
  })

  it('has aria-label "DM is thinking" when visible', () => {
    useGameStore.setState({ isThinking: true })
    render(<ThinkingIndicator />)
    const el = screen.getByRole('status')
    expect(el).toHaveAttribute('aria-label', 'DM is thinking')
  })

  it('does not have aria-label when hidden', () => {
    useGameStore.setState({ isThinking: false })
    render(<ThinkingIndicator />)
    const el = screen.getByRole('status')
    expect(el).not.toHaveAttribute('aria-label')
  })
})

/* ------------------------------------------------------------------ */
/*  Toggle transitions                                                 */
/* ------------------------------------------------------------------ */

describe('ThinkingIndicator — toggle transitions', () => {
  it('switches from hidden to visible class when isThinking becomes true', () => {
    const { container, rerender } = render(<ThinkingIndicator />)
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper.className).toMatch(/hidden/)

    act(() => useGameStore.setState({ isThinking: true }))
    rerender(<ThinkingIndicator />)

    expect(wrapper.className).toMatch(/visible/)
  })

  it('switches from visible to hidden class when isThinking becomes false', () => {
    useGameStore.setState({ isThinking: true })
    const { container, rerender } = render(<ThinkingIndicator />)
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper.className).toMatch(/visible/)

    act(() => useGameStore.setState({ isThinking: false }))
    rerender(<ThinkingIndicator />)

    expect(wrapper.className).toMatch(/hidden/)
  })
})
