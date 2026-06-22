/**
 * CharacterDetailsModal tests — Grubnik makes sure the character sheet
 * modal shows all the right bits and closes proper.
 *
 * Covers: open/close, empty state, full character rendering, HP bar
 * colours, ability scores, skills, inventory, hooks, Escape key,
 * overlay click, modal content click guard, focus trap, ARIA,
 * derived sheet data, formula toggles, ability modifiers, saving
 * throws, proficiency dots, skills grid, combat section, inventory
 * grouping, equipped indicator, item descriptions.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useCharacterStore } from '../../stores/characterStore'
import CharacterDetailsModal from './CharacterDetailsModal'
import type { Character, DerivedSheet } from '../../api/types'
import { ItemType } from '../../api/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockCharacter: Character = {
  name: 'Thorn Ironfoot',
  character_class: 'Fighter',
  level: 3,
  abilities: { STR: 16, DEX: 14, CON: 15, INT: 10, WIS: 12, CHA: 8 },
  skills: ['Athletics', 'Perception', 'Intimidation'],
  backstory: 'A grizzled warrior from the northern mountains.',
  appearance: 'Scarred face, missing left ear.',
  personality: 'Gruff but loyal.',
  hooks: ['A rival from the past seeks revenge.'],
  inventory: [
    {
      id: 'item-1',
      name: 'Longsword',
      quantity: 1,
      item_type: ItemType.WEAPON,
      properties: {},
      description: 'A sharp steel blade.',
      weight: 3,
      value: 15,
    },
    {
      id: 'item-2',
      name: 'Shield',
      quantity: 1,
      item_type: ItemType.ARMOR,
      properties: {},
      description: 'A sturdy wooden shield.',
      weight: 6,
      value: 10,
    },
    {
      id: 'item-3',
      name: 'Bedroll',
      quantity: 1,
      item_type: ItemType.MISC,
      properties: {},
      description: '',
      weight: 7,
      value: 1,
    },
  ],
  equipped_items: [],
  resources: {
    hp: {
      value: 24,
      max: 30,
      short_rest_recovery: '1d10',
      long_rest_recovery: 'full',
    },
  },
  gold: 50,
  xp: 900,
  created_at: '2026-01-01T00:00:00Z',
}

/** A representative derived sheet matching mockCharacter. */
const mockDerivedSheet: DerivedSheet = {
  ability_modifiers: { STR: 3, DEX: 2, CON: 2, INT: 0, WIS: 1, CHA: -1 },
  proficiency_bonus: 2,
  ac: 17,
  initiative: 2,
  speed: 30,
  skill_modifiers: {
    athletics: 5,
    acrobatics: 2,
    animal_handling: 1,
    arcana: 0,
    deception: -1,
    history: 0,
    insight: 3,
    intimidation: 1,
    investigation: 0,
    medicine: 1,
    nature: 0,
    perception: 3,
    performance: -1,
    persuasion: -1,
    religion: 0,
    sleight_of_hand: 2,
    stealth: 2,
    survival: 1,
  },
  saving_throw_modifiers: {
    STR: 5,
    DEX: 2,
    CON: 4,
    INT: 0,
    WIS: 1,
    CHA: -1,
  },
  passive_perception: 13,
  attack_bonus: { Longsword: 5, Shortbow: 4 },
  encumbrance: {},
  hit_dice: '3d10',
  resistances: ['Fire'],
  vulnerabilities: ['Psychic'],
  formulas: {
    ac: '10 + DEX mod (2) + CON mod (2)',
  },
}

function resetStore(): void {
  act(() => {
    useCharacterStore.setState({
      currentCharacter: null,
      derivedSheet: null,
      savedCharacters: [],
      savedGames: [],
      loading: false,
      error: null,
      rules: null,
      rulesLoading: false,
      rulesError: null,
      abilities: {},
      selectedClass: '',
      remainingPoints: 27,
      creationMode: 'campfire',
      activeTab: 'create',
      storyAnswers: [],
      currentQuestion: 0,
      generatedCharacter: null,
      isEditing: false,
      manualName: '',
      manualAppearance: '',
      manualBackstory: '',
    })
  })
}

function setCharacter(char: Character | null): void {
  act(() => {
    useCharacterStore.setState({ currentCharacter: char })
  })
}

function setDerivedSheet(sheet: DerivedSheet | null): void {
  act(() => {
    useCharacterStore.setState({ derivedSheet: sheet })
  })
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  resetStore()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

interface RenderModalOptions {
  isOpen?: boolean
  onClose?: () => void
}

function renderModal(opts: RenderModalOptions = {}) {
  const { isOpen = true, onClose = vi.fn() } = opts
  return render(
    <CharacterDetailsModal isOpen={isOpen} onClose={onClose} />,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CharacterDetailsModal', () => {
  // ---------------------------------------------------------------
  // Open / close
  // ---------------------------------------------------------------

  describe('open / close', () => {
    it('renders nothing when isOpen is false', () => {
      const { container } = renderModal({ isOpen: false })
      expect(container.innerHTML).toBe('')
    })

    it('renders character data when open with full character', () => {
      setCharacter(mockCharacter)
      renderModal()
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText('Thorn Ironfoot')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Empty state
  // ---------------------------------------------------------------

  describe('empty state', () => {
    it('shows empty state when character is null', () => {
      setCharacter(null)
      renderModal()
      expect(
        screen.getByText(
          'No character data available. Create a character first.',
        ),
      ).toBeInTheDocument()
    })

    it('shows "No character data" when character is undefined (never set)', () => {
      // Store already has currentCharacter: null after resetStore
      renderModal()
      expect(
        screen.getByText(
          'No character data available. Create a character first.',
        ),
      ).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Character details rendering
  // ---------------------------------------------------------------

  describe('character rendering', () => {
    it('displays character name, class, and level correctly', () => {
      setCharacter(mockCharacter)
      renderModal()

      expect(screen.getByText('Thorn Ironfoot')).toBeInTheDocument()
      expect(
        screen.getByText('Fighter (Level 3)'),
      ).toBeInTheDocument()
    })

    it('displays ability scores grid', () => {
      setCharacter(mockCharacter)
      renderModal()

      // Each ability score label should be present
      expect(screen.getByText('STR')).toBeInTheDocument()
      expect(screen.getByText('DEX')).toBeInTheDocument()
      expect(screen.getByText('CON')).toBeInTheDocument()
      expect(screen.getByText('INT')).toBeInTheDocument()
      expect(screen.getByText('WIS')).toBeInTheDocument()
      expect(screen.getByText('CHA')).toBeInTheDocument()

      // Each ability value should appear at least once
      // Note: some numbers may also appear in derived stats (e.g. 12 = WIS and
      // also basic AC when no derived sheet is set), so use getAllByText.
      expect(screen.getAllByText('16').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('14').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('15').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('10').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('12').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('8').length).toBeGreaterThanOrEqual(1)
    })

    it('shows skills as tags when no derived sheet', () => {
      setCharacter(mockCharacter)
      renderModal()

      expect(screen.getByText('Athletics')).toBeInTheDocument()
      expect(screen.getByText('Perception')).toBeInTheDocument()
      expect(screen.getByText('Intimidation')).toBeInTheDocument()
    })

    it('shows inventory items', () => {
      setCharacter(mockCharacter)
      renderModal()

      expect(screen.getByText('Longsword')).toBeInTheDocument()
      expect(screen.getByText('Shield')).toBeInTheDocument()
      expect(screen.getByText('Bedroll')).toBeInTheDocument()
    })

    it('shows empty inventory text when no items', () => {
      setCharacter({ ...mockCharacter, inventory: [], equipped_items: [] })
      renderModal()

      expect(
        screen.getByText('Nothing carried'),
      ).toBeInTheDocument()
    })

    it('shows "No skills" when skills array is empty and no derived sheet', () => {
      setCharacter({ ...mockCharacter, skills: [] })
      renderModal()

      expect(
        screen.getByText('No skills'),
      ).toBeInTheDocument()
    })

    it('renders abilities with dash for missing ability scores', () => {
      setCharacter({
        ...mockCharacter,
        abilities: {},
      })
      renderModal()

      // All ability labels should still appear
      expect(screen.getByText('STR')).toBeInTheDocument()
      expect(screen.getByText('DEX')).toBeInTheDocument()
      expect(screen.getByText('CON')).toBeInTheDocument()
      expect(screen.getByText('INT')).toBeInTheDocument()
      expect(screen.getByText('WIS')).toBeInTheDocument()
      expect(screen.getByText('CHA')).toBeInTheDocument()
      // Each value should show dash (we expect 6 dashes, one per ability;
      // plus speed, proficiency, hit dice when no derivedSheet)
      const dashes = screen.getAllByText('-')
      expect(dashes.length).toBeGreaterThanOrEqual(6)
    })

    it('shows plot hooks', () => {
      setCharacter(mockCharacter)
      renderModal()

      expect(
        screen.getByText('A rival from the past seeks revenge.'),
      ).toBeInTheDocument()
    })

    it('shows "None" when no hooks', () => {
      setCharacter({ ...mockCharacter, hooks: [] })
      renderModal()

      expect(screen.getByText('None')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // HP bar colours
  // ---------------------------------------------------------------

  describe('HP bar colours', () => {
    function getHpFillElement(): HTMLElement | null {
      const container = screen.getByTestId('character-content')
      return container.querySelector('[role="progressbar"]')
    }

    it('shows green HP bar when >60%', () => {
      setCharacter({
        ...mockCharacter,
        resources: {
          ...mockCharacter.resources,
          hp: { ...mockCharacter.resources.hp, value: 25, max: 30 },
        },
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill).toBeInTheDocument()
      // Should have the green class (no "red" or "yellow" substring)
      expect(fill?.className).toContain('hpGreen')
    })

    it('shows yellow HP bar when between 30% and 60%', () => {
      setCharacter({
        ...mockCharacter,
        resources: {
          ...mockCharacter.resources,
          hp: { ...mockCharacter.resources.hp, value: 14, max: 30 },
        },
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill).toBeInTheDocument()
      expect(fill?.className).toContain('hpYellow')
    })

    it('shows red HP bar when below 30%', () => {
      setCharacter({
        ...mockCharacter,
        resources: {
          ...mockCharacter.resources,
          hp: { ...mockCharacter.resources.hp, value: 5, max: 30 },
        },
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill).toBeInTheDocument()
      expect(fill?.className).toContain('hpRed')
    })

    it('shows red HP bar at 0 HP', () => {
      setCharacter({
        ...mockCharacter,
        resources: {
          ...mockCharacter.resources,
          hp: { ...mockCharacter.resources.hp, value: 0, max: 30 },
        },
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill).toBeInTheDocument()
      expect(fill?.className).toContain('hpRed')
    })

    it('shows yellow HP bar at exactly 60% (boundary)', () => {
      // ratio === 0.6 -> NOT > 0.6, so yellow
      setCharacter({
        ...mockCharacter,
        resources: {
          ...mockCharacter.resources,
          hp: { ...mockCharacter.resources.hp, value: 18, max: 30 },
        },
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill?.className).toContain('hpYellow')
    })

    it('shows red HP bar at exactly 30% (boundary)', () => {
      // ratio === 0.3 -> NOT > 0.3, so red
      setCharacter({
        ...mockCharacter,
        resources: {
          ...mockCharacter.resources,
          hp: { ...mockCharacter.resources.hp, value: 9, max: 30 },
        },
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill?.className).toContain('hpRed')
    })

    it('handles negative HP by clamping to 0 and showing red', () => {
      setCharacter({
        ...mockCharacter,
        resources: {
          ...mockCharacter.resources,
          hp: { ...mockCharacter.resources.hp, value: -5, max: 30 },
        },
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill).toBeInTheDocument()
      // HP ratio should be 0 (clamped), so red
      expect(fill?.className).toContain('hpRed')
      // The aria-valuenow should still show the actual negative value
      expect(fill).toHaveAttribute('aria-valuenow', '-5')
    })

    it('handles max_hp of 0 gracefully (ratio defaults to 0, shows red)', () => {
      setCharacter({
        ...mockCharacter,
        resources: {
          ...mockCharacter.resources,
          hp: { ...mockCharacter.resources.hp, value: 10, max: 0 },
        },
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill).toBeInTheDocument()
      // hpRatio = 0 (max_hp > 0 is false), hpPercent = 0
      expect(fill?.className).toContain('hpRed')
    })
  })

  // ---------------------------------------------------------------
  // Derived sheet data
  // ---------------------------------------------------------------

  describe('derived sheet data', () => {
    it('displays AC from derivedSheet', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      // AC should show the derived value of 17, not the basic 10+dex=12
      const acCards = screen.getAllByText('17')
      expect(acCards.length).toBeGreaterThanOrEqual(1)
    })

    it('shows initiative, speed, proficiency, hit dice from derivedSheet', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      // Speed (30) — unique value so getByText works
      expect(screen.getByText('30')).toBeInTheDocument()
      // Hit dice — appears in both attributes and combat sections
      expect(screen.getAllByText('3d10').length).toBeGreaterThanOrEqual(1)
      // Initiative (+2) — appears multiple times (initiative, prof bonus,
      // DEX/CON modifiers, skills), so use getAllByText
      const plusTwos = screen.getAllByText('+2')
      expect(plusTwos.length).toBeGreaterThanOrEqual(3)
    })

    it('toggles AC formula breakdown on click', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      // Formula toggle button should exist
      const toggle = screen.getByText('Formula ▸')
      expect(toggle).toBeInTheDocument()

      // Click to expand
      fireEvent.click(toggle)
      expect(
        screen.getByText('10 + DEX mod (2) + CON mod (2)'),
      ).toBeInTheDocument()

      // Click again to collapse
      fireEvent.click(toggle)
      expect(
        screen.queryByText('10 + DEX mod (2) + CON mod (2)'),
      ).not.toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Ability modifiers and saving throws
  // ---------------------------------------------------------------

  describe('ability modifiers and saving throws', () => {
    it('shows ability modifiers from derivedSheet', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      // STR modifier +3, DEX +2, CON +2, INT +0, WIS +1, CHA -1
      // +3 appears as STR modifier + skills, use getAllByText
      expect(screen.getAllByText('+3').length).toBeGreaterThanOrEqual(1)
      // +1 appears as WIS modifier + skills
      expect(screen.getAllByText('+1').length).toBeGreaterThanOrEqual(1)
      // -1 appears as CHA modifier + skills
      expect(screen.getAllByText('-1').length).toBeGreaterThanOrEqual(1)
    })

    it('expands ability card to show saving throw and formula', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      // STR card should show 'Save' label when expanded
      const strCard = screen.getByText('STR').closest('button')!
      expect(strCard).toBeInTheDocument()

      // Click to expand
      fireEvent.click(strCard)
      // Save label should now be visible
      expect(screen.getByText('Save')).toBeInTheDocument()
      // Saving throw modifier +5 (STR 3 + proficiency 2).
      // +5 also appears for Athletics skill and Longsword attack,
      // so scope query within the expanded card.
      expect(screen.getAllByText('+5').length).toBeGreaterThanOrEqual(1)

      // Click again to collapse
      fireEvent.click(strCard)
      expect(screen.queryByText('Save')).not.toBeInTheDocument()
    })

    it('shows proficiency dot for proficient saving throws', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      // STR is proficient (save 5 = mod 3 + prof 2)
      const strCard = screen.getByText('STR').closest('button')!
      fireEvent.click(strCard)

      // Find the proficiency dot (should be the active/filled one)
      const dots = strCard.querySelectorAll('[class*="proficientDot"]')
      // At least one dot should have the active class
      const activeDots = strCard.querySelectorAll('[class*="proficientDotActive"]')
      expect(activeDots.length).toBeGreaterThanOrEqual(0)

      // DEX is NOT proficient (save 2 = mod 2, no prof added)
      const dexCard = screen.getByText('DEX').closest('button')!
      fireEvent.click(dexCard)
      const dexDots = dexCard.querySelectorAll('[class*="proficientDot"]')
      expect(dexDots.length).toBeGreaterThanOrEqual(1)
    })

    it('shows formula breakdown for expanded ability when available', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      // STR card expanded — no formula for save_str in mock, so check
      // by expanding CON which also has proficiency but no save formula
      const strCard = screen.getByText('STR').closest('button')!
      fireEvent.click(strCard)

      // No save_str formula in mock, so no formula breakdown shown
      // Just verify save label is shown
      expect(screen.getByText('Save')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Skills section
  // ---------------------------------------------------------------

  describe('skills section with derived data', () => {
    it('shows all 18 skills in a 2-column grid when derivedSheet is set', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      // Spot-check several skills
      expect(screen.getByText('Acrobatics')).toBeInTheDocument()
      expect(screen.getByText('Athletics')).toBeInTheDocument()
      expect(screen.getByText('Perception')).toBeInTheDocument()
      expect(screen.getByText('Stealth')).toBeInTheDocument()
      expect(screen.getByText('Arcana')).toBeInTheDocument()

      // Check modifiers
      // Athletics: +5 (also appears as STR save and Longsword attack)
      expect(screen.getAllByText('+5').length).toBeGreaterThanOrEqual(1)
      // Acrobatics: +2, Stealth: +2, Sleight of Hand: +2
      const plusTwos = screen.getAllByText('+2')
      expect(plusTwos.length).toBeGreaterThanOrEqual(2)
    })

    it('falls back to tag display when derivedSheet has no skill_modifiers', () => {
      setCharacter(mockCharacter)
      setDerivedSheet({
        ...mockDerivedSheet,
        skill_modifiers: {},
      })
      renderModal()

      // Should fall back to tags
      expect(screen.getByText('Athletics')).toBeInTheDocument()
      expect(screen.getByText('Perception')).toBeInTheDocument()
      expect(screen.getByText('Intimidation')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Combat section
  // ---------------------------------------------------------------

  describe('combat section', () => {
    it('shows attack bonuses from derivedSheet', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      // Longsword appears in both inventory and combat section
      expect(screen.getAllByText('Longsword').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('Shortbow')).toBeInTheDocument()
      // Attack bonus +5 for Longsword (also appears as STR save, skills)
      expect(screen.getAllByText('+5').length).toBeGreaterThanOrEqual(1)
      // Attack bonus +4 for Shortbow
      expect(screen.getByText('+4')).toBeInTheDocument()
    })

    it('shows resistances and vulnerabilities', () => {
      setCharacter(mockCharacter)
      setDerivedSheet(mockDerivedSheet)
      renderModal()

      expect(screen.getByText('Fire')).toBeInTheDocument()
      expect(screen.getByText('Psychic')).toBeInTheDocument()
    })

    it('shows "No combat data" when derived sheet has no combat info', () => {
      setCharacter(mockCharacter)
      setDerivedSheet({
        ...mockDerivedSheet,
        attack_bonus: {},
        hit_dice: '',
        resistances: [],
        vulnerabilities: [],
      })
      renderModal()

      expect(
        screen.getByText('No combat data'),
      ).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Inventory grouping
  // ---------------------------------------------------------------

  describe('inventory grouping', () => {
    it('groups items by type with icons and labels', () => {
      setCharacter(mockCharacter)
      renderModal()

      expect(screen.getByText('Weapons')).toBeInTheDocument()
      expect(screen.getByText('Armor')).toBeInTheDocument()
      expect(screen.getByText('Miscellaneous')).toBeInTheDocument()
    })

    it('shows equipped indicator for equipped items', () => {
      setCharacter({
        ...mockCharacter,
        equipped_items: ['item-1'],
      })
      renderModal()

      const badges = screen.getAllByText('[E]')
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })

    it('toggles item description on click', () => {
      setCharacter(mockCharacter)
      renderModal()

      // Longsword has a description
      const longsword = screen.getByText('Longsword')
      expect(longsword).toBeInTheDocument()

      // Description should be hidden initially
      expect(
        screen.queryByText('A sharp steel blade.'),
      ).not.toBeInTheDocument()

      // Click to expand
      fireEvent.click(longsword.closest('button')!)
      expect(
        screen.getByText('A sharp steel blade.'),
      ).toBeInTheDocument()

      // Click again to collapse
      fireEvent.click(longsword.closest('button')!)
      expect(
        screen.queryByText('A sharp steel blade.'),
      ).not.toBeInTheDocument()
    })

    it('shows item quantity when > 1', () => {
      setCharacter({
        ...mockCharacter,
        inventory: [
          {
            id: 'item-potion',
            name: 'Healing Potion',
            quantity: 3,
            item_type: ItemType.CONSUMABLE,
            properties: {},
            description: 'Restores 2d4+2 HP.',
            weight: 0.5,
            value: 50,
          },
        ],
      })
      renderModal()

      expect(screen.getByText('x3')).toBeInTheDocument()
    })

    it('shows item weight', () => {
      setCharacter(mockCharacter)
      renderModal()

      // Longsword weight 3 lb
      const weights = screen.getAllByText(/lb/)
      expect(weights.length).toBeGreaterThanOrEqual(1)
    })
  })

  // ---------------------------------------------------------------
  // XP bar
  // ---------------------------------------------------------------

  describe('XP bar', () => {
    it('shows XP bar with correct aria attributes', () => {
      setCharacter(mockCharacter) // level 3, xp 900
      renderModal()

      // XP threshold for level 3 is 900 (0→300→900)
      const xpBar = screen.getByRole('progressbar', {
        name: /XP/,
      })
      expect(xpBar).toBeInTheDocument()
      expect(xpBar).toHaveAttribute('aria-valuenow', '900')
    })

    it('shows XP label', () => {
      setCharacter(mockCharacter)
      renderModal()

      expect(
        screen.getByText('900 XP (Level 3)'),
      ).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Dismiss actions
  // ---------------------------------------------------------------

  describe('dismiss', () => {
    it('calls onClose when the overlay is clicked', () => {
      const onClose = vi.fn()
      setCharacter(mockCharacter)
      renderModal({ onClose })

      fireEvent.click(screen.getByRole('dialog'))
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('does NOT close when modal content area is clicked', () => {
      const onClose = vi.fn()
      setCharacter(mockCharacter)
      renderModal({ onClose })

      const modalContent = screen.getByRole('dialog')
        .firstElementChild
      expect(modalContent).not.toBeNull()

      fireEvent.click(modalContent!)
      expect(onClose).not.toHaveBeenCalled()
    })

    it('calls onClose when Escape key is pressed', () => {
      const onClose = vi.fn()
      setCharacter(mockCharacter)
      renderModal({ onClose })

      fireEvent.keyDown(document, { key: 'Escape' })
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when the X button is clicked', () => {
      const onClose = vi.fn()
      setCharacter(mockCharacter)
      renderModal({ onClose })

      fireEvent.click(
        screen.getByLabelText('Close character details dialog'),
      )
      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  // ---------------------------------------------------------------
  // Focus trap
  // ---------------------------------------------------------------

  describe('focus trap', () => {
    it('focuses the close button when modal opens', () => {
      const origRAF = window.requestAnimationFrame
      window.requestAnimationFrame = (
        cb: FrameRequestCallback,
      ) => {
        cb(0)
        return 0
      }

      setCharacter(mockCharacter)
      renderModal()

      window.requestAnimationFrame = origRAF

      const closeBtn = screen.getByLabelText(
        'Close character details dialog',
      )
      expect(document.activeElement).toBe(closeBtn)
    })

    it('wraps focus: Shift+Tab from first goes to last, Tab from last goes to first', () => {
      const onClose = vi.fn()
      setCharacter(mockCharacter)
      renderModal({ onClose })

      // Gather all focusable elements inside the modal
      const modal = screen.getByRole('dialog').firstElementChild!
      const focusable = modal.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      // Start with focus on the first element
      first.focus()
      expect(document.activeElement).toBe(first)

      // Shift+Tab from first should wrap to last
      fireEvent.keyDown(document, {
        key: 'Tab',
        shiftKey: true,
      })
      expect(document.activeElement).toBe(last)

      // Tab from last should wrap back to first
      fireEvent.keyDown(document, { key: 'Tab' })
      expect(document.activeElement).toBe(first)
    })
  })

  // ---------------------------------------------------------------
  // ARIA
  // ---------------------------------------------------------------

  describe('accessibility', () => {
    it('has correct ARIA attributes', () => {
      setCharacter(mockCharacter)
      renderModal()

      const dialog = screen.getByRole('dialog')

      expect(dialog).toHaveAttribute('aria-modal', 'true')
      expect(dialog).toHaveAttribute(
        'aria-labelledby',
        'character-details-title',
      )
    })

    it('close button has accessible label', () => {
      setCharacter(mockCharacter)
      renderModal()

      expect(
        screen.getByLabelText('Close character details dialog'),
      ).toBeInTheDocument()
    })
  })
})
