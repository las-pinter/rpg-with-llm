/**
 * GamePage tests — full game layout with stores, hooks, and modals.
 *
 * Acceptance criteria:
 * 1. Renders empty state when no character exists
 * 2. Renders game components when character exists
 * 3. Opens Save modal when save button clicked
 * 4. Opens Load modal when load button clicked
 * 5. Opens Story modal when story button clicked
 * 6. Opens Character Details modal when triggered
 * 7. Submits a turn via onSubmit
 * 8. Shows connecting indicator when isConnecting
 * 9. Handles game start on mount
 * 10. Error banner displays when there's a stream error
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { useGameStore } from '../stores/gameStore'
import { useCharacterStore } from '../stores/characterStore'
import * as endpoints from '../api/endpoints'
import type { Character } from '../api/types'
import type { SavesListResponse, LoadResponse } from '../api/types'
import GamePage from './GamePage'

// ---------------------------------------------------------------------------
// Mocks — use vi.hoisted() for mutable references so tests can change values
// ---------------------------------------------------------------------------

const mockConnect = vi.fn()
const mockDisconnect = vi.fn()

/** Mutable hook state — tests can flip these to change what useGameStream returns. */
const mockHookState = vi.hoisted(() => ({
  isConnecting: false,
  error: null as string | null,
}))

vi.mock('../hooks/useGameStream', async () => {
  const { useEffect } = await vi.importActual<typeof import('react')>('react')
  return {
    useGameStream: () => {
      // Replicate the real hook's cleanup-on-unmount behavior
      useEffect(() => () => { mockDisconnect() }, [])
      return {
        connect: mockConnect,
        disconnect: mockDisconnect,
        isConnecting: mockHookState.isConnecting,
        error: mockHookState.error,
      }
    },
  }
})

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const sampleCharacter: Character = {
  id: 'test-char-1',
  name: 'Baldric the Brave',
  character_class: 'Fighter',
  level: 1,
  abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
  hp: 12,
  max_hp: 12,
  ac: 18,
  skills: ['Athletics', 'Intimidation'],
  backstory: 'A brave warrior from the northern reaches.',
  appearance: 'Tall and broad-shouldered with a weathered cloak.',
  personality: 'Courageous and loyal to a fault.',
  hooks: ['Searching for a lost family heirloom'],
  inventory: ['Longsword', 'Shield', 'Rations'],
  gold: 15,
  xp: 0,
  created_at: '2026-01-01T00:00:00Z',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/game']}>
      <GamePage />
    </MemoryRouter>,
  )
}

/** Create a deferred promise with manually-typed resolve/reject. */
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

function resetStores() {
  useGameStore.getState().reset()
  useCharacterStore.getState().reset()
}

/** Sample save data for load game flow tests. */
const sampleSaveList: SavesListResponse = {
  ok: true,
  saves: [
    {
      id: 'save-test-1',
      name: 'Test Save',
      timestamp: '2026-06-01T14:30:00Z',
      character_name: 'Baldric the Brave',
      turn_count: 5,
    },
  ],
}

beforeEach(() => {
  resetStores()
  mockConnect.mockClear()
  mockDisconnect.mockClear()
  mockNavigate.mockClear()
  mockHookState.isConnecting = false
  mockHookState.error = null
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Empty State (no character)
// ---------------------------------------------------------------------------

describe('GamePage — empty state', () => {
  it('renders empty state when no character exists', () => {
    renderPage()
    expect(screen.getByText(/no character found/i)).toBeInTheDocument()
    expect(screen.getByText(/create a character first/i)).toBeInTheDocument()
  })

  it('renders a button to navigate to character page', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /create character/i }),
    ).toBeInTheDocument()
  })

  it('navigates to /character when Create Character is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /create character/i }))

    expect(mockNavigate).toHaveBeenCalledWith('/character')
  })

  it('does not connect to game stream when there is no character', () => {
    renderPage()
    expect(mockConnect).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Game Start Flow
// ---------------------------------------------------------------------------

describe('GamePage — game start', () => {
  it('calls connect on mount when character exists and game not active', () => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    renderPage()

    expect(mockConnect).toHaveBeenCalledTimes(1)
    expect(mockConnect).toHaveBeenCalledWith(
      expect.objectContaining({ input: 'start' }),
    )
  })

  it('does not set isActive optimistically — waits for stream confirmation', () => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    renderPage()

    // isActive should remain false because GamePage no longer sets it
    // optimistically before connect resolves. Only a state_update event
    // (via useGameStream) should set isActive=true.
    expect(useGameStore.getState().isActive).toBe(false)
  })

  it('does not connect when character exists and game is already active', () => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
    renderPage()

    expect(mockConnect).not.toHaveBeenCalled()
  })

  it('passes character data in the connect call', () => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    renderPage()

    expect(mockConnect).toHaveBeenCalledWith(
      expect.objectContaining({
        input: 'start',
        character: expect.objectContaining({ name: 'Baldric the Brave' }),
      }),
    )
  })
})

// ---------------------------------------------------------------------------
// Connecting State
// ---------------------------------------------------------------------------

describe('GamePage — connecting state', () => {
  it('shows connecting indicator when isConnecting is true', () => {
    mockHookState.isConnecting = true
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    renderPage()

    expect(screen.getByText(/entering the realm/i)).toBeInTheDocument()
    expect(
      screen.getByText(/the dungeon master is weaving your tale/i),
    ).toBeInTheDocument()
  })

  it('does not show game layout while connecting', () => {
    mockHookState.isConnecting = true
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    renderPage()

    expect(screen.queryByText(/adventure log/i)).not.toBeInTheDocument()
    expect(
      screen.queryByPlaceholderText(/what do you do/i),
    ).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Game Layout Render
// ---------------------------------------------------------------------------

describe('GamePage — game layout', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('renders the Adventure Log heading', () => {
    renderPage()
    expect(screen.getByText(/adventure log/i)).toBeInTheDocument()
  })

  it('renders the Story button', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /view adventure story/i }),
    ).toBeInTheDocument()
  })

  it('renders the Character button', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /view character details/i }),
    ).toBeInTheDocument()
  })

  it('renders NarrativeStream area', () => {
    renderPage()
    expect(screen.getByText(/the adventure awaits/i)).toBeInTheDocument()
  })

  it('renders the input area', () => {
    renderPage()
    expect(
      screen.getByPlaceholderText(/what do you do/i),
    ).toBeInTheDocument()
  })

  it('renders quick action chips', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /look around/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /check inventory/i }),
    ).toBeInTheDocument()
  })

  it('renders Save Game button', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /save game/i }),
    ).toBeInTheDocument()
  })

  it('renders Load Game button', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /load game/i }),
    ).toBeInTheDocument()
  })

  it('renders New Game button', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /new game/i }),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Modal Interactions
// ---------------------------------------------------------------------------

describe('GamePage — save modal', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('opens the Save modal when Save Game is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /save game/i }))

    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: /save game/i }),
      ).toBeInTheDocument()
    })
  })

  it('closes Save modal when close button is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /save game/i }))
    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: /save game/i }),
      ).toBeInTheDocument()
    })

    const closeBtn = screen.getByRole('button', { name: /close save dialog/i })
    await user.click(closeBtn)

    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: /save game/i }),
      ).not.toBeInTheDocument()
    })
  })
})

describe('GamePage — load modal', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('opens the Load modal when Load Game is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /load game/i }))

    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: /load game/i }),
      ).toBeInTheDocument()
    })
  })

  it('closes Load modal when close button is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /load game/i }))
    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: /load game/i }),
      ).toBeInTheDocument()
    })

    const btn = screen.getByRole('button', { name: /close load dialog/i })
    await user.click(btn)

    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: /load game/i }),
      ).not.toBeInTheDocument()
    })
  })
})

describe('GamePage — story modal', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('opens the Story modal when Story button is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /view adventure story/i }),
    )

    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: /adventure story/i }),
      ).toBeInTheDocument()
    })
  })
})

describe('GamePage — character details modal', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('opens Character Details modal when Character button is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /view character details/i }),
    )

    // Modal uses aria-labelledby pointing to the character name heading
    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: /baldric the brave/i }),
      ).toBeInTheDocument()
    })
  })

  it('shows character name in the details modal', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /view character details/i }),
    )

    await waitFor(() => {
      expect(screen.getByText(/baldric the brave/i)).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------

describe('GamePage — submit', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('calls connect when user submits an action', async () => {
    const user = userEvent.setup()
    renderPage()

    const input = screen.getByPlaceholderText(/what do you do/i)
    await user.type(input, 'Look around the room')
    await user.click(screen.getByRole('button', { name: /submit action/i }))

    await waitFor(() => {
      expect(mockConnect).toHaveBeenCalledWith(
        expect.objectContaining({
          input: 'Look around the room',
        }),
      )
    })
  })

  it('sets processing to true when submitting', async () => {
    const user = userEvent.setup()
    renderPage()

    const input = screen.getByPlaceholderText(/what do you do/i)
    await user.type(input, 'Open the chest')
    await user.click(screen.getByRole('button', { name: /submit action/i }))

    await waitFor(() => {
      expect(useGameStore.getState().processing).toBe(true)
    })
  })

  it('sets isThinking to true when submitting', async () => {
    const user = userEvent.setup()
    renderPage()

    const input = screen.getByPlaceholderText(/what do you do/i)
    await user.type(input, 'Search for traps')
    await user.click(screen.getByRole('button', { name: /submit action/i }))

    await waitFor(() => {
      expect(useGameStore.getState().isThinking).toBe(true)
    })
  })

  it('clears input after submission', async () => {
    const user = userEvent.setup()
    renderPage()

    const input = screen.getByPlaceholderText(
      /what do you do/i,
    ) as HTMLInputElement
    await user.type(input, 'Look around')
    await user.click(screen.getByRole('button', { name: /submit action/i }))

    await waitFor(() => {
      expect(input.value).toBe('')
    })
  })
})

// ---------------------------------------------------------------------------
// Double-submit guard
// ---------------------------------------------------------------------------

describe('GamePage — double-submit guard', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    mockConnect.mockClear()
  })

  it('disables the Act button when processing is true (prevents double-submit)', async () => {
    const user = userEvent.setup()
    // isActive starts false, so auto-start fires connect() on mount
    useGameStore.getState().setIsActive(false)
    renderPage()

    // Auto-start effect fires connect() with input: 'start'
    await waitFor(() => {
      expect(mockConnect).toHaveBeenCalledTimes(1)
    })

    // Now mark the game as active and set processing=true
    useGameStore.getState().setIsActive(true)
    useGameStore.getState().setProcessing(true)

    const input = screen.getByPlaceholderText(/what do you do/i)
    await user.type(input, 'Second action')

    // The submit button should be disabled while processing
    expect(
      screen.getByRole('button', { name: /submit action/i }),
    ).toBeDisabled()

    // mockConnect should still be 1 (from mount) — processing blocked the submit
    expect(mockConnect).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// Error recovery
// ---------------------------------------------------------------------------

describe('GamePage — error recovery', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
    useGameStore.getState().setError('A terrible error occurred')
    mockConnect.mockClear()
  })

  it('displays error banner and persists on new submit until SSE clears it', async () => {
    const user = userEvent.setup()
    renderPage()

    // Error banner should be visible (set before render)
    expect(screen.getByRole('alert')).toHaveTextContent(
      /a terrible error occurred/i,
    )

    // Submit a new action — the error banner persists until the SSE stream
    // returns a 'done' or 'error' event that clears it
    const input = screen.getByPlaceholderText(/what do you do/i) as HTMLInputElement
    await user.type(input, 'Try again')
    await user.click(screen.getByRole('button', { name: /submit action/i }))

    // The error banner should still be visible (cleared by SSE events, not by submit)
    expect(screen.getByRole('alert')).toBeInTheDocument()

    // Connect was called with the new input
    expect(mockConnect).toHaveBeenCalledWith(
      expect.objectContaining({ input: 'Try again' }),
    )
  })
})

// ---------------------------------------------------------------------------
// Modal close edge cases
// ---------------------------------------------------------------------------

describe('GamePage — modal close edge cases', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('closes Story modal via overlay click', async () => {
    const user = userEvent.setup()
    renderPage()

    // Open the Story modal
    await user.click(
      screen.getByRole('button', { name: /view adventure story/i }),
    )
    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: /adventure story/i }),
      ).toBeInTheDocument()
    })

    // Close by pressing Escape
    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: /adventure story/i }),
      ).not.toBeInTheDocument()
    })
  })

  it('closes Character Details modal via Escape', async () => {
    const user = userEvent.setup()
    renderPage()

    // Open the Character Details modal
    await user.click(
      screen.getByRole('button', { name: /view character details/i }),
    )
    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: /baldric the brave/i }),
      ).toBeInTheDocument()
    })

    // Close by pressing Escape
    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: /baldric the brave/i }),
      ).not.toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// New Game Navigation
// ---------------------------------------------------------------------------

describe('GamePage — new game', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('navigates to /character when New Game is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /new game/i }))

    expect(mockNavigate).toHaveBeenCalledWith('/character')
  })

  it('calls disconnect when New Game is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /new game/i }))

    expect(mockDisconnect).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// Load Game Flow (handleLoaded)
// ---------------------------------------------------------------------------

describe('GamePage — load game flow', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('does not auto-connect when a save is loaded (waits for player input)', async () => {
    const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
    const { promise: loadPromise, resolve: resolveLoad } = deferred<LoadResponse>()
    vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
    vi.spyOn(endpoints, 'loadGame').mockReturnValue(loadPromise)
    renderPage()

    // Open the load modal
    await userEvent.click(screen.getByRole('button', { name: /load game/i }))
    await act(async () => {
      resolveList(sampleSaveList)
    })
    await waitFor(() => {
      expect(screen.getByText('Load')).toBeInTheDocument()
    })

    // Click the Load button on the save card
    await userEvent.click(screen.getByText('Load'))
    await act(async () => {
      resolveLoad({
        ok: true,
        state: { location: 'Dungeon', hp: 50 },
        character: { name: 'Baldric the Brave', class: 'Fighter' },
      })
    })

    // Game should show the loaded state but NOT auto-submit a turn
    await waitFor(() => {
      expect(useGameStore.getState().isActive).toBe(true)
    })
    expect(mockConnect).not.toHaveBeenCalled()
  })

  it('sets isActive to true when a save is loaded', async () => {
    const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
    const { promise: loadPromise, resolve: resolveLoad } = deferred<LoadResponse>()
    vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
    vi.spyOn(endpoints, 'loadGame').mockReturnValue(loadPromise)
    renderPage()

    // Open the load modal
    await userEvent.click(screen.getByRole('button', { name: /load game/i }))
    await act(async () => {
      resolveList(sampleSaveList)
    })
    await waitFor(() => {
      expect(screen.getByText('Load')).toBeInTheDocument()
    })

    // Click Load
    await userEvent.click(screen.getByText('Load'))
    await act(async () => {
      resolveLoad({
        ok: true,
        state: { location: 'Dungeon', hp: 50 },
      })
    })

    await waitFor(() => {
      expect(useGameStore.getState().isActive).toBe(true)
    })
  })

  it('sets worldState in game store when a save is loaded', async () => {
    const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
    const { promise: loadPromise, resolve: resolveLoad } = deferred<LoadResponse>()
    vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
    vi.spyOn(endpoints, 'loadGame').mockReturnValue(loadPromise)
    renderPage()

    // Open the load modal
    await userEvent.click(screen.getByRole('button', { name: /load game/i }))
    await act(async () => {
      resolveList(sampleSaveList)
    })
    await waitFor(() => {
      expect(screen.getByText('Load')).toBeInTheDocument()
    })

    // Click Load
    await userEvent.click(screen.getByText('Load'))
    await act(async () => {
      resolveLoad({
        ok: true,
        state: { location: 'Dungeon', hp: 50 },
      })
    })

    await waitFor(() => {
      expect(useGameStore.getState().worldState).toEqual({
        location: 'Dungeon',
        hp: 50,
      })
    })
  })

  it('sets character in store when a save with character is loaded', async () => {
    const { promise: listPromise, resolve: resolveList } = deferred<SavesListResponse>()
    const { promise: loadPromise, resolve: resolveLoad } = deferred<LoadResponse>()
    vi.spyOn(endpoints, 'listSaves').mockReturnValue(listPromise)
    vi.spyOn(endpoints, 'loadGame').mockReturnValue(loadPromise)
    renderPage()

    // Open the load modal
    await userEvent.click(screen.getByRole('button', { name: /load game/i }))
    await act(async () => {
      resolveList(sampleSaveList)
    })
    await waitFor(() => {
      expect(screen.getByText('Load')).toBeInTheDocument()
    })

    // Click Load
    await userEvent.click(screen.getByText('Load'))
    await act(async () => {
      resolveLoad({
        ok: true,
        state: { location: 'Dungeon', hp: 50 },
        character: { name: 'Thorn', class: 'Rogue' },
      })
    })

    await waitFor(() => {
      const char = useCharacterStore.getState().currentCharacter
      expect(char).not.toBeNull()
      expect(char!.name).toBe('Thorn')
    })
  })
})

// ---------------------------------------------------------------------------
// Unmount Cleanup
// ---------------------------------------------------------------------------

describe('GamePage — unmount cleanup', () => {
  it('calls disconnect when GamePage unmounts', () => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
    const { unmount } = renderPage()

    unmount()

    expect(mockDisconnect).toHaveBeenCalledTimes(1)
  })

  it('calls disconnect on unmount even when auto-connecting', () => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    // isActive is false so auto-start effect fires connect()
    const { unmount } = renderPage()

    unmount()

    // disconnect should be called (from the cleanup and potentially from connect's internal flow)
    expect(mockDisconnect).toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Error State
// ---------------------------------------------------------------------------

describe('GamePage — error state', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('displays error banner when store has an error', () => {
    useGameStore.getState().setError('Something went wrong in the realm')
    renderPage()

    expect(
      screen.getByText(/something went wrong in the realm/i),
    ).toBeInTheDocument()
  })

  it('shows error banner with alert role', () => {
    useGameStore.getState().setError('Connection to the ether failed')
    renderPage()

    expect(screen.getByRole('alert')).toHaveTextContent(
      /connection to the ether failed/i,
    )
  })

  it('shows error banner when stream error is set', () => {
    mockHookState.error = 'Stream connection failed'
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
    renderPage()

    expect(screen.getByText(/stream connection failed/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe('GamePage — accessibility', () => {
  beforeEach(() => {
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)
  })

  it('has alert role on error banner', () => {
    useGameStore.getState().setError('A terrible error occurred')
    renderPage()

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('has aria-label on input area region', () => {
    renderPage()
    expect(screen.getByLabelText(/game input area/i)).toBeInTheDocument()
  })

  it('has proper heading hierarchy', () => {
    renderPage()
    const heading = screen.getByRole('heading', { name: /adventure log/i })
    expect(heading).toBeInTheDocument()
    expect(heading.tagName).toBe('H2')
  })
})
