/**
 * GameStatusSidebar tests — goblin-checks on the collapsible stats panel.
 *
 * Covers: empty state, character info, HP bar coloring, abilities grid,
 * inventory/NPC display, collapse toggle, token usage visibility, and
 * location formatting.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useGameStore } from '../../stores/gameStore'
import GameStatusSidebar from './GameStatusSidebar'

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function setWorldState(state: Record<string, unknown> | null): void {
  act(() => {
    useGameStore.setState({ worldState: state })
  })
}

function setTokenUsage(
  totalTotal: number,
  latestTotal: number,
): void {
  act(() => {
    useGameStore.setState({
      tokenUsage: {
        total: { prompt_tokens: 0, completion_tokens: 0, total_tokens: totalTotal },
        latest: { prompt_tokens: 0, completion_tokens: 0, total_tokens: latestTotal },
      },
      showTokens: true,
    })
  })
}

function hideTokens(): void {
  act(() => {
    useGameStore.setState({ showTokens: false })
  })
}

interface CharacterData {
  name: string
  character_class: string
  level: number
  hp: number
  max_hp: number
  ac: number
  xp: number
  abilities: Record<string, number>
}

const mockCharacter: CharacterData = {
  name: 'Thorn Ironhide',
  character_class: 'Fighter',
  level: 3,
  hp: 14,
  max_hp: 28,
  ac: 16,
  xp: 900,
  abilities: { STR: 16, DEX: 13, CON: 15, INT: 10, WIS: 12, CHA: 8 },
}

const mockWorldState: Record<string, unknown> = {
  _character: { ...mockCharacter },
  gold: 47,
  current_location: 'dark_forest',
  inventory: ['Iron Sword', 'Torch', 'Healing Potion'],
  active_npcs: {
    elf_merchant: { name: 'Elara', last_seen_turn: 5 },
    goblin_chief: { name: 'Grubnik', last_seen_turn: 12 },
  },
}

function makeCharacter(overrides: Partial<CharacterData>): CharacterData {
  return { ...mockCharacter, ...overrides }
}

beforeEach(() => {
  hideTokens()
  setWorldState(null)
})

afterEach(() => {
  hideTokens()
  setWorldState(null)
})

/* ------------------------------------------------------------------ */
/*  Empty state                                                        */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — empty state', () => {
  it('renders empty message when worldState is null', () => {
    render(<GameStatusSidebar />)
    expect(
      screen.getByText('Start your adventure to see character stats'),
    ).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Character info                                                     */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — character info', () => {
  it('renders character name, class, and level', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('Thorn Ironhide')).toBeInTheDocument()
    expect(screen.getByText('Fighter (Level 3)')).toBeInTheDocument()
  })

  it('renders HP value', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('14/28')).toBeInTheDocument()
  })

  it('renders AC and XP values', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('AC')).toBeInTheDocument()
    // AC is 16, STR is also 16 — use getAllByText and check count
    const sixteenElements = screen.getAllByText('16')
    expect(sixteenElements.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('XP')).toBeInTheDocument()
    expect(screen.getByText('900')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  HP bar                                                             */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — HP bar', () => {
  it('renders progressbar with correct ARIA attributes', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toBeInTheDocument()
    expect(bar).toHaveAttribute('aria-valuenow', '14')
    expect(bar).toHaveAttribute('aria-valuemax', '28')
    expect(bar).toHaveAttribute('aria-valuemin', '0')
  })

  it('shows green bar when HP > 60%', () => {
    const highHp = {
      ...mockWorldState,
      _character: makeCharacter({ hp: 24, max_hp: 28 }),
    }
    setWorldState(highHp)
    render(<GameStatusSidebar />)
    const bar = screen.getByRole('progressbar')
    expect(bar.className).toContain('hpGreen')
  })

  it('shows yellow bar when HP 30-60%', () => {
    const midHp = {
      ...mockWorldState,
      _character: makeCharacter({ hp: 12, max_hp: 28 }),
    }
    setWorldState(midHp)
    render(<GameStatusSidebar />)
    const bar = screen.getByRole('progressbar')
    expect(bar.className).toContain('hpYellow')
  })

  it('shows red bar when HP < 30%', () => {
    const lowHp = {
      ...mockWorldState,
      _character: makeCharacter({ hp: 5, max_hp: 28 }),
    }
    setWorldState(lowHp)
    render(<GameStatusSidebar />)
    const bar = screen.getByRole('progressbar')
    expect(bar.className).toContain('hpRed')
  })
})

/* ------------------------------------------------------------------ */
/*  Abilities grid                                                     */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — abilities', () => {
  it('renders all 6 ability scores', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('STR')).toBeInTheDocument()
    expect(screen.getByText('DEX')).toBeInTheDocument()
    expect(screen.getByText('CON')).toBeInTheDocument()
    expect(screen.getByText('INT')).toBeInTheDocument()
    expect(screen.getByText('WIS')).toBeInTheDocument()
    expect(screen.getByText('CHA')).toBeInTheDocument()
    // STR=16 is duplicated by AC=16, so getAllByText
    expect(screen.getAllByText('16').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('13')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
  })

  it('handles lowercase ability keys', () => {
    const lowerAbilities = {
      ...mockWorldState,
      _character: makeCharacter({
        abilities: {
          str: 14,
          dex: 12,
          con: 13,
          int: 9,
          wis: 11,
          cha: 7,
        },
      }),
    }
    setWorldState(lowerAbilities)
    render(<GameStatusSidebar />)
    expect(screen.getByText('14')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  World state: gold, location, inventory, NPCs                       */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — world state sections', () => {
  it('shows gold amount', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('47 gold')).toBeInTheDocument()
  })

  it('formats location from snake_case to Title Case', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('Dark Forest')).toBeInTheDocument()
  })

  it('renders inventory items', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('Iron Sword')).toBeInTheDocument()
    expect(screen.getByText('Torch')).toBeInTheDocument()
    expect(screen.getByText('Healing Potion')).toBeInTheDocument()
  })

  it('shows "Nothing" for empty inventory', () => {
    const noInv = {
      ...mockWorldState,
      inventory: [],
    }
    setWorldState(noInv)
    render(<GameStatusSidebar />)
    expect(screen.getByText('Nothing')).toBeInTheDocument()
  })

  it('renders NPCs with last-seen turn info', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('Elara')).toBeInTheDocument()
    expect(screen.getByText('Grubnik')).toBeInTheDocument()
    expect(screen.getByText('Last seen: turn 5')).toBeInTheDocument()
    expect(screen.getByText('Last seen: turn 12')).toBeInTheDocument()
  })

  it('shows empty NPC message when no NPCs', () => {
    const noNpcs = {
      ...mockWorldState,
      active_npcs: {},
    }
    setWorldState(noNpcs)
    render(<GameStatusSidebar />)
    expect(
      screen.getByText('No NPCs encountered yet.'),
    ).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Collapse / Expand                                                  */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — collapse toggle', () => {
  it('collapses when toggle button is clicked', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    const collapseBtn = screen.getByLabelText('Collapse sidebar')
    fireEvent.click(collapseBtn)
    // After collapse, the expand button should appear
    expect(screen.getByLabelText('Expand sidebar')).toBeInTheDocument()
  })

  it('expands when toggle button is clicked in collapsed state', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    // Collapse first
    fireEvent.click(screen.getByLabelText('Collapse sidebar'))
    // Then expand
    fireEvent.click(screen.getByLabelText('Expand sidebar'))
    // Collapse button should be back
    expect(screen.getByLabelText('Collapse sidebar')).toBeInTheDocument()
  })

  it('shows character initial when collapsed', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    fireEvent.click(screen.getByLabelText('Collapse sidebar'))
    expect(screen.getByText('T')).toBeInTheDocument()
  })

  it('shows abbreviated class when collapsed', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    fireEvent.click(screen.getByLabelText('Collapse sidebar'))
    expect(screen.getByText('Fighter')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Token usage                                                        */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — token usage', () => {
  it('shows token total and latest when showTokens is true', () => {
    setWorldState(mockWorldState)
    setTokenUsage(1500, 234)
    render(<GameStatusSidebar />)
    expect(screen.getByText('1,500')).toBeInTheDocument()
    expect(screen.getByText('+234 this turn')).toBeInTheDocument()
  })

  it('does not show token section when showTokens is false', () => {
    setWorldState(mockWorldState)
    hideTokens()
    render(<GameStatusSidebar />)
    // The token section renders ⚡ which has aria-hidden, so check
    // that the total token number is not present
    expect(screen.queryByText('+234 this turn')).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Gold = null / location = null                                      */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — null world fields', () => {
  it('shows fallback text when gold and location are null', () => {
    const minimalWorld: Record<string, unknown> = {
      _character: {
        name: 'Test',
        character_class: 'Wizard',
        level: 1,
        hp: 8,
        max_hp: 8,
        ac: 10,
        abilities: { STR: 8 },
      },
    }
    setWorldState(minimalWorld)
    render(<GameStatusSidebar />)
    expect(screen.getByText('No world data yet.')).toBeInTheDocument()
  })
})
