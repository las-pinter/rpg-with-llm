/**
 * CharacterDetailsModal tests — Grubnik makes sure the character sheet
 * modal shows all the right bits and closes proper.
 *
 * Covers: open/close, empty state, full character rendering, HP bar
 * colours, ability scores, skills, inventory, hooks, Escape key,
 * overlay click, modal content click guard, focus trap, ARIA.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useCharacterStore } from '../../stores/characterStore'
import CharacterDetailsModal from './CharacterDetailsModal'
import type { Character } from '../../api/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockCharacter: Character = {
  name: 'Thorn Ironfoot',
  character_class: 'Fighter',
  level: 3,
  abilities: { STR: 16, DEX: 14, CON: 15, INT: 10, WIS: 12, CHA: 8 },
  hp: 24,
  max_hp: 30,
  ac: 16,
  skills: ['Athletics', 'Perception', 'Intimidation'],
  backstory: 'A grizzled warrior from the northern mountains.',
  appearance: 'Scarred face, missing left ear.',
  personality: 'Gruff but loyal.',
  hooks: ['A rival from the past seeks revenge.'],
  inventory: ['Longsword', 'Shield', 'Bedroll'],
  gold: 50,
  xp: 900,
  created_at: '2026-01-01T00:00:00Z',
}

function resetStore(): void {
  act(() => {
    useCharacterStore.setState({
      currentCharacter: null,
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
      // (some numbers like 16 may appear in both AC stat and ability scores)
      expect(screen.getAllByText('16').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('14').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('15').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('10')).toBeInTheDocument()
      expect(screen.getByText('12')).toBeInTheDocument()
      expect(screen.getByText('8')).toBeInTheDocument()
    })

    it('shows skills as tags', () => {
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
      setCharacter({ ...mockCharacter, inventory: [] })
      renderModal()

      expect(
        screen.getByText('Nothing carried'),
      ).toBeInTheDocument()
    })

    it('shows "No skills" when skills array is empty', () => {
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
      // Each value should show dash (we expect 6 dashes, one per ability)
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
        hp: 25,
        max_hp: 30,
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
        hp: 14,
        max_hp: 30,
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill).toBeInTheDocument()
      expect(fill?.className).toContain('hpYellow')
    })

    it('shows red HP bar when below 30%', () => {
      setCharacter({
        ...mockCharacter,
        hp: 5,
        max_hp: 30,
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill).toBeInTheDocument()
      expect(fill?.className).toContain('hpRed')
    })

    it('shows red HP bar at 0 HP', () => {
      setCharacter({
        ...mockCharacter,
        hp: 0,
        max_hp: 30,
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
        hp: 18,
        max_hp: 30,
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill?.className).toContain('hpYellow')
    })

    it('shows red HP bar at exactly 30% (boundary)', () => {
      // ratio === 0.3 -> NOT > 0.3, so red
      setCharacter({
        ...mockCharacter,
        hp: 9,
        max_hp: 30,
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill?.className).toContain('hpRed')
    })

    it('handles negative HP by clamping to 0 and showing red', () => {
      setCharacter({
        ...mockCharacter,
        hp: -5,
        max_hp: 30,
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
        hp: 10,
        max_hp: 0,
      })
      renderModal()

      const fill = getHpFillElement()
      expect(fill).toBeInTheDocument()
      // hpRatio = 0 (max_hp > 0 is false), hpPercent = 0
      expect(fill?.className).toContain('hpRed')
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

    it('cycles focus with Tab when only close button is focusable', () => {
      const onClose = vi.fn()
      setCharacter(mockCharacter)
      renderModal({ onClose })

      const closeBtn = screen.getByLabelText(
        'Close character details dialog',
      )
      closeBtn.focus()

      // Tab — since closeBtn is both first and last, it stays focused
      fireEvent.keyDown(document, { key: 'Tab' })
      expect(document.activeElement).toBe(closeBtn)

      // Shift+Tab — same behaviour
      fireEvent.keyDown(document, {
        key: 'Tab',
        shiftKey: true,
      })
      expect(document.activeElement).toBe(closeBtn)
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
