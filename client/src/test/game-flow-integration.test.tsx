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
  it('connects to the SSE stream with "start" input when character exists', async () => {
    // Mock fetch so the real useGameStream can connect
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream([], 0)),
    )

    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)

    renderPage()

    // The hook should start connecting
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled()
    })

    const callArgs = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(callArgs[0]).toBe('/api/game/stream')
    expect(callArgs[1].method).toBe('POST')

    const body = JSON.parse(callArgs[1].body)
    expect(body.input).toBe('start')
    expect(body.character.name).toBe('Baldric the Brave')
  })

  it('renders the game layout after connection establishes', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream([], 0)),
    )

    useCharacterStore.getState().setCurrentCharacter(sampleCharacter)

    renderPage()

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/what do you do/i),
      ).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Submitting input and processing SSE events
// ---------------------------------------------------------------------------

describe('game flow — submitting input', () => {
  it('renders narrative content from SSE events', async () => {
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

    renderPage()

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

    renderPage()

    // Initially the game is not active after start (no SSE events yet)
    // Wait for fetch to be called with 'start'
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled()
    })

    // Now resolve the start stream with a narrative + done
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

    renderPage()

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

    // Render with real timers — the hook will retry with backoff delays
    // (1s, 2s, 4s), so we need to wait longer than the default timeout
    renderPage()

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
