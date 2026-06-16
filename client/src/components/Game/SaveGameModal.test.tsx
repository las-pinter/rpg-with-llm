/**
 * SaveGameModal tests — Grubnik checks the 4-state machine works proper.
 *
 * Covers: open/close, escape key, overlay click, name input, save flow
 * (input → saving → success / error), auto-close timer, onSaved callback.
 *
 * Strategy: each test that calls the save API uses a fresh vi.spyOn so there
 * is zero cross-test interference.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { useGameStore } from '../../stores/gameStore'
import { useCharacterStore } from '../../stores/characterStore'
import * as endpoints from '../../api/endpoints'
import SaveGameModal from './SaveGameModal'

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
      tokenUsage: {
        total: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        latest: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      },
      autoScroll: true,
      showTokens: true,
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

/** Create a deferred promise + manually-typed resolve/reject. */
function deferred<T>(): {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason: unknown) => void
} {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  resetStores()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers() // undo any fake timers left by failed tests
})

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

interface RenderModalOptions {
  isOpen?: boolean
  onClose?: () => void
  onSaved?: (slug: string) => void
}

function renderModal(opts: RenderModalOptions = {}) {
  const { isOpen = true, onClose = vi.fn(), onSaved = vi.fn() } = opts
  return render(
    <SaveGameModal isOpen={isOpen} onClose={onClose} onSaved={onSaved} />,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SaveGameModal', () => {
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
      expect(screen.getByText('Save Game')).toBeInTheDocument()
    })

    it('shows an auto-generated save name in the input', () => {
      renderModal()
      const input = screen.getByLabelText('Save Name') as HTMLInputElement
      expect(input.value).toContain('Adventure - Turn 0')
    })

    it('includes character name in auto-generated name when available', () => {
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
      const input = screen.getByLabelText('Save Name') as HTMLInputElement
      expect(input.value).toContain('Thorn - Turn 0')
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

    it('does NOT close via overlay click during saving phase', async () => {
      // Use never-resolving save so component stays in 'saving' phase
      vi.spyOn(endpoints, 'saveGame').mockImplementation(
        () => new Promise<never>(() => {}),
      )
      const onClose = vi.fn()
      renderModal({ onClose })

      fireEvent.click(screen.getByText('Save'))
      await waitFor(() => {
        expect(screen.getByText('Saving…')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('dialog'))
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
      fireEvent.click(screen.getByLabelText('Close save dialog'))
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when Cancel button is clicked', () => {
      const onClose = vi.fn()
      renderModal({ onClose })
      fireEvent.click(screen.getByText('Cancel'))
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('does not close via Escape during saving phase', async () => {
      vi.spyOn(endpoints, 'saveGame').mockImplementation(
        () => new Promise<never>(() => {}),
      )
      const onClose = vi.fn()
      renderModal({ onClose })

      fireEvent.click(screen.getByText('Save'))
      await waitFor(() => {
        expect(screen.getByText('Saving…')).toBeInTheDocument()
      })

      fireEvent.keyDown(document, { key: 'Escape' })
      expect(onClose).not.toHaveBeenCalled()
    })
  })

  // ---------------------------------------------------------------
  // State machine: INPUT
  // ---------------------------------------------------------------

  describe('input phase', () => {
    it('shows the name input, Save button, and Cancel button', () => {
      renderModal()
      expect(screen.getByLabelText('Save Name')).toBeInTheDocument()
      expect(screen.getByText('Save')).toBeInTheDocument()
      expect(screen.getByText('Cancel')).toBeInTheDocument()
    })

    it('allows editing the save name', () => {
      renderModal()
      const input = screen.getByLabelText('Save Name') as HTMLInputElement
      fireEvent.change(input, { target: { value: 'My Custom Save' } })
      expect(input.value).toBe('My Custom Save')
    })

    it('shows error when trying to save with empty name', async () => {
      renderModal()
      const input = screen.getByLabelText('Save Name') as HTMLInputElement
      fireEvent.change(input, { target: { value: '' } })
      fireEvent.click(screen.getByText('Save'))

      await waitFor(() => {
        expect(
          screen.getByText('Please enter a save name.'),
        ).toBeInTheDocument()
      })
      // Should still show Try Again / Cancel (error phase now)
      expect(screen.getByText('Try Again')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // State machine: SAVING
  // ---------------------------------------------------------------

  describe('saving phase', () => {
    it('shows a spinner and "Saving…" text while saving', async () => {
      vi.spyOn(endpoints, 'saveGame').mockImplementation(
        () => new Promise<never>(() => {}),
      )
      renderModal()

      fireEvent.click(screen.getByText('Save'))

      await waitFor(() => {
        expect(screen.getByText('Saving…')).toBeInTheDocument()
      })
      // The input and buttons should be gone
      expect(screen.queryByLabelText('Save Name')).not.toBeInTheDocument()
      expect(screen.queryByText('Cancel')).not.toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // State machine: SUCCESS
  // ---------------------------------------------------------------

  describe('success phase', () => {
    it('shows a checkmark and "Game saved!" on success', async () => {
      const { promise, resolve } = deferred<{ ok: boolean; slug: string }>()
      vi.spyOn(endpoints, 'saveGame').mockImplementation(() => promise)
      renderModal()

      fireEvent.click(screen.getByText('Save'))

      // Let the save resolve
      await act(async () => {
        resolve({ ok: true, slug: 'test-save-abc' })
      })

      await waitFor(() => {
        expect(screen.getByText('Game saved!')).toBeInTheDocument()
      })
      // Checkmark should be visible
      expect(screen.getByText('✓')).toBeInTheDocument()
    })

    it('calls onSaved with the slug and then onClose after 1.2s', async () => {
      vi.useFakeTimers()
      const { promise, resolve } = deferred<{ ok: boolean; slug: string }>()
      vi.spyOn(endpoints, 'saveGame').mockImplementation(() => promise)

      const onClose = vi.fn()
      const onSaved = vi.fn()
      renderModal({ onClose, onSaved })

      fireEvent.click(screen.getByText('Save'))

      // Resolve the save — act flushes all React updates after the microtask
      await act(async () => {
        resolve({ ok: true, slug: 'my-save-42' })
      })

      // After act, the DOM should already be updated — no waitFor needed
      expect(screen.getByText('Game saved!')).toBeInTheDocument()

      // Advance timer by 1.2s to trigger the auto-close
      act(() => {
        vi.advanceTimersByTime(1200)
      })

      expect(onSaved).toHaveBeenCalledWith('my-save-42')
      expect(onClose).toHaveBeenCalledTimes(1)
      vi.useRealTimers()
    })

    it('cleans up the auto-close timer on unmount', async () => {
      vi.useFakeTimers()
      const { promise, resolve } = deferred<{ ok: boolean; slug: string }>()
      vi.spyOn(endpoints, 'saveGame').mockImplementation(() => promise)

      const onClose = vi.fn()
      const { unmount } = renderModal({ onClose })

      fireEvent.click(screen.getByText('Save'))

      await act(async () => {
        resolve({ ok: true, slug: 'test' })
      })

      // act flushes, so Game saved! should be visible
      expect(screen.getByText('Game saved!')).toBeInTheDocument()

      // Unmount while timer is still pending
      unmount()

      // Advance past the timer to make sure it doesn't fire
      act(() => {
        vi.advanceTimersByTime(1200)
      })
      expect(onClose).not.toHaveBeenCalled()
      vi.useRealTimers()
    })
  })

  // ---------------------------------------------------------------
  // State machine: ERROR
  // ---------------------------------------------------------------

  describe('error phase', () => {
    it('shows error message when save throws', async () => {
      const { promise, reject } = deferred<{ ok: boolean; slug: string }>()
      vi.spyOn(endpoints, 'saveGame').mockImplementation(() => promise)
      renderModal()

      fireEvent.click(screen.getByText('Save'))

      await act(async () => {
        reject(new Error('Network failure'))
      })

      await waitFor(() => {
        expect(screen.getByText('Network failure')).toBeInTheDocument()
      })
      expect(screen.getByText('Try Again')).toBeInTheDocument()
      expect(screen.getByText('Cancel')).toBeInTheDocument()
    })

    it('shows error when server returns ok: false', async () => {
      const { promise, resolve } = deferred<{ ok: boolean; slug: string }>()
      vi.spyOn(endpoints, 'saveGame').mockImplementation(() => promise)
      renderModal()

      fireEvent.click(screen.getByText('Save'))

      await act(async () => {
        resolve({ ok: false, slug: '' })
      })

      await waitFor(() => {
        expect(
          screen.getByText(/server returned an error/),
        ).toBeInTheDocument()
      })
    })

    it('retries with Try Again button', async () => {
      // First call: fail
      const firstDef = deferred<{ ok: boolean; slug: string }>()
      // Second call: succeed
      const secondDef = deferred<{ ok: boolean; slug: string }>()
      let callCount = 0
      vi.spyOn(endpoints, 'saveGame').mockImplementation(() => {
        callCount++
        return callCount === 1 ? firstDef.promise : secondDef.promise
      })

      renderModal()
      fireEvent.click(screen.getByText('Save'))

      await act(async () => {
        firstDef.reject(new Error('Network failure'))
      })

      await waitFor(() => {
        expect(screen.getByText('Network failure')).toBeInTheDocument()
      })

      // Click Try Again — uses the second deferred
      fireEvent.click(screen.getByText('Try Again'))

      await act(async () => {
        secondDef.resolve({ ok: true, slug: 'retry-slug' })
      })

      await waitFor(() => {
        expect(screen.getByText('Game saved!')).toBeInTheDocument()
      })
    })
  })

  // ---------------------------------------------------------------
  // Integration: worldState included in save
  // ---------------------------------------------------------------

  describe('save payload', () => {
    it('includes worldState and character data in the save payload', async () => {
      // Set up stores with data
      act(() => {
        useGameStore.setState({
          worldState: { location: 'Dungeon', hp: 30, gold: 100 },
          turnCount: 5,
        })
        useCharacterStore.setState({
          currentCharacter: {
            id: 'char-99',
            name: 'Grom',
            character_class: 'Fighter',
            level: 2,
            abilities: { str: 16, dex: 12 },
            hp: 25,
            max_hp: 25,
            ac: 16,
            skills: ['Athletics'],
            backstory: 'A hardy warrior.',
            appearance: 'Scarred face',
            personality: 'Brave',
            hooks: ['Lost brother'],
            inventory: ['Sword'],
            gold: 75,
            xp: 300,
            created_at: '2025-01-01',
          },
        })
      })

      const { promise, resolve } = deferred<{ ok: boolean; slug: string }>()
      const saveSpy = vi
        .spyOn(endpoints, 'saveGame')
        .mockImplementation(() => promise)

      renderModal()

      const input = screen.getByLabelText('Save Name') as HTMLInputElement
      expect(input.value).toContain('Grom - Turn 5')

      fireEvent.click(screen.getByText('Save'))

      // Wait for saveGame to be called
      await waitFor(() => {
        expect(saveSpy).toHaveBeenCalledTimes(1)
      })

      const callArg = saveSpy.mock.calls[0]![0]
      expect(callArg.name).toBe(input.value)
      expect(callArg.state).toBeDefined()
      expect(callArg.state?._character).toBeDefined()
      expect((callArg.state?._character as Record<string, unknown>).name).toBe(
        'Grom',
      )
      expect((callArg.state as Record<string, unknown>).location).toBe('Dungeon')

      // Resolve so the component doesn't hang
      await act(async () => {
        resolve({ ok: true, slug: 'grom-save' })
      })
    })

    it('embeds character id as string', async () => {
      act(() => {
        useCharacterStore.setState({
          currentCharacter: {
            id: '42',
            name: 'Test',
            character_class: 'Mage',
            level: 1,
            abilities: {},
            hp: 10,
            max_hp: 10,
            ac: 10,
            skills: [],
            backstory: '',
            appearance: '',
            personality: '',
            hooks: [],
            inventory: [],
            gold: 0,
            xp: 0,
            created_at: '',
          },
        })
        useGameStore.setState({ worldState: {}, turnCount: 1 })
      })

      const { promise, resolve } = deferred<{ ok: boolean; slug: string }>()
      const saveSpy = vi
        .spyOn(endpoints, 'saveGame')
        .mockImplementation(() => promise)

      renderModal()
      fireEvent.click(screen.getByText('Save'))

      await waitFor(() => {
        expect(saveSpy).toHaveBeenCalled()
      })

      const arg = saveSpy.mock.calls[0]![0]
      const embedded = arg.state?._character as Record<string, unknown>
      expect(embedded.id).toBe('42')
      expect(typeof embedded.id).toBe('string')

      await act(async () => {
        resolve({ ok: true, slug: 'test' })
      })
    })
  })

  // ---------------------------------------------------------------
  // Edge: null worldState
  // ---------------------------------------------------------------

  describe('edge cases', () => {
    it('handles null worldState gracefully', async () => {
      act(() => {
        useGameStore.setState({ worldState: null, turnCount: 0 })
      })

      const { promise, resolve } = deferred<{ ok: boolean; slug: string }>()
      const saveSpy = vi
        .spyOn(endpoints, 'saveGame')
        .mockImplementation(() => promise)

      renderModal()
      fireEvent.click(screen.getByText('Save'))

      await waitFor(() => {
        expect(saveSpy).toHaveBeenCalled()
      })

      const arg = saveSpy.mock.calls[0]![0]
      expect(arg.state).toEqual({})

      await act(async () => {
        resolve({ ok: true, slug: 'null-state' })
      })
    })
  })
})
