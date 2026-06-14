/**
 * NpcThinkingIndicator tests — goblin-skeptic scrutiny of NPC thinking display.
 *
 * Covers: NPC name and hint rendering, null state, default state, dynamic
 * updates between different NPCs, and hint-less fallback formatting.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { useGameStore } from '../../stores/gameStore'
import NpcThinkingIndicator from './NpcThinkingIndicator'

function resetStore(): void {
  useGameStore.setState({
    npcThinking: null,
  })
}

beforeEach(() => {
  resetStore()
})

/* ------------------------------------------------------------------ */
/*  Visible with NPC data                                              */
/* ------------------------------------------------------------------ */

describe('NpcThinkingIndicator — visible state', () => {
  it('shows NPC name and hint when npcThinking is set', () => {
    useGameStore.setState({
      npcThinking: { npcId: 'dragon', hint: 'plotting' },
    })
    render(<NpcThinkingIndicator />)
    expect(screen.getByText(/dragon/)).toBeInTheDocument()
    expect(screen.getByText(/plotting/)).toBeInTheDocument()
  })

  it('shows NPC name without hint when hint is empty', () => {
    useGameStore.setState({
      npcThinking: { npcId: 'goblin', hint: '' },
    })
    render(<NpcThinkingIndicator />)
    expect(screen.getByText(/goblin/)).toBeInTheDocument()
    // Should use fallback: "goblin is pondering…"
    expect(
      screen.getByText(/goblin is pondering/),
    ).toBeInTheDocument()
  })

  it('has role="status" and aria-live="polite"', () => {
    useGameStore.setState({
      npcThinking: { npcId: 'lich', hint: 'scheming' },
    })
    render(<NpcThinkingIndicator />)
    const el = screen.getByRole('status')
    expect(el).toHaveAttribute('aria-live', 'polite')
  })
})

/* ------------------------------------------------------------------ */
/*  Hidden state                                                       */
/* ------------------------------------------------------------------ */

describe('NpcThinkingIndicator — hidden state', () => {
  it('renders nothing when npcThinking is null', () => {
    useGameStore.setState({ npcThinking: null })
    const { container } = render(<NpcThinkingIndicator />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing by default (npcThinking starts null)', () => {
    const { container } = render(<NpcThinkingIndicator />)
    expect(container).toBeEmptyDOMElement()
  })
})

/* ------------------------------------------------------------------ */
/*  Dynamic updates                                                    */
/* ------------------------------------------------------------------ */

describe('NpcThinkingIndicator — dynamic updates', () => {
  it('updates displayed NPC info when npcThinking changes', () => {
    useGameStore.setState({
      npcThinking: { npcId: 'elf', hint: 'negotiating' },
    })
    const { rerender } = render(<NpcThinkingIndicator />)
    expect(screen.getByText(/elf/)).toBeInTheDocument()
    expect(screen.getByText(/negotiating/)).toBeInTheDocument()

    // Switch to a different NPC
    act(() => {
      useGameStore.setState({
        npcThinking: { npcId: 'dwarf', hint: 'mining' },
      })
    })
    rerender(<NpcThinkingIndicator />)

    // Old NPC should be gone, new one should appear
    expect(screen.queryByText(/elf/)).not.toBeInTheDocument()
    expect(screen.getByText(/dwarf/)).toBeInTheDocument()
    expect(screen.getByText(/mining/)).toBeInTheDocument()
  })

  it('disappears when npcThinking becomes null after being set', () => {
    useGameStore.setState({
      npcThinking: { npcId: 'orc', hint: 'attacking' },
    })
    const { rerender } = render(<NpcThinkingIndicator />)
    expect(screen.getByText(/orc/)).toBeInTheDocument()

    // Clear npcThinking
    act(() => {
      useGameStore.setState({ npcThinking: null })
    })
    rerender(<NpcThinkingIndicator />)

    expect(screen.queryByText(/orc/)).not.toBeInTheDocument()
  })

  it('displays correct text format with hint: "npcId is pondering (hint)…"', () => {
    useGameStore.setState({
      npcThinking: { npcId: 'wizard', hint: 'casting' },
    })
    render(<NpcThinkingIndicator />)
    expect(
      screen.getByText('wizard is pondering (casting)…'),
    ).toBeInTheDocument()
  })
})
