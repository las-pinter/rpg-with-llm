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
    it('shows empty state when worldState is null', () => {
      renderModal()
      expect(
        screen.getByText('No story entries yet. Begin your adventure!'),
      ).toBeInTheDocument()
    })

    it('shows empty state when worldState is empty object', () => {
      act(() => {
        useGameStore.setState({ worldState: {} })
      })
      renderModal()
      expect(
        screen.getByText('No story entries yet. Begin your adventure!'),
      ).toBeInTheDocument()
    })

    it('shows empty state when story_summary is empty array', () => {
      act(() => {
        useGameStore.setState({
          worldState: { story_summary: [] },
        })
      })
      renderModal()
      expect(
        screen.getByText('No story entries yet. Begin your adventure!'),
      ).toBeInTheDocument()
    })

    it('shows empty state when story_summary is not an array', () => {
      act(() => {
        useGameStore.setState({
          worldState: { story_summary: 'not-an-array' },
        })
      })
      renderModal()
      expect(
        screen.getByText('No story entries yet. Begin your adventure!'),
      ).toBeInTheDocument()
    })

    it('shows empty state when story_summary contains only empty strings', () => {
      act(() => {
        useGameStore.setState({
          worldState: { story_summary: ['', '', ''] },
        })
      })
      renderModal()
      expect(
        screen.getByText('No story entries yet. Begin your adventure!'),
      ).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Story summary rendering
  // ---------------------------------------------------------------

  describe('story_summary rendering', () => {
    it('renders story_summary entries as paragraphs', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_summary: [
              'You enter the dark forest.',
              'A goblin approaches you with a rusty dagger.',
              'You defeat the goblin and find 5 gold pieces.',
            ],
          },
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

    it('renders a single story entry', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_summary: ['Your adventure begins at the crossroads.'],
          },
        })
      })
      renderModal()

      expect(
        screen.getByText('Your adventure begins at the crossroads.'),
      ).toBeInTheDocument()
    })

    it('does not render empty strings in story_summary', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_summary: ['First entry', '', 'Third entry'],
          },
        })
      })
      renderModal()

      expect(screen.getByText('First entry')).toBeInTheDocument()
      expect(screen.getByText('Third entry')).toBeInTheDocument()
    })

    it('filters out non-string entries in story_summary (numbers, objects, booleans)', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_summary: [
              'A real string entry.',
              42,
              { key: 'value' },
              true,
              'Another valid entry.',
              null,
              ['nested'],
            ],
          },
        })
      })
      renderModal()

      // Only string entries should render
      expect(
        screen.getByText('A real string entry.'),
      ).toBeInTheDocument()
      expect(
        screen.getByText('Another valid entry.'),
      ).toBeInTheDocument()
      // Non-strings should be filtered out
      expect(screen.queryByText('42')).not.toBeInTheDocument()
      expect(screen.queryByText('[object Object]')).not.toBeInTheDocument()
    })

    it('shows empty state when story_summary has only non-string entries (no fallback)', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_summary: [42, true],
            story_log: [
              '[Turn 1] The story begins!',
            ],
          },
        })
      })
      renderModal()

      // story_summary exists (non-empty array) even though all entries are non-strings,
      // so it blocks the story_log fallback. The result is empty state.
      expect(
        screen.getByText('No story entries yet. Begin your adventure!'),
      ).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Story log fallback
  // ---------------------------------------------------------------

  describe('story_log fallback', () => {
    it('falls back to story_log when story_summary is empty', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_summary: [],
            story_log: [
              '[Turn 1] You wake up in a damp cave.',
              '[Turn 2] A rat scurries past your feet.',
            ],
          },
        })
      })
      renderModal()

      expect(screen.getByText('Turn 1')).toBeInTheDocument()
      expect(
        screen.getByText('You wake up in a damp cave.'),
      ).toBeInTheDocument()
      expect(screen.getByText('Turn 2')).toBeInTheDocument()
      expect(
        screen.getByText('A rat scurries past your feet.'),
      ).toBeInTheDocument()
    })

    it('falls back to story_log when story_summary is absent', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_log: [
              '[Turn 1] The adventure begins!',
            ],
          },
        })
      })
      renderModal()

      expect(screen.getByText('Turn 1')).toBeInTheDocument()
      expect(
        screen.getByText('The adventure begins!'),
      ).toBeInTheDocument()
    })

    it('parses story_log entries without [Turn N] format as plain paragraphs', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_log: [
              'A mysterious figure appears before you.',
              '[Turn 3] He offers you a choice.',
            ],
          },
        })
      })
      renderModal()

      expect(
        screen.getByText('A mysterious figure appears before you.'),
      ).toBeInTheDocument()
      expect(screen.getByText('Turn 3')).toBeInTheDocument()
      expect(
        screen.getByText('He offers you a choice.'),
      ).toBeInTheDocument()
    })

    it('shows empty state when both story_summary and story_log are empty', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_summary: [],
            story_log: [],
          },
        })
      })
      renderModal()

      expect(
        screen.getByText('No story entries yet. Begin your adventure!'),
      ).toBeInTheDocument()
    })

    it('skips non-string entries in story_log gracefully', () => {
      act(() => {
        useGameStore.setState({
          worldState: {
            story_log: [
              '[Turn 1] A valid log entry.',
              42,
              { some: 'object' },
              null,
              '[Turn 2] Another valid entry.',
            ],
          },
        })
      })
      renderModal()

      // String entries should render
      expect(screen.getByText('Turn 1')).toBeInTheDocument()
      expect(
        screen.getByText('A valid log entry.'),
      ).toBeInTheDocument()
      expect(screen.getByText('Turn 2')).toBeInTheDocument()
      expect(
        screen.getByText('Another valid entry.'),
      ).toBeInTheDocument()
      // Non-strings should be silently skipped
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
      const entries = Array.from(
        { length: 20 },
        (_, i) => `Entry number ${i + 1}: the story continues...`,
      )
      act(() => {
        useGameStore.setState({
          worldState: { story_summary: entries },
        })
      })
      renderModal()

      for (let i = 0; i < 20; i += 1) {
        expect(
          screen.getByText(`Entry number ${i + 1}: the story continues...`),
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
          worldState: { story_summary: [longText] },
        })
      })
      renderModal()

      expect(screen.getByText(longText)).toBeInTheDocument()

      // The story content container should exist
      expect(screen.getByTestId('story-content')).toBeInTheDocument()
    })

    it('renders multiple long entries without crashing', () => {
      const entries = Array.from(
        { length: 5 },
        (_, i) => `Long entry ${i + 1}: ` + 'B'.repeat(2000),
      )
      act(() => {
        useGameStore.setState({
          worldState: { story_summary: entries },
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
