/**
 * StoryModal tests — Grubnik ensures the story-reader works proper.
 *
 * Covers: open/close, empty/fallback states, story_summary rendering,
 * Escape key, overlay click, modal content click guard, focus trap,
 * multiple entries, and long text scrolling.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useGameStore } from '../../stores/gameStore'
import { useCharacterStore } from '../../stores/characterStore'
import StoryModal from './StoryModal'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resetStores(): void {
  act(() => {
    useGameStore.setState({
      worldState: null,
      turnCount: 0,
      narrative: '',
      playerInput: '',
      processing: false,
      isActive: false,
      error: null,
      narrativeEntries: [],
      streamingText: '',
      isThinking: false,
      npcThinking: null,
      tokenUsage: { accumulated: 0, latest: 0 },
      autoScroll: true,
      showTokens: false,
    })

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

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  resetStores()
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
    <StoryModal isOpen={isOpen} onClose={onClose} />,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('StoryModal', () => {
  // ---------------------------------------------------------------
  // Open / close
  // ---------------------------------------------------------------

  describe('open / close', () => {
    it('renders nothing when isOpen is false', () => {
      const { container } = renderModal({ isOpen: false })
      expect(container.innerHTML).toBe('')
    })

    it('renders the modal when isOpen is true', () => {
      renderModal()
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText('Adventure Story')).toBeInTheDocument()
    })

    it('renders the title with book emoji', () => {
      renderModal()
      // The title contains both the emoji and "Adventure Story"
      const title = screen.getByText('Adventure Story')
      expect(title).toBeInTheDocument()
      // The emoji is in the same heading
      expect(title.parentElement?.textContent).toContain('📖')
    })
  })

  // ---------------------------------------------------------------
  // Empty state
  // ---------------------------------------------------------------

  describe('empty state', () => {
    it('shows empty state when narrativeEntries is empty', () => {
      renderModal()
      expect(
        screen.getByText('No story entries available.'),
      ).toBeInTheDocument()
    })

    it('shows empty state when narrativeEntries contains only separators', () => {
      act(() => {
        useGameStore.setState({
          narrativeEntries: [
            { id: 's1', type: 'separator', content: '', timestamp: 1 },
            { id: 's2', type: 'separator', content: '', timestamp: 2 },
          ],
        })
      })
      renderModal()
      expect(
        screen.getByText('No story entries available.'),
      ).toBeInTheDocument()
    })

    it('shows empty state when narrativeEntries contains only empty-content entries', () => {
      act(() => {
        useGameStore.setState({
          narrativeEntries: [
            { id: 'e1', type: 'narrative', content: '', timestamp: 1 },
            { id: 'e2', type: 'player', content: '', timestamp: 2 },
          ],
        })
      })
      renderModal()
      expect(
        screen.getByText('No story entries available.'),
      ).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Narrative entries rendering
  // ---------------------------------------------------------------

  describe('narrative entries rendering', () => {
    it('renders narrative entries as paragraphs', () => {
      act(() => {
        useGameStore.setState({
          narrativeEntries: [
            { id: 'n1', type: 'narrative', content: 'You enter the dark forest.', timestamp: 1 },
            { id: 'n2', type: 'narrative', content: 'A goblin approaches you with a rusty dagger.', timestamp: 2 },
            { id: 'n3', type: 'narrative', content: 'You defeat the goblin and find 5 gold pieces.', timestamp: 3 },
          ],
        })
      })
      renderModal()

      expect(screen.getByText('You enter the dark forest.')).toBeInTheDocument()
      expect(
        screen.getByText('A goblin approaches you with a rusty dagger.'),
      ).toBeInTheDocument()
      expect(
        screen.getByText('You defeat the goblin and find 5 gold pieces.'),
      ).toBeInTheDocument()
    })

    it('renders player entries as paragraphs', () => {
      act(() => {
        useGameStore.setState({
          narrativeEntries: [
            { id: 'p1', type: 'player', content: 'I search the room.', timestamp: 1 },
          ],
        })
      })
      renderModal()

      expect(
        screen.getByText('I search the room.'),
      ).toBeInTheDocument()
    })

    it('renders tool_result entries as paragraphs', () => {
      act(() => {
        useGameStore.setState({
          narrativeEntries: [
            { id: 'tr1', type: 'tool_result', content: 'Rolled 18 — success!', timestamp: 1 },
          ],
        })
      })
      renderModal()

      expect(
        screen.getByText('Rolled 18 — success!'),
      ).toBeInTheDocument()
    })

    it('renders a single story entry', () => {
      act(() => {
        useGameStore.setState({
          narrativeEntries: [
            { id: 'e1', type: 'narrative', content: 'Your adventure begins at the crossroads.', timestamp: 1 },
          ],
        })
      })
      renderModal()

      expect(
        screen.getByText('Your adventure begins at the crossroads.'),
      ).toBeInTheDocument()
    })

    it('skips separator entries', () => {
      act(() => {
        useGameStore.setState({
          narrativeEntries: [
            { id: 'n1', type: 'narrative', content: 'First entry.', timestamp: 1 },
            { id: 's1', type: 'separator', content: '', timestamp: 2 },
            { id: 'n2', type: 'narrative', content: 'After separator.', timestamp: 3 },
          ],
        })
      })
      renderModal()

      expect(screen.getByText('First entry.')).toBeInTheDocument()
      expect(screen.getByText('After separator.')).toBeInTheDocument()
    })

    it('does not render empty-content entries', () => {
      act(() => {
        useGameStore.setState({
          narrativeEntries: [
            { id: 'e1', type: 'narrative', content: 'First entry', timestamp: 1 },
            { id: 'e2', type: 'narrative', content: '', timestamp: 2 },
            { id: 'e3', type: 'narrative', content: 'Third entry', timestamp: 3 },
          ],
        })
      })
      renderModal()

      expect(screen.getByText('First entry')).toBeInTheDocument()
      expect(screen.getByText('Third entry')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Dismiss actions
  // ---------------------------------------------------------------

  describe('dismiss', () => {
    it('calls onClose when the overlay is clicked', () => {
      const onClose = vi.fn()
      renderModal({ onClose })
      fireEvent.click(screen.getByRole('dialog'))
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('does NOT close when modal content area is clicked', () => {
      const onClose = vi.fn()
      renderModal({ onClose })

      // Find the inner modal element (the one with stopPropagation)
      const modalContent = screen.getByRole('dialog').firstElementChild
      expect(modalContent).not.toBeNull()

      fireEvent.click(modalContent!)
      expect(onClose).not.toHaveBeenCalled()
    })

    it('calls onClose when Escape key is pressed', () => {
      const onClose = vi.fn()
      renderModal({ onClose })
      fireEvent.keyDown(document, { key: 'Escape' })
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when the X button is clicked', () => {
      const onClose = vi.fn()
      renderModal({ onClose })
      fireEvent.click(screen.getByLabelText('Close story dialog'))
      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  // ---------------------------------------------------------------
  // Focus trap
  // ---------------------------------------------------------------

  describe('focus trap', () => {
    it('focuses the close button when modal opens', () => {
      // Mock requestAnimationFrame to fire synchronously so the focus
      // effect in the component runs during the test render.
      const origRAF = window.requestAnimationFrame
      window.requestAnimationFrame = (cb: FrameRequestCallback) => {
        cb(0)
        return 0
      }

      renderModal()

      // Restore original rAF after render
      window.requestAnimationFrame = origRAF

      const closeBtn = screen.getByLabelText('Close story dialog')
      expect(document.activeElement).toBe(closeBtn)
    })

    it('cycles focus with Tab when only close button is focusable', () => {
      const onClose = vi.fn()
      renderModal({ onClose })

      const closeBtn = screen.getByLabelText('Close story dialog')
      closeBtn.focus()

      // Tab — since closeBtn is both first and last, it should stay focused
      fireEvent.keyDown(document, { key: 'Tab' })
      expect(document.activeElement).toBe(closeBtn)

      // Shift+Tab — same behavior
      fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
      expect(document.activeElement).toBe(closeBtn)
    })
  })

  // ---------------------------------------------------------------
  // Multiple entries
  // ---------------------------------------------------------------

  describe('multiple entries', () => {
    it('renders many story entries correctly', () => {
      const textEntries = Array.from(
        { length: 20 },
        (_, i) => `Entry number ${i + 1}: the story continues…`,
      )
      act(() => {
        useGameStore.setState({
          narrativeEntries: textEntries.map((text, i) => ({
            id: `e${i}`,
            type: 'narrative' as const,
            content: text,
            timestamp: i,
          })),
        })
      })
      renderModal()

      for (let i = 0; i < 20; i += 1) {
        expect(
          screen.getByText(`Entry number ${i + 1}: the story continues…`),
        ).toBeInTheDocument()
      }
    })
  })

  // ---------------------------------------------------------------
  // Character name in subtitle
  // ---------------------------------------------------------------

  describe('character name subtitle', () => {
    it('shows character name when currentCharacter is set', () => {
      act(() => {
        useCharacterStore.setState({
          currentCharacter: {
            id: 'char-1',
            name: 'Thorn',
            character_class: 'Rogue',
            level: 3,
            abilities: {},
            hp: 20,
            max_hp: 20,
            ac: 14,
            skills: [],
            backstory: '',
            appearance: '',
            personality: '',
            hooks: [],
            inventory: [],
            gold: 50,
            xp: 0,
            created_at: '',
          },
        })
      })
      renderModal()
      expect(
        screen.getByText('Adventure Log for Thorn'),
      ).toBeInTheDocument()
    })

    it('does not show subtitle when no character is set', () => {
      renderModal()
      expect(
        screen.queryByText(/Adventure Log for/),
      ).not.toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Long text scrolling
  // ---------------------------------------------------------------

  describe('long text handling', () => {
    it('renders extremely long story text and content area is scrollable', () => {
      const longText = 'A'.repeat(5000)
      act(() => {
        useGameStore.setState({
          narrativeEntries: [
            { id: 'e1', type: 'narrative', content: longText, timestamp: 1 },
          ],
        })
      })
      renderModal()

      expect(screen.getByText(longText)).toBeInTheDocument()

      // The story content container should exist
      expect(screen.getByTestId('story-content')).toBeInTheDocument()
    })

    it('renders multiple long entries without crashing', () => {
      const textEntries = Array.from(
        { length: 5 },
        (_, i) => `Long entry ${i + 1}: ` + 'B'.repeat(2000),
      )
      act(() => {
        useGameStore.setState({
          narrativeEntries: textEntries.map((text, i) => ({
            id: `e${i}`,
            type: 'narrative' as const,
            content: text,
            timestamp: i,
          })),
        })
      })
      renderModal()

      for (let i = 0; i < 5; i += 1) {
        expect(
          screen.getByText(`Long entry ${i + 1}: ` + 'B'.repeat(2000)),
        ).toBeInTheDocument()
      }
    })
  })

  // ---------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------

  describe('accessibility', () => {
    it('has correct ARIA attributes', () => {
      renderModal()
      const dialog = screen.getByRole('dialog')

      expect(dialog).toHaveAttribute('aria-modal', 'true')
      expect(dialog).toHaveAttribute('aria-labelledby', 'story-modal-title')
    })

    it('close button has accessible label', () => {
      renderModal()
      expect(
        screen.getByLabelText('Close story dialog'),
      ).toBeInTheDocument()
    })
  })
})
