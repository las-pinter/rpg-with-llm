/**
 * NarrativeStream tests — goblin-skeptic scrutiny of the scrollable narrative pane.
 *
 * Covers: empty state, all 5 entry types, rendering order, newline-to-paragraph
 * conversion, auto-scroll behavior, scroll-to-bottom button appearance and
 * interaction, unique keyed entries, and long-content rendering.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useGameStore } from '../../stores/gameStore'
import type { NarrativeEntry } from '../../stores/gameStore'
import NarrativeStream from './NarrativeStream'

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function addEntries(entries: NarrativeEntry[]): void {
  act(() => {
    useGameStore.setState({ narrativeEntries: entries })
  })
}

function resetStore(): void {
  act(() => {
    useGameStore.setState({
      narrativeEntries: [],
      isThinking: false,
      npcThinking: null,
    })
  })
}

beforeEach(() => {
  resetStore()
})

afterEach(() => {
  resetStore()
})

/* ------------------------------------------------------------------ */
/*  Empty state                                                        */
/* ------------------------------------------------------------------ */

describe('NarrativeStream — empty state', () => {
  it('renders "The adventure awaits…" when no entries exist', () => {
    render(<NarrativeStream />)
    expect(screen.getByText('The adventure awaits…')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  All 5 entry types                                                  */
/* ------------------------------------------------------------------ */

describe('NarrativeStream — entry types', () => {
  it('renders a player entry with player-formatted content', () => {
    addEntries([
      { id: 'p1', type: 'player', content: 'I draw my sword', timestamp: 1 },
    ])
    render(<NarrativeStream />)
    expect(screen.getByText('I draw my sword')).toBeInTheDocument()
  })

  it('renders a narrative entry with narrative text', () => {
    addEntries([
      { id: 'n1', type: 'narrative', content: 'The goblin cackles.', timestamp: 2 },
    ])
    render(<NarrativeStream />)
    expect(screen.getByText('The goblin cackles.')).toBeInTheDocument()
  })

  it('renders a tool_result entry with italic content', () => {
    addEntries([
      { id: 't1', type: 'tool_result', content: 'Rolled 18 on Persuasion', timestamp: 3 },
    ])
    render(<NarrativeStream />)
    const el = screen.getByText('Rolled 18 on Persuasion')
    expect(el).toBeInTheDocument()
    expect(el.tagName).toBe('EM')
  })

  it('renders a separator entry with decorative glyph', () => {
    addEntries([
      { id: 's1', type: 'separator', content: '', timestamp: 4 },
    ])
    const { container } = render(<NarrativeStream />)
    // The ✦ has aria-hidden="true", so bypass default ignore
    expect(container.textContent).toContain('✦')
  })

  it('renders an error entry with role="alert"', () => {
    addEntries([
      { id: 'e1', type: 'error', content: 'Failed to connect', timestamp: 5 },
    ])
    render(<NarrativeStream />)
    const el = screen.getByText('Failed to connect')
    expect(el).toBeInTheDocument()
    expect(el.closest('[role="alert"]')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  All 5 types together + order                                       */
/* ------------------------------------------------------------------ */

describe('NarrativeStream — multiple entries', () => {
  it('renders all 5 entry types simultaneously', () => {
    const entries: NarrativeEntry[] = [
      { id: 'a', type: 'player', content: 'Hello', timestamp: 1 },
      { id: 'b', type: 'narrative', content: 'World', timestamp: 2 },
      { id: 'c', type: 'tool_result', content: 'Roll 20', timestamp: 3 },
      { id: 'd', type: 'separator', content: '', timestamp: 4 },
      { id: 'e', type: 'error', content: 'Oops', timestamp: 5 },
    ]
    addEntries(entries)
    render(<NarrativeStream />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(screen.getByText('World')).toBeInTheDocument()
    expect(screen.getByText('Roll 20')).toBeInTheDocument()
    expect(screen.getByText('Oops')).toBeInTheDocument()
    // The container should contain the separator glyph
    expect(screen.queryByText('✦', { ignore: '' })).toBeInTheDocument()
  })

  it('renders entries in the order they were added', () => {
    const entries: NarrativeEntry[] = [
      { id: 'o1', type: 'narrative', content: 'First paragraph', timestamp: 1 },
      { id: 'o2', type: 'narrative', content: 'Second paragraph', timestamp: 2 },
      { id: 'o3', type: 'narrative', content: 'Third paragraph', timestamp: 3 },
    ]
    addEntries(entries)
    const { container } = render(<NarrativeStream />)
    const paragraphs = container.querySelectorAll('p')
    expect(paragraphs).toHaveLength(3)
    expect(paragraphs[0]).toHaveTextContent('First paragraph')
    expect(paragraphs[1]).toHaveTextContent('Second paragraph')
    expect(paragraphs[2]).toHaveTextContent('Third paragraph')
  })
})

/* ------------------------------------------------------------------ */
/*  Newline handling                                                   */
/* ------------------------------------------------------------------ */

describe('NarrativeStream — newline splitting', () => {
  it('splits narrative content on newlines into separate <p> elements', () => {
    addEntries([
      {
        id: 'nl1',
        type: 'narrative',
        content: 'Line one\n\nLine two\nLine three',
        timestamp: 1,
      },
    ])
    const { container } = render(<NarrativeStream />)
    const paragraphs = container.querySelectorAll('p')
    // "Line one", "Line two", "Line three" after split + filter(Boolean)
    expect(paragraphs).toHaveLength(3)
    expect(paragraphs[0]).toHaveTextContent('Line one')
    expect(paragraphs[1]).toHaveTextContent('Line two')
    expect(paragraphs[2]).toHaveTextContent('Line three')
  })

  it('handles single-line narrative without splitting', () => {
    addEntries([
      {
        id: 'nl2',
        type: 'narrative',
        content: 'A single line of narrative.',
        timestamp: 2,
      },
    ])
    const { container } = render(<NarrativeStream />)
    const paragraphs = container.querySelectorAll('p')
    expect(paragraphs).toHaveLength(1)
    expect(paragraphs[0]).toHaveTextContent('A single line of narrative.')
  })
})

/* ------------------------------------------------------------------ */
/*  Auto-scroll behavior                                               */
/* ------------------------------------------------------------------ */

describe('NarrativeStream — auto-scroll', () => {
  function setupScrollableContainer(entries: NarrativeEntry[]) {
    addEntries(entries)
    const { container } = render(<NarrativeStream />)
    const scrollArea = container.querySelector(
      '[class*="scrollArea"]',
    ) as HTMLElement
    return { container, scrollArea }
  }

  function mockScrollDimensions(el: HTMLElement, height: number, clientHeight: number) {
    Object.defineProperty(el, 'scrollHeight', {
      get: () => height,
      configurable: true,
    })
    Object.defineProperty(el, 'clientHeight', {
      get: () => clientHeight,
      configurable: true,
    })
  }

  it('auto-scrolls to bottom when new entries are added', () => {
    const { scrollArea } = setupScrollableContainer([
      { id: 'a1', type: 'narrative', content: 'First', timestamp: 1 },
    ])
    expect(scrollArea).toBeTruthy()

    // Give scrollable dimensions
    mockScrollDimensions(scrollArea, 1000, 400)
    scrollArea.scrollTop = 0

    // Add another entry — useEffect should fire and scroll to bottom
    act(() => {
      useGameStore.setState({
        narrativeEntries: [
          { id: 'a1', type: 'narrative', content: 'First', timestamp: 1 },
          { id: 'a2', type: 'narrative', content: 'Second', timestamp: 2 },
        ],
      })
    })

    expect(scrollArea.scrollTop).toBe(1000)
  })

  it('does not auto-scroll when user has scrolled up', () => {
    const { scrollArea } = setupScrollableContainer([
      { id: 'b1', type: 'narrative', content: 'First', timestamp: 1 },
    ])
    expect(scrollArea).toBeTruthy()

    mockScrollDimensions(scrollArea, 1000, 400)
    scrollArea.scrollTop = 0

    // Simulate scrolling up — this sets shouldAutoScroll.current = false
    fireEvent.scroll(scrollArea)

    // Reset scrollTop to a non-bottom position for the check
    scrollArea.scrollTop = 50

    // Add entry — effect runs but shouldAutoScroll is false
    act(() => {
      useGameStore.setState({
        narrativeEntries: [
          { id: 'b1', type: 'narrative', content: 'First', timestamp: 1 },
          { id: 'b2', type: 'narrative', content: 'Second', timestamp: 2 },
        ],
      })
    })

    // scrollTop should STILL be 50 (not auto-scrolled to 1000)
    expect(scrollArea.scrollTop).toBe(50)
  })
})

/* ------------------------------------------------------------------ */
/*  Scroll-to-bottom button                                            */
/* ------------------------------------------------------------------ */

describe('NarrativeStream — scroll-to-bottom button', () => {
  function setupScrollableContainer(entries: NarrativeEntry[]) {
    addEntries(entries)
    const { container } = render(<NarrativeStream />)
    const scrollArea = container.querySelector(
      '[class*="scrollArea"]',
    ) as HTMLElement
    return { container, scrollArea }
  }

  function mockScrollDimensions(el: HTMLElement, height: number, clientHeight: number) {
    Object.defineProperty(el, 'scrollHeight', {
      get: () => height,
      configurable: true,
    })
    Object.defineProperty(el, 'clientHeight', {
      get: () => clientHeight,
      configurable: true,
    })
  }

  it('appears when user scrolls up away from the bottom', () => {
    const { scrollArea } = setupScrollableContainer([
      { id: 'c1', type: 'narrative', content: 'Content', timestamp: 1 },
    ])
    expect(scrollArea).toBeTruthy()

    mockScrollDimensions(scrollArea, 1000, 300)
    scrollArea.scrollTop = 0

    // Fire scroll event — distance = 1000 - 0 - 300 = 700 > 100
    fireEvent.scroll(scrollArea)

    expect(
      screen.getByLabelText('Scroll to bottom'),
    ).toBeInTheDocument()
  })

  it('does not appear when already near the bottom', () => {
    const { scrollArea } = setupScrollableContainer([
      { id: 'd1', type: 'narrative', content: 'Content', timestamp: 1 },
    ])
    expect(scrollArea).toBeTruthy()

    mockScrollDimensions(scrollArea, 500, 480)
    scrollArea.scrollTop = 0

    // Fire scroll event — distance = 500 - 0 - 480 = 20 <= 100 (near bottom)
    fireEvent.scroll(scrollArea)

    expect(
      screen.queryByLabelText('Scroll to bottom'),
    ).not.toBeInTheDocument()
  })

  it('scrolls to bottom when clicked', () => {
    const { scrollArea } = setupScrollableContainer([
      { id: 'e1', type: 'narrative', content: 'Content', timestamp: 1 },
    ])
    expect(scrollArea).toBeTruthy()

    mockScrollDimensions(scrollArea, 800, 300)
    scrollArea.scrollTop = 0

    // Make button appear
    fireEvent.scroll(scrollArea)

    // Click the scroll-to-bottom button
    fireEvent.click(screen.getByLabelText('Scroll to bottom'))

    // Should now be at the bottom
    expect(scrollArea.scrollTop).toBe(800)
  })

  it('reappears after scrolling up again following a click', () => {
    const { scrollArea } = setupScrollableContainer([
      { id: 'f1', type: 'narrative', content: 'Content', timestamp: 1 },
    ])
    expect(scrollArea).toBeTruthy()

    mockScrollDimensions(scrollArea, 800, 300)
    scrollArea.scrollTop = 0

    // Make button appear
    fireEvent.scroll(scrollArea)

    // Click to go to bottom
    fireEvent.click(screen.getByLabelText('Scroll to bottom'))

    // Button should be hidden now (at bottom)
    expect(
      screen.queryByLabelText('Scroll to bottom'),
    ).not.toBeInTheDocument()

    // Scroll up again
    scrollArea.scrollTop = 0
    fireEvent.scroll(scrollArea)

    // Button should reappear
    expect(
      screen.getByLabelText('Scroll to bottom'),
    ).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Unique entry IDs                                                   */
/* ------------------------------------------------------------------ */

describe('NarrativeStream — entry identification', () => {
  it('renders entries with distinct IDs without duplicate keys', () => {
    // Add entries with unique IDs — React will use them as keys
    const entries: NarrativeEntry[] = [
      { id: 'uniq-1', type: 'narrative', content: 'Alpha', timestamp: 1 },
      { id: 'uniq-2', type: 'narrative', content: 'Beta', timestamp: 2 },
      { id: 'uniq-3', type: 'narrative', content: 'Gamma', timestamp: 3 },
    ]
    addEntries(entries)
    render(<NarrativeStream />)
    // If keys are duplicated, React would warn.  We verify all render.
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
    expect(screen.getByText('Gamma')).toBeInTheDocument()
  })

  it('adds entries via addNarrativeEntry action with unique generated IDs', () => {
    act(() => {
      useGameStore.getState().addNarrativeEntry({
        type: 'narrative',
        content: 'Auto-generated ID entry',
      })
    })
    act(() => {
      useGameStore.getState().addNarrativeEntry({
        type: 'narrative',
        content: 'Another auto-generated ID entry',
      })
    })
    render(<NarrativeStream />)
    expect(
      screen.getByText('Auto-generated ID entry'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Another auto-generated ID entry'),
    ).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Long content                                                       */
/* ------------------------------------------------------------------ */

describe('NarrativeStream — long content', () => {
  it('renders very long narrative content without breaking layout', () => {
    const longText =
      'A dark and stormy night. '.repeat(50) + 'The end.'
    addEntries([
      { id: 'long1', type: 'narrative', content: longText, timestamp: 1 },
    ])
    render(<NarrativeStream />)
    expect(screen.getByText(/A dark and stormy night/)).toBeInTheDocument()
    expect(screen.getByText(/The end\./)).toBeInTheDocument()
  })

  it('renders very long player content without breaking', () => {
    const longPlayerText =
      'I carefully inspect every inch of the ancient tome, examining each rune… '.repeat(
        30,
      )
    addEntries([
      {
        id: 'long2',
        type: 'player',
        content: longPlayerText,
        timestamp: 2,
      },
    ])
    render(<NarrativeStream />)
    expect(
      screen.getByText(/I carefully inspect/),
    ).toBeInTheDocument()
  })
})
