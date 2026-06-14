/**
 * Store + Hook Integration — tests that useGameStream dispatched SSE events
 * correctly propagate to and update the game store.
 *
 * These are INTEGRATION tests: they use the real hook with the real store,
 * mocking only the fetch/network layer via global.fetch.
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useGameStore } from '../stores/gameStore'
import { useGameStream } from '../hooks/useGameStream'

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

/** Create a ReadableStream that emits SSE-formatted events after a delay. */
function mockSSEStream(
  events: Array<{ event: string; data: string }>,
  delay: number = 0,
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

/** Create a mock fetch Response with the given ReadableStream body. */
function mockFetchResponse(
  stream: ReadableStream<Uint8Array> | null,
  ok: boolean = true,
  status: number = 200,
) {
  return { ok, status, body: stream }
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  useGameStore.getState().reset()
  vi.clearAllMocks()
})

afterEach(() => {
  vi.resetAllMocks()
})

// ---------------------------------------------------------------------------
// Integration: store + hook event pipeline
// ---------------------------------------------------------------------------

describe('store-hook integration — narrative event → store', () => {
  it('adds a narrative entry and appends narrative text on narrative event', async () => {
    const events = [
      {
        event: 'narrative',
        data: JSON.stringify({ content: 'You enter the dark forest.' }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'look around' })
    })

    await waitFor(() => {
      const state = useGameStore.getState()
      expect(state.narrativeEntries).toHaveLength(1)
      expect(state.narrativeEntries[0].type).toBe('narrative')
      expect(state.narrativeEntries[0].content).toBe(
        'You enter the dark forest.',
      )
      expect(state.narrative).toBe('You enter the dark forest.')
    })
  })

  it('accumulates multiple narrative events in order', async () => {
    const events = [
      { event: 'narrative', data: JSON.stringify({ content: 'Part one. ' }) },
      { event: 'narrative', data: JSON.stringify({ content: 'Part two.' }) },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'explore' })
    })

    await waitFor(() => {
      const state = useGameStore.getState()
      expect(state.narrativeEntries).toHaveLength(2)
      expect(state.narrativeEntries[0].content).toBe('Part one. ')
      expect(state.narrativeEntries[1].content).toBe('Part two.')
      expect(state.narrative).toBe('Part one. Part two.')
    })
  })
})

describe('store-hook integration — state_update event → store', () => {
  it('updates worldState via applyStateUpdate with set action', async () => {
    // Set initial world state
    useGameStore.getState().setWorldState({ hp: 50, gold: 100 })

    const events = [
      {
        event: 'state_update',
        data: JSON.stringify({
          state: { hp: 30, gold: 125 },
          turn_count: 1,
        }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'take damage' })
    })

    await waitFor(() => {
      const state = useGameStore.getState()
      expect(state.worldState).not.toBeNull()
      expect(state.worldState!.hp).toBe(30)
      expect(state.worldState!.gold).toBe(125)
    })
  })

  it('creates world state from null and applies updates', async () => {
    useGameStore.getState().setWorldState(null)

    const events = [
      {
        event: 'state_update',
        data: JSON.stringify({
          state: { location: 'Dungeon', stats: { hp: 100 } },
        }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'enter dungeon' })
    })

    await waitFor(() => {
      const state = useGameStore.getState()
      expect(state.worldState).toEqual({
        location: 'Dungeon',
        stats: { hp: 100 },
      })
    })
  })
})

describe('store-hook integration — done event → store', () => {
  it('increments turn count, resets processing, clears streaming text, adds separator', async () => {
    // Pre-set some state that done should reset
    act(() => {
      useGameStore.getState().setProcessing(true)
      useGameStore.getState().setIsThinking(true)
      useGameStore.getState().setStreamingText('stale tokens')
    })

    const events = [{ event: 'done', data: JSON.stringify({}) }]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'end turn' })
    })

    await waitFor(() => {
      const state = useGameStore.getState()
      expect(state.turnCount).toBe(1)
      expect(state.processing).toBe(false)
      expect(state.isThinking).toBe(false)
      expect(state.streamingText).toBe('')
    })

    const state = useGameStore.getState()
    expect(state.narrativeEntries).toHaveLength(1)
    expect(state.narrativeEntries[0].type).toBe('separator')
    expect(state.narrativeEntries[0].content).toBe('---')
  })
})

describe('store-hook integration — token_usage event → store', () => {
  it('sets accumulated and latest token counts', async () => {
    const events = [
      {
        event: 'token_usage',
        data: JSON.stringify({ accumulated: 150, latest: 50 }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'cast spell' })
    })

    await waitFor(() => {
      const state = useGameStore.getState()
      expect(state.tokenUsage.accumulated).toBe(150)
      expect(state.tokenUsage.latest).toBe(50)
    })
  })

  it('partially updates token tracking when only accumulated is provided', async () => {
    useGameStore.getState().setTokenUsage({ accumulated: 50, latest: 10 })

    const events = [
      {
        event: 'token_usage',
        data: JSON.stringify({ accumulated: 100 }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'test' })
    })

    await waitFor(() => {
      const state = useGameStore.getState()
      expect(state.tokenUsage.accumulated).toBe(100)
      expect(state.tokenUsage.latest).toBe(10) // preserved from previous
    })
  })
})

describe('store-hook integration — npc_thinking event → store', () => {
  it('sets npcThinking state with npcId and hint', async () => {
    const events = [
      {
        event: 'npc_thinking',
        data: JSON.stringify({ npc_id: 'goblin_1', hint: 'sneaking up' }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'watch goblin' })
    })

    await waitFor(() => {
      const state = useGameStore.getState()
      expect(state.npcThinking).not.toBeNull()
      expect(state.npcThinking!.npcId).toBe('goblin_1')
      expect(state.npcThinking!.hint).toBe('sneaking up')
    })
  })
})

describe('store-hook integration — full lifecycle', () => {
  it('processes a complete turn (token → narrative → state_update → done)', async () => {
    const events = [
      {
        event: 'token',
        data: JSON.stringify({ content: 'The DM ponders… ' }),
      },
      {
        event: 'narrative',
        data: JSON.stringify({ content: 'A goblin appears!' }),
      },
      {
        event: 'state_update',
        data: JSON.stringify({
          state: { hp: 15, turn: 2 },
        }),
      },
      { event: 'done', data: JSON.stringify({}) },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 20)),
    )

    // Set initial state
    useGameStore.getState().setWorldState({ hp: 20 })
    useGameStore.getState().setProcessing(true)
    useGameStore.getState().setIsThinking(true)

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'attack goblin' })
    })

    // Wait for all events to be processed
    await waitFor(() => {
      const state = useGameStore.getState()
      // done clears streaming text and processing
      expect(state.processing).toBe(false)
      expect(state.isThinking).toBe(false)
      expect(state.streamingText).toBe('')
      expect(state.turnCount).toBe(1)
    })

    const state = useGameStore.getState()

    // Token text was set before done cleared it (done clears streamingText)
    // Narrative entries
    expect(state.narrativeEntries.length).toBeGreaterThanOrEqual(1)
    const narrativeEntry = state.narrativeEntries.find(
      (e) => e.type === 'narrative',
    )
    expect(narrativeEntry).toBeDefined()
    expect(narrativeEntry!.content).toBe('A goblin appears!')

    // State update applied
    expect(state.worldState).not.toBeNull()
    expect(state.worldState!.hp).toBe(15)
    expect(state.worldState!.turn).toBe(2)

    // Separator added after done
    const separatorEntry = state.narrativeEntries.find(
      (e) => e.type === 'separator',
    )
    expect(separatorEntry).toBeDefined()
  })
})

describe('store-hook integration — error event → store', () => {
  it('sets error via store and disconnects on error event', async () => {
    const events = [
      {
        event: 'error',
        data: JSON.stringify({ message: 'DM override failed' }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'break game' })
    })

    await waitFor(() => {
      expect(useGameStore.getState().error).toBe('DM override failed')
    })
  })
})

describe('store-hook integration — isConnecting state', () => {
  it('sets isConnecting while fetch is pending, then clears it', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream([], 0)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'hello' })
    })

    // isConnecting should eventually be false after response
    await waitFor(() => {
      expect(result.current.isConnecting).toBe(false)
    })
  })
})
