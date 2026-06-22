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
import { useCharacterStore } from '../../stores/characterStore'
import type { ItemType } from '../../api/types'
import type { DerivedSheet } from '../../api/types'
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

function setDerivedSheet(sheet: DerivedSheet | null): void {
  act(() => {
    useCharacterStore.setState({ derivedSheet: sheet })
  })
}

/* ------------------------------------------------------------------ */
/*  Mock data                                                          */
/* ------------------------------------------------------------------ */

interface MockItem {
  id: string
  name: string
  quantity: number
  item_type: string
  properties: Record<string, unknown>
  description: string
  weight: number
  value: number
}

interface CharacterData {
  name: string
  character_class: string
  level: number
  resources: Record<string, { value: number; max: number }>
  ac: number
  xp: number
  abilities: Record<string, number>
  inventory: MockItem[]
  equipped_items: string[]
}

const mockInventory: MockItem[] = [
  {
    id: 'sword-1',
    name: 'Iron Sword',
    quantity: 1,
    item_type: 'WEAPON',
    properties: {},
    description: 'A sturdy iron blade.',
    weight: 3,
    value: 10,
  },
  {
    id: 'torch-1',
    name: 'Torch',
    quantity: 2,
    item_type: 'TOOL',
    properties: {},
    description: 'Provides light.',
    weight: 1,
    value: 1,
  },
  {
    id: 'potion-1',
    name: 'Healing Potion',
    quantity: 1,
    item_type: 'CONSUMABLE',
    properties: {},
    description: 'Restores 2d4+2 HP.',
    weight: 0.5,
    value: 50,
  },
]

const mockCharacter: CharacterData = {
  name: 'Thorn Ironhide',
  character_class: 'Fighter',
  level: 3,
  resources: {
    hp: { value: 14, max: 28 },
  },
  ac: 16,
  xp: 900,
  abilities: { STR: 16, DEX: 13, CON: 15, INT: 10, WIS: 12, CHA: 8 },
  inventory: mockInventory,
  equipped_items: ['sword-1'],
}

const mockWorldState: Record<string, unknown> = {
  _character: { ...mockCharacter },
  gold: 47,
  current_location: 'dark_forest',
  active_npcs: {
    elf_merchant: { name: 'Elara', last_seen_turn: 5 },
    goblin_chief: { name: 'Grubnik', last_seen_turn: 12 },
  },
}

const mockDerivedSheet: DerivedSheet = {
  ability_modifiers: { STR: 3, DEX: 1, CON: 2, INT: 0, WIS: 1, CHA: -1 },
  proficiency_bonus: 2,
  ac: 17,
  initiative: 1,
  speed: 30,
  skill_modifiers: {
    Perception: 3,
    Stealth: 3,
    Investigation: 2,
    Insight: 3,
    Athletics: 5,
    Acrobatics: 3,
  },
  saving_throw_modifiers: {
    STR: 5,
    DEX: 1,
    CON: 4,
    INT: 0,
    WIS: 1,
    CHA: -1,
  },
  passive_perception: 13,
  attack_bonus: {},
  encumbrance: {},
  hit_dice: 'd10',
  resistances: [],
  vulnerabilities: [],
  formulas: { ac: '10 + DEX modifier (1) + proficiency bonus (2) + shield (4)' },
}

function makeCharacter(overrides: Partial<CharacterData>): CharacterData {
  return { ...mockCharacter, ...overrides }
}

beforeEach(() => {
  hideTokens()
  setWorldState(null)
  setDerivedSheet(null)
})

afterEach(() => {
  hideTokens()
  setWorldState(null)
  setDerivedSheet(null)
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

  it('renders HP value from resources', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('14/28')).toBeInTheDocument()
  })

  it('renders AC and XP values', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('AC')).toBeInTheDocument()
    // AC is 16 from character, STR is also 16 — use getAllByText and check count
    const sixteenElements = screen.getAllByText('16')
    expect(sixteenElements.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('XP')).toBeInTheDocument()
    expect(screen.getByText('900')).toBeInTheDocument()
  })

  it('renders AC from derivedSheet when available', () => {
    setWorldState(mockWorldState)
    setDerivedSheet(mockDerivedSheet)
    render(<GameStatusSidebar />)
    // Derived sheet has AC 17, character has AC 16 — should show 17
    expect(screen.getByText('17')).toBeInTheDocument()
  })

  it('shows AC formula in tooltip when derivedSheet is available', () => {
    setWorldState(mockWorldState)
    setDerivedSheet(mockDerivedSheet)
    render(<GameStatusSidebar />)
    const acItem = screen.getByText('AC').closest('span')
    expect(acItem).toHaveAttribute(
      'title',
      '10 + DEX modifier (1) + proficiency bonus (2) + shield (4)',
    )
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
      _character: makeCharacter({
        resources: { hp: { value: 24, max: 28 } },
      }),
    }
    setWorldState(highHp)
    render(<GameStatusSidebar />)
    const bar = screen.getByRole('progressbar')
    expect(bar.className).toContain('hpGreen')
  })

  it('shows yellow bar when HP 30-60%', () => {
    const midHp = {
      ...mockWorldState,
      _character: makeCharacter({
        resources: { hp: { value: 12, max: 28 } },
      }),
    }
    setWorldState(midHp)
    render(<GameStatusSidebar />)
    const bar = screen.getByRole('progressbar')
    expect(bar.className).toContain('hpYellow')
  })

  it('shows red bar when HP < 30%', () => {
    const lowHp = {
      ...mockWorldState,
      _character: makeCharacter({
        resources: { hp: { value: 5, max: 28 } },
      }),
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

  it('shows ability modifiers from derivedSheet', () => {
    setWorldState(mockWorldState)
    setDerivedSheet(mockDerivedSheet)
    render(<GameStatusSidebar />)
    // STR: 16 score, +3 modifier (+3 also appears for skills, so use getAllByText)
    expect(screen.getAllByText('+3').length).toBeGreaterThanOrEqual(1)
    // DEX: 13 score, +1 modifier
    expect(screen.getAllByText('+1').length).toBeGreaterThanOrEqual(1)
    // CON: 15 score, +2 modifier (+2 also appears for Investigation skill)
    expect(screen.getAllByText('+2').length).toBeGreaterThanOrEqual(1)
    // CHA: 8 score, -1 modifier (also appears as CHA save)
    expect(screen.getAllByText('-1').length).toBeGreaterThanOrEqual(1)
  })
})

/* ------------------------------------------------------------------ */
/*  Saving throws                                                      */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — saving throws', () => {
  it('renders saving throw modifiers from derivedSheet', () => {
    setWorldState(mockWorldState)
    setDerivedSheet(mockDerivedSheet)
    render(<GameStatusSidebar />)
    expect(screen.getByText('Saving Throws')).toBeInTheDocument()
    // CON save: +4 (unique to saves, ability 2 + prof 2)
    expect(screen.getByText('+4')).toBeInTheDocument()
    // INT save: +0
    expect(screen.getAllByText('+0').length).toBeGreaterThanOrEqual(1)
    // CHA save: -1 (also appears in ability modifiers, but still present)
    expect(screen.getAllByText('-1').length).toBeGreaterThanOrEqual(1)
  })

  it('shows proficiency indicator for proficient saves', () => {
    setWorldState(mockWorldState)
    setDerivedSheet(mockDerivedSheet)
    render(<GameStatusSidebar />)
    // STR save: mod 5 = ability 3 + prof 2 → proficient
    const proficientDots = document.querySelectorAll('[title="Proficient"]')
    expect(proficientDots.length).toBeGreaterThanOrEqual(1)
  })
})

/* ------------------------------------------------------------------ */
/*  Skills                                                             */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — skills', () => {
  it('renders skill modifiers from derivedSheet for key skills', () => {
    setWorldState(mockWorldState)
    setDerivedSheet(mockDerivedSheet)
    render(<GameStatusSidebar />)
    expect(screen.getByText('Skills')).toBeInTheDocument()
    expect(screen.getByText('Perception')).toBeInTheDocument()
    expect(screen.getByText('Stealth')).toBeInTheDocument()
    expect(screen.getByText('Athletics')).toBeInTheDocument()
    // Investigation is +2 (also appears as CON ability modifier)
    expect(screen.getAllByText('+2').length).toBeGreaterThanOrEqual(1)
  })

  it('does not render skills section when derivedSheet has no skill_modifiers', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.queryByText('Skills')).not.toBeInTheDocument()
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

  it('renders inventory items with type icons', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(screen.getByText('Iron Sword')).toBeInTheDocument()
    expect(screen.getByText('Torch')).toBeInTheDocument()
    expect(screen.getByText('Healing Potion')).toBeInTheDocument()
  })

  it('shows equipped indicator for equipped items', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    // Iron Sword is equipped (id: sword-1)
    const swordEntry = screen.getByText('Iron Sword')
      .closest('li')
    expect(swordEntry?.textContent).toContain('[E]')
  })

  it('shows quantity for items with quantity > 1', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    // Torch has quantity 2
    const torchEntry = screen.getByText('Torch')
      .closest('li')
    expect(torchEntry?.textContent).toContain('x2')
  })

  it('shows "Nothing" for empty inventory', () => {
    const noInv = {
      ...mockWorldState,
      _character: makeCharacter({ inventory: [], equipped_items: [] }),
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

  it('shows HP and AC in collapsed state', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    fireEvent.click(screen.getByLabelText('Collapse sidebar'))
    // HP display in collapsed state
    expect(screen.getByText('❤️14/28')).toBeInTheDocument()
    // AC display in collapsed state
    expect(screen.getByText('🛡️16')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Character Sheet button                                             */
/* ------------------------------------------------------------------ */

describe('GameStatusSidebar — Character Sheet button', () => {
  it('renders the Character Sheet button', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    expect(
      screen.getByRole('button', { name: /open character sheet/i }),
    ).toBeInTheDocument()
  })

  it('opens CharacterDetailsModal when clicked', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    const btn = screen.getByLabelText('Open character sheet')
    fireEvent.click(btn)
    // Modal should be visible with the title
    expect(
      screen.getByText('Character Details'),
    ).toBeInTheDocument()
  })

  it('closes CharacterDetailsModal when close is triggered', () => {
    setWorldState(mockWorldState)
    render(<GameStatusSidebar />)
    // Open modal
    fireEvent.click(screen.getByLabelText('Open character sheet'))
    expect(
      screen.getByText('Character Details'),
    ).toBeInTheDocument()
    // Close by clicking overlay
    const overlay = screen.getByRole('dialog')
    fireEvent.click(overlay)
    expect(
      screen.queryByText('Character Details'),
    ).not.toBeInTheDocument()
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
        resources: { hp: { value: 8, max: 8 } },
        ac: 10,
        abilities: { STR: 8 },
        inventory: [],
        equipped_items: [],
      },
    }
    setWorldState(minimalWorld)
    render(<GameStatusSidebar />)
    expect(screen.getByText('No world data yet.')).toBeInTheDocument()
  })
})
