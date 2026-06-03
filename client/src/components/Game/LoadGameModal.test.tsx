/**
 * LoadGameModal tests — Frettnik checks every state machine phase and card interaction.
 *
 * Covers: open/close, fetch states (loading/empty/list/fetchError),
 * load flow (card spinner → success/error), delete flow (confirm → deleting → deleted),
 * dismiss, re-fetch on reopen, and optional field handling.
 *
 * Strategy: each test that calls an API uses a fresh vi.spyOn so there
 * is zero cross-test interference.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { useGameStore } from '../../stores/gameStore'
import { useCharacterStore } from '../../stores/characterStore'
import * as endpoints from '../../api/endpoints'
import type { SavesListResponse, LoadResponse, SuccessResponse } from '../../api/types'
import LoadGameModal from './LoadGameModal'

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
// Test data
// ---------------------------------------------------------------------------

const SAVES_LIST: SavesListResponse = {
  ok: true,
  saves: [
    {
      id: 'save-1',
      name: 'Dungeon of Doom',
      timestamp: '2026-06-01T14:30:00Z',
      character_name: 'Thorn',
      turn_count: 42,
    },
    {
      id: 'save-2',
      name: 'Forest Retreat',
      timestamp: '2026-05-28T09:15:00Z',
      character_name: 'Elara',
      turn_count: 17,
    },
  ],
}

const SINGLE_SAVE: SavesListResponse = {
  ok: true,
  saves: [SAVES_LIST.saves[0]],
}

const EMPTY_LIST: SavesListResponse = { ok: true, saves: [] }

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  resetStores()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

interface RenderModalOptions {
  isOpen?: boolean
  onClose?: () => void
  onLoaded?: (state: Record<string, unknown>, character?: Record<string, unknown>) => void
}

function renderModal(opts: RenderModalOptions = {}) {
  const { isOpen = true, onClose = vi.fn(), onLoaded = vi.fn() } = opts
  return render(
    <LoadGameModal isOpen={isOpen} onClose={onClose} onLoaded={onLoaded} />,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LoadGameModal', () => {
  // ---------------------------------------------------------------
  // Rendering & Initial State
  // ---------------------------------------------------------------

  describe('rendering / initial state', () => {
    it('renders nothing when isOpen is false', () => {
      const { container } = renderModal({ isOpen: false })
      expect(container.innerHTML).toBe('')
    })

    it('renders the modal when isOpen is true', () => {
      // Keep listSaves pending to avoid async state updates outside act
      vi.spyOn(endpoints, 'listSaves').mockImplementation(
        () => new Promise<never>(() => {}),
      )
      renderModal()
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText('Load Game')).toBeInTheDocument()
    })

    it('shows a loading spinner and "Loading saves..." initially', () => {
      // Keep listSaves pending so the component stays in LOADING phase
      vi.spyOn(endpoints, 'listSaves').mockImplementation(
        () => new Promise<never>(() => {}),
      )
      renderModal()
      expect(screen.getByText('Loading saves...')).toBeInTheDocument()
    })

    it('calls listSaves() on open', async () => {
      const mockList = vi.spyOn(endpoints, 'listSaves').mockImplementation(
        () => new Promise<never>(() => {}),
      )
      renderModal()
      // useLayoutEffect fires synchronously on mount and calls fetchSaves,
      // which synchronously calls listSaves() before the first await.
      await waitFor(() => {
        expect(mockList).toHaveBeenCalledTimes(1)
      })
    })
  })

  // ---------------------------------------------------------------
  // Empty State
  // ---------------------------------------------------------------

  describe('empty state', () => {
    it('shows "No saved games found." when save list is empty', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      renderModal()

      await act(async () => {
        resolve(EMPTY_LIST)
      })

      await waitFor(() => {
        expect(screen.getByText('No saved games found.')).toBeInTheDocument()
      })
    })

    it('shows a Close button in empty state', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      renderModal()

      await act(async () => {
        resolve(EMPTY_LIST)
      })

      await waitFor(() => {
        expect(screen.getByText('Close')).toBeInTheDocument()
      })
      // The Close button should be the one inside the empty state,
      // not the ✕ close button in the top corner
      expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Save List
  // ---------------------------------------------------------------

  describe('save list', () => {
    it('renders save cards with name, character, and turn count', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      renderModal()

      await act(async () => {
        resolve(SINGLE_SAVE)
      })

      await waitFor(() => {
        expect(screen.getByText('Dungeon of Doom')).toBeInTheDocument()
        expect(screen.getByText('Thorn')).toBeInTheDocument()
        expect(screen.getByText(/Turn 42/)).toBeInTheDocument()
      })
    })

    it('formats timestamp correctly', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      renderModal()

      await act(async () => {
        resolve(SINGLE_SAVE)
      })

      await waitFor(() => {
        // The formatted timestamp should contain the year
        expect(screen.getByText(/2026/)).toBeInTheDocument()
      })
    })

    it('shows multiple saves in order', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      renderModal()

      await act(async () => {
        resolve(SAVES_LIST)
      })

      await waitFor(() => {
        expect(screen.getByText('Dungeon of Doom')).toBeInTheDocument()
        expect(screen.getByText('Forest Retreat')).toBeInTheDocument()
      })
      // Each card should have its own Load and Delete buttons
      expect(screen.getAllByText('Load')).toHaveLength(2)
      expect(screen.getAllByText('Delete')).toHaveLength(2)
    })
  })

  // ---------------------------------------------------------------
  // Load Flow
  // ---------------------------------------------------------------

  describe('load flow', () => {
    it('calls loadGame with the correct slug when Load is clicked', async () => {
      const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
      const { promise: loadPromise, resolve: resolveLoad } = deferred<LoadResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
      const mockLoad = vi.spyOn(endpoints, 'loadGame').mockReturnValue(loadPromise)
      renderModal()

      await act(async () => {
        resolveList(SINGLE_SAVE)
      })
      await waitFor(() => {
        expect(screen.getByText('Load')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Load'))

      await waitFor(() => {
        expect(mockLoad).toHaveBeenCalledWith('save-1')
      })

      // Resolve so there is no hanging promise warning
      await act(async () => {
        resolveLoad({ ok: true, state: {} })
      })
    })

    it('shows a spinner on the card during load and hides Load/Delete', async () => {
      const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
      // Never-resolving load promise keeps the card in loading state
      vi.spyOn(endpoints, 'loadGame').mockImplementation(
        () => new Promise<never>(() => {}),
      )
      const { container } = renderModal()

      await act(async () => {
        resolveList(SINGLE_SAVE)
      })
      await waitFor(() => {
        expect(screen.getByText('Load')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Load'))

      // The card should no longer show Load/Delete buttons
      await waitFor(() => {
        expect(screen.queryByText('Load')).not.toBeInTheDocument()
        expect(screen.queryByText('Delete')).not.toBeInTheDocument()
      })
      // The card text should still be visible
      expect(container.textContent).toContain('Dungeon of Doom')
    })

    it('calls onLoaded with state and character on successful load', async () => {
      const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
      const { promise: loadPromise, resolve: resolveLoad } = deferred<LoadResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
      vi.spyOn(endpoints, 'loadGame').mockReturnValue(loadPromise)

      const onLoaded = vi.fn()
      renderModal({ onLoaded })

      await act(async () => {
        resolveList(SINGLE_SAVE)
      })
      await waitFor(() => {
        expect(screen.getByText('Load')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Load'))

      await act(async () => {
        resolveLoad({
          ok: true,
          state: { location: 'Castle', hp: 50 },
          character: { name: 'Thorn', class: 'Rogue' },
        })
      })

      await waitFor(() => {
        expect(onLoaded).toHaveBeenCalledWith(
          { location: 'Castle', hp: 50 },
          { name: 'Thorn', class: 'Rogue' },
        )
      })
    })

    it('closes modal on successful load', async () => {
      const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
      const { promise: loadPromise, resolve: resolveLoad } = deferred<LoadResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
      vi.spyOn(endpoints, 'loadGame').mockReturnValue(loadPromise)

      const onClose = vi.fn()
      renderModal({ onClose })

      await act(async () => {
        resolveList(SINGLE_SAVE)
      })
      await waitFor(() => {
        expect(screen.getByText('Load')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Load'))

      await act(async () => {
        resolveLoad({ ok: true, state: { location: 'Dungeon' } })
      })

      await waitFor(() => {
        expect(onClose).toHaveBeenCalledTimes(1)
      })
    })

    it('shows error on the card when load fails', async () => {
      const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
      const { promise: loadPromise, reject: rejectLoad } = deferred<LoadResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
      vi.spyOn(endpoints, 'loadGame').mockReturnValue(loadPromise)
      renderModal()

      await act(async () => {
        resolveList(SINGLE_SAVE)
      })
      await waitFor(() => {
        expect(screen.getByText('Load')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Load'))

      await act(async () => {
        rejectLoad(new Error('Server unreachable'))
      })

      await waitFor(() => {
        expect(screen.getByText('Failed to load game.')).toBeInTheDocument()
      })
      // The Load button should return so the user can retry
      expect(screen.getByText('Load')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Delete Flow
  // ---------------------------------------------------------------

  describe('delete flow', () => {
    it('shows a confirm dialog when Delete is clicked', async () => {
      const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
      renderModal()

      await act(async () => {
        resolveList(SINGLE_SAVE)
      })
      await waitFor(() => {
        expect(screen.getByText('Delete')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Delete'))

      await waitFor(() => {
        // The confirm overlay shows &lsquo;/&rsquo; curly quotes around the name,
        // so we verify via the button presence instead of matching broken text
        expect(screen.getByText('Yes, delete')).toBeInTheDocument()
        expect(screen.getByText('Cancel')).toBeInTheDocument()
      })
    })

    it('calls deleteSave with the correct slug on confirm', async () => {
      const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
      const { promise: delPromise, resolve: resolveDel } = deferred<SuccessResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
      const mockDel = vi.spyOn(endpoints, 'deleteSave').mockReturnValue(delPromise)
      renderModal()

      await act(async () => {
        resolveList(SINGLE_SAVE)
      })
      await waitFor(() => {
        expect(screen.getByText('Delete')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Delete'))
      await waitFor(() => {
        expect(screen.getByText('Yes, delete')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Yes, delete'))

      await waitFor(() => {
        expect(mockDel).toHaveBeenCalledWith('save-1')
      })

      // Resolve to avoid hanging promises
      await act(async () => {
        resolveDel({ ok: true })
      })
    })

    it('shows "Deleted!" feedback then removes the card after timeout', async () => {
      vi.useFakeTimers()
      const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
      const { promise: delPromise, resolve: resolveDel } = deferred<SuccessResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
      vi.spyOn(endpoints, 'deleteSave').mockReturnValue(delPromise)
      renderModal()

      // Resolve the list — act flushes the state
      await act(async () => {
        resolveList(SINGLE_SAVE)
      })
      // DOM should be updated after act; waitFor uses setTimeout which is faked
      expect(screen.getByText('Dungeon of Doom')).toBeInTheDocument()
      expect(screen.getByText('Delete')).toBeInTheDocument()

      // Click Delete — fireEvent is wrapped in act, sync state flushes
      fireEvent.click(screen.getByText('Delete'))
      // Confirm overlay should be visible (buttons confirm this)
      expect(screen.getByText('Yes, delete')).toBeInTheDocument()
      expect(screen.getByText('Cancel')).toBeInTheDocument()

      // Click Yes, delete — triggers async handleConfirmDelete
      fireEvent.click(screen.getByText('Yes, delete'))
      // Sync part of the handler flushes: we're now in deleting state
      expect(screen.getByText('Deleting...')).toBeInTheDocument()

      // Resolve the delete promise
      await act(async () => {
        resolveDel({ ok: true })
      })

      // "Deleted!" feedback should appear immediately after promise resolves
      expect(screen.getByText('Deleted!')).toBeInTheDocument()

      // Advance timer by 1.2s to trigger card removal
      act(() => {
        vi.advanceTimersByTime(1200)
      })

      // Card should be removed
      expect(screen.queryByText('Dungeon of Doom')).not.toBeInTheDocument()
      vi.useRealTimers()
    })

    it('cancel restores the card to idle state', async () => {
      const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
      renderModal()

      await act(async () => {
        resolveList(SINGLE_SAVE)
      })
      await waitFor(() => {
        expect(screen.getByText('Delete')).toBeInTheDocument()
      })

      // Enter confirm state
      fireEvent.click(screen.getByText('Delete'))
      await waitFor(() => {
        // Confirm overlay uses &lsquo;/&rsquo; curly quotes; verify via buttons
        expect(screen.getByText('Yes, delete')).toBeInTheDocument()
        expect(screen.getByText('Cancel')).toBeInTheDocument()
      })

      // Cancel
      fireEvent.click(screen.getByText('Cancel'))

      // Should be back to idle with Load and Delete buttons
      await waitFor(() => {
        expect(screen.getByText('Load')).toBeInTheDocument()
        expect(screen.getByText('Delete')).toBeInTheDocument()
      })
      // Confirm overlay should be gone (buttons no longer visible)
      expect(screen.queryByText('Yes, delete')).not.toBeInTheDocument()
      expect(screen.queryByText('Cancel')).not.toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Fetch Error
  // ---------------------------------------------------------------

  describe('fetch error', () => {
    it('shows "Failed to load saves." when listSaves returns ok:false', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      renderModal()

      await act(async () => {
        resolve({ ok: false, saves: [] })
      })

      await waitFor(() => {
        expect(screen.getByText('Failed to load saves.')).toBeInTheDocument()
      })
    })

    it('shows "Failed to load saves." when listSaves throws', async () => {
      const { promise, reject } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      renderModal()

      await act(async () => {
        reject(new Error('Network error'))
      })

      await waitFor(() => {
        expect(screen.getByText('Failed to load saves.')).toBeInTheDocument()
      })
    })

    it('Try Again button re-fetches the save list', async () => {
      let callCount = 0
      const firstDef = deferred<SavesListResponse>()
      const secondDef = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockImplementation(() => {
        callCount++
        return callCount === 1 ? firstDef.promise : secondDef.promise
      })
      renderModal()

      // First call: fail
      await act(async () => {
        firstDef.resolve({ ok: false, saves: [] })
      })
      await waitFor(() => {
        expect(screen.getByText('Failed to load saves.')).toBeInTheDocument()
      })

      // Click Try Again
      fireEvent.click(screen.getByText('Try Again'))

      // Should show loading state again
      expect(screen.getByText('Loading saves...')).toBeInTheDocument()

      // Second call: succeed
      await act(async () => {
        secondDef.resolve(SINGLE_SAVE)
      })
      await waitFor(() => {
        expect(screen.getByText('Dungeon of Doom')).toBeInTheDocument()
      })
      // Error should be gone
      expect(screen.queryByText('Failed to load saves.')).not.toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Dismiss
  // ---------------------------------------------------------------

  describe('dismiss', () => {
    it('calls onClose when Escape key is pressed (not during active load/delete)', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      const onClose = vi.fn()
      renderModal({ onClose })

      await act(async () => {
        resolve(EMPTY_LIST)
      })
      await waitFor(() => {
        expect(screen.getByText('No saved games found.')).toBeInTheDocument()
      })

      fireEvent.keyDown(document, { key: 'Escape' })
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when the overlay is clicked (not during active load/delete)', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      const onClose = vi.fn()
      renderModal({ onClose })

      await act(async () => {
        resolve(EMPTY_LIST)
      })
      await waitFor(() => {
        expect(screen.getByText('No saved games found.')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('dialog'))
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when the ✕ close button is clicked', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      const onClose = vi.fn()
      renderModal({ onClose })

      await act(async () => {
        resolve(EMPTY_LIST)
      })
      await waitFor(() => {
        expect(screen.getByText('No saved games found.')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByLabelText('Close load dialog'))
      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  // ---------------------------------------------------------------
  // Edge Cases
  // ---------------------------------------------------------------

  describe('edge cases', () => {
    it('re-fetches fresh data when the modal is re-opened', async () => {
      let callCount = 0
      const firstDef = deferred<SavesListResponse>()
      const secondDef = deferred<SavesListResponse>()
      const mockList = vi.spyOn(endpoints, 'listSaves').mockImplementation(() => {
        callCount++
        return callCount === 1 ? firstDef.promise : secondDef.promise
      })

      const onClose = vi.fn()
      const onLoaded = vi.fn()
      const { rerender } = render(
        <LoadGameModal isOpen={true} onClose={onClose} onLoaded={onLoaded} />,
      )

      // First fetch resolves with save-1
      await act(async () => {
        firstDef.resolve({ ok: true, saves: [SAVES_LIST.saves[0]] })
      })
      await waitFor(() => {
        expect(screen.getByText('Dungeon of Doom')).toBeInTheDocument()
      })

      // Close modal
      rerender(<LoadGameModal isOpen={false} onClose={onClose} onLoaded={onLoaded} />)

      // Re-open
      rerender(<LoadGameModal isOpen={true} onClose={onClose} onLoaded={onLoaded} />)

      // Should be loading again
      expect(screen.getByText('Loading saves...')).toBeInTheDocument()

      // Second fetch resolves with save-2
      await act(async () => {
        secondDef.resolve({ ok: true, saves: [SAVES_LIST.saves[1]] })
      })
      await waitFor(() => {
        expect(screen.getByText('Forest Retreat')).toBeInTheDocument()
      })
      // Old data should not be visible
      expect(screen.queryByText('Dungeon of Doom')).not.toBeInTheDocument()
      // listSaves should have been called twice
      expect(mockList).toHaveBeenCalledTimes(2)
    })

    it('handles missing optional fields on SaveMeta without crashing', async () => {
      const { promise, resolve } = deferred<SavesListResponse>()
      vi.spyOn(endpoints, 'listSaves').mockReturnValue(promise)
      renderModal()

      const minimalSave: SavesListResponse = {
        ok: true,
        saves: [
          {
            id: 'minimal-1',
            name: 'Bare Bones',
            // no character_name, no turn_count — only required fields
            timestamp: '2026-06-03T08:00:00Z',
          },
        ],
      }

      await act(async () => {
        resolve(minimalSave)
      })

      await waitFor(() => {
        expect(screen.getByText('Bare Bones')).toBeInTheDocument()
      })
      // No character_name — character span should not exist
      expect(screen.queryByText('Thorn')).not.toBeInTheDocument()
      // No turn_count — should not render "Turn N"
      expect(screen.queryByText(/Turn/)).not.toBeInTheDocument()
      // Timestamp should still render
      expect(screen.getByText(/2026/)).toBeInTheDocument()
      // Load and Delete buttons should still be present
      expect(screen.getByText('Load')).toBeInTheDocument()
      expect(screen.getByText('Delete')).toBeInTheDocument()
    })
  })
})
