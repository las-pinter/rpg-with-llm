/**
 * Game Flow Integration — tests the complete game flow through GamePage
 * with the REAL useGameStream hook and stores, mocking only the fetch layer.
 *
 * This is the HIGHEST-INTEGRATION test: the real hook, real stores,
 * real React rendering. Only the network layer (fetch) is mocked.
 *
 * Covers: starting a new game, submitting input, SSE events rendering
 * narrative, game over / error recovery, and loading a saved game.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { useGameStore } from '../stores/gameStore'
import { useCharacterStore } from '../stores/characterStore'
import * as endpoints from '../api/endpoints'
import type { Character } from '../api/types'
import { ItemType } from '../api/types'
import type { SavesListResponse, LoadResponse } from '../api/types'
import GamePage from '../pages/GamePage'

// ---------------------------------------------------------------------------
// Mock — only mock react-router-dom and API endpoints, NOT useGameStream
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// ---------------------------------------------------------------------------
// SSE Stream helpers
// ---------------------------------------------------------------------------

/** Create a ReadableStream that emits SSE-formatted events after a delay. */
function mockSSEStream(
  events: Array<{ event: string; data: string }>,
  delay: number = 5,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  const sseText =
    events
      .map((e) => `event: ${e.event}\ndata: ${e.data}`)
      .join('\n\n') + '\n\n'
  return new ReadableStream({
    start(controller) {
      setTimeout(() => {
        try {
          controller.enqueue(encoder.encode(sseText))
          controller.close()
        } catch {
          // Stream may have been cancelled — ignore
        }
      }, delay)
    },
  })
}

function mockFetchResponse(
  stream: ReadableStream<Uint8Array> | null,
  ok: boolean = true,
  status: number = 200,
) {
  return { ok, status, body: stream }
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

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const sampleCharacter: Character = {
  id: 'test-char-1',
  name: 'Baldric the Brave',
  character_class: 'Fighter',
  level: 1,
  abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
  skills: ['Athletics', 'Intimidation'],
  backstory: 'A brave warrior from the northern reaches.',
  appearance: 'Tall and broad-shouldered with a weathered cloak.',
  personality: 'Courageous and loyal to a fault.',
  hooks: ['Searching for a lost family heirloom'],
  inventory: [
    { id: 'item-1', name: 'Longsword', quantity: 1, item_type: ItemType.WEAPON, properties: {}, description: '', weight: 3, value: 15 },
    { id: 'item-2', name: 'Shield', quantity: 1, item_type: ItemType.ARMOR, properties: {}, description: '', weight: 6, value: 10 },
    { id: 'item-3', name: 'Rations', quantity: 3, item_type: ItemType.CONSUMABLE, properties: {}, description: '', weight: 2, value: 5 },
  ],
  equipped_items: [],
  resources: { hp: { value: 12, max: 12, short_rest_recovery: '1d10', long_rest_recovery: 'full' } },
  gold: 15,
  xp: 0,
  created_at: '2026-01-01T00:00:00Z',
}

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

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/game']}>
      <GamePage />
    </MemoryRouter>,
  )
}

function resetStores() {
  useGameStore.getState().reset()
  useCharacterStore.getState().reset()
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  resetStores()
  mockNavigate.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Starting a new game
// ---------------------------------------------------------------------------

describe('game flow — starting a new game', () => {
  it('auto-connects with start input on mount when no active game', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream([], 0)),
    )

    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)

    renderPage()

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/game/stream',
        expect.objectContaining({
          body: expect.stringContaining('"input":"start"'),
        }),
      )
    })
  })

  it('shows connecting overlay on mount when no active game', async () => {
    const { promise } = deferred<Response>()
    global.fetch = vi.fn().mockReturnValue(promise)

    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)

    renderPage()

    // Auto-start fires — connecting overlay shows while waiting for backend
    await waitFor(() => {
      expect(screen.getByText('Entering the Realm…')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Submitting input and processing SSE events
// ---------------------------------------------------------------------------

describe('game flow — submitting input', () => {
  it('renders narrative content from SSE events after user submit', async () => {
    const events = [
      {
        event: 'narrative',
        data: JSON.stringify({ content: 'A dark cave looms before you.' }),
      },
      { event: 'done', data: JSON.stringify({}) },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 20)),
    )

    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    // Game must be active for the input to be enabled
    useGameStore.getState().setIsActive(true)

    const user = userEvent.setup()
    renderPage()

    // Submit a turn to trigger the SSE connection
    const input = screen.getByPlaceholderText(/what do you do/i)
    await user.type(input, 'Look around')
    await user.click(screen.getByRole('button', { name: /submit action/i }))

    // Wait for the narrative content to appear in the DOM via NarrativeStream
    await waitFor(() => {
      expect(
        screen.getByText('A dark cave looms before you.'),
      ).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it('submits a turn and processes the SSE stream', async () => {
    // Use a deferred fetch so we can control when the connection resolves
    let resolveFetch!: (value: unknown) => void
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve
    })

    global.fetch = vi.fn().mockReturnValue(fetchPromise)

    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    // Game must be active for the input to be enabled
    useGameStore.getState().setIsActive(true)

    const user = userEvent.setup()
    renderPage()

    // Submit a turn to trigger the SSE connection
    const input = screen.getByPlaceholderText(/what do you do/i)
    await user.type(input, 'Explore the cave')
    await user.click(screen.getByRole('button', { name: /submit action/i }))

    // Wait for fetch to be called (from the user submit)
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled()
    })

    // Now resolve the stream with a narrative + done
    const startEvents = [
      {
        event: 'narrative',
        data: JSON.stringify({ content: 'Welcome, adventurer!' }),
      },
      { event: 'done', data: JSON.stringify({}) },
    ]
    resolveFetch(mockFetchResponse(mockSSEStream(startEvents, 10)))

    // Wait for the narrative content
    await waitFor(() => {
      expect(
        screen.getByText('Welcome, adventurer!'),
      ).toBeInTheDocument()
    }, { timeout: 5000 })
  })
})

// ---------------------------------------------------------------------------
// Error recovery
// ---------------------------------------------------------------------------

describe('game flow — error recovery', () => {
  it('shows error banner when server returns an error event', async () => {
    const events = [
      {
        event: 'error',
        data: JSON.stringify({ message: 'Server error: DM unavailable' }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    // Game must be active for the input to be enabled
    useGameStore.getState().setIsActive(true)

    const user = userEvent.setup()
    renderPage()

    // Submit a turn — the SSE stream will return an error event
    const input = screen.getByPlaceholderText(/what do you do/i)
    await user.type(input, 'Enter the darkness')
    await user.click(screen.getByRole('button', { name: /submit action/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/server error: dm unavailable/i),
      ).toBeInTheDocument()
    })
  })

  it('handles HTTP error responses gracefully', { timeout: 20000 }, async () => {
    // Return 503 for ALL fetch attempts so the retry loop exhausts
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      body: null,
    })

    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    // Game must be active for the input to be enabled
    useGameStore.getState().setIsActive(true)

    const user = userEvent.setup()

    // Render with real timers — the hook will retry with backoff delays
    // (1s, 2s, 4s), so we need to wait longer than the default timeout
    renderPage()

    // Submit a turn — the fetch will return a 503 error
    const input = screen.getByPlaceholderText(/what do you do/i)
    await user.type(input, 'Test the connection')
    await user.click(screen.getByRole('button', { name: /submit action/i }))

    await waitFor(() => {
      expect(screen.getByText(/HTTP 503/i)).toBeInTheDocument()
    }, { timeout: 15000 })
  })
})

// ---------------------------------------------------------------------------
// Loading a saved game
// ---------------------------------------------------------------------------

describe('game flow — loading a saved game', () => {
  it('loads a saved game and restores world state', async () => {
    // Set isActive=true so the mount auto-connect does NOT fire
    // (the load flow will handle connecting)
    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)
    useGameStore.getState().setIsActive(true)

    renderPage()

    // Game layout should render immediately (no connect on mount)
    expect(
      screen.getByPlaceholderText(/what do you do/i),
    ).toBeInTheDocument()

    // Setup deferred promises for the load modal flow
    const listDef = deferred<SavesListResponse>()
    const loadDef = deferred<LoadResponse>()
    vi.spyOn(endpoints, 'listSaves').mockReturnValue(listDef.promise)
    vi.spyOn(endpoints, 'loadGame').mockReturnValue(loadDef.promise)

    const user = userEvent.setup()

    // Open Load modal
    await user.click(screen.getByRole('button', { name: /load game/i }))
    await act(async () => {
      listDef.resolve(sampleSaveList)
    })
    await waitFor(() => {
      expect(screen.getByText('Test Save')).toBeInTheDocument()
    })

    // Click Load
    await user.click(screen.getByText('Load'))
    await act(async () => {
      loadDef.resolve({
        ok: true,
        state: { location: 'Dungeon', hp: 50, gold: 100 },
        character: { name: 'Baldric', class: 'Fighter' },
      })
    })

    // Verify world state is restored
    await waitFor(() => {
      expect(useGameStore.getState().worldState).toEqual({
        location: 'Dungeon',
        hp: 50,
        gold: 100,
      })
    })
  })
})
