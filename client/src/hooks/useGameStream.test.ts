/**
 * useGameStream tests — SSE stream connection, event parsing, store dispatch.
 *
 * Covers: initialization, fetch calls, all SSE event types, disconnect,
 * error responses, network failures, cleanup on unmount, and reconnection.
 *
 * NOTE on error tests: the hook retries with exponential backoff (1s, 2s, 4s)
 * before setting the error state, so we use fake timers to advance past them.
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useGameStore } from '../stores/gameStore'
import { useGameStream } from './useGameStream'

// ---------------------------------------------------------------------------
//  Mock helpers
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
      const timerId = setTimeout(() => {
        try {
          controller.enqueue(encoder.encode(sseText))
          controller.close()
        } catch {
          // Stream may have been cancelled (e.g. reader.cancel()) — ignore
        }
      }, delay)
      // Cancel the pending timeout if the stream is cancelled
      if ('signal' in controller) {
        ;(controller as { signal: AbortSignal }).signal.addEventListener(
          'abort',
          () => clearTimeout(timerId),
          { once: true },
        )
      }
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

/** Advance fake timers enough for 4 fetch attempts (initial + 3 retries). */
const RETRY_TOTAL_MS = 8000 // 1s + 2s + 4s + buffer

// ---------------------------------------------------------------------------
//  Test setup / teardown
// ---------------------------------------------------------------------------

function resetStore() {
  useGameStore.getState().reset()
}

beforeEach(() => {
  resetStore()
  vi.clearAllMocks()
})

afterEach(() => {
  vi.resetAllMocks()
})

// ---------------------------------------------------------------------------
//  Initialization
// ---------------------------------------------------------------------------

describe('useGameStream — initialization', () => {
  it('initializes with isConnecting=false and error=null', () => {
    const { result } = renderHook(() => useGameStream())

    expect(result.current.isConnecting).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.connect).toBeInstanceOf(Function)
    expect(result.current.disconnect).toBeInstanceOf(Function)
  })
})

// ---------------------------------------------------------------------------
//  Connect — fetch behavior
// ---------------------------------------------------------------------------

describe('useGameStream — connect', () => {
  it('triggers fetch POST to /api/game/stream with correct headers', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream([], 0)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'hello' })
    })

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/game/stream',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })
  })

  it('sends correct body JSON with all fields mapped to snake_case', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream([], 0)),
    )

    const { result } = renderHook(() => useGameStream())

    const options = {
      input: 'attack the goblin',
      provider: { type: 'ollama', model: 'llama3' },
      state: { hp: 10 },
      character: { name: 'Frettnik', class: 'Rogue' },
      npcProvider: { type: 'groq', model: 'mixtral' },
      summarizerProvider: { type: 'openai', model: 'gpt-4' },
    }

    act(() => {
      result.current.connect(options)
    })

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled()
    })

    const callBody = JSON.parse(
      (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
    )
    expect(callBody.input).toBe('attack the goblin')
    expect(callBody.provider).toEqual({ type: 'ollama', model: 'llama3' })
    expect(callBody.state).toEqual({ hp: 10 })
    expect(callBody.character).toEqual({ name: 'Frettnik', class: 'Rogue' })
    expect(callBody.npc_provider).toEqual({ type: 'groq', model: 'mixtral' })
    expect(callBody.summarizer_provider).toEqual({
      type: 'openai',
      model: 'gpt-4',
    })
  })

  it('sends body without optional fields when they are omitted', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream([], 0)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'hello' })
    })

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled()
    })

    const callBody = JSON.parse(
      (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
    )
    expect(callBody.input).toBe('hello')
    expect(callBody.provider).toBeUndefined()
    expect(callBody.state).toBeUndefined()
    expect(callBody.character).toBeUndefined()
    expect(callBody.npc_provider).toBeUndefined()
    expect(callBody.summarizer_provider).toBeUndefined()
  })

  it('sets isConnecting=true while connecting, then false after response', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream([], 0)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'hello' })
    })

    await waitFor(() => {
      expect(result.current.isConnecting).toBe(false)
    })
  })
})

// ---------------------------------------------------------------------------
//  SSE event dispatch
// ---------------------------------------------------------------------------

describe('useGameStream — SSE events', () => {
  it('appends token content to streamingText on token event', async () => {
    const events = [
      {
        event: 'token',
        data: JSON.stringify({ content: 'Hello, brave adventurer!' }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'say hi' })
    })

    await waitFor(() => {
      expect(useGameStore.getState().streamingText).toBe(
        'Hello, brave adventurer!',
      )
    })
  })

  it('appends multiple token events sequentially', async () => {
    const events = [
      { event: 'token', data: JSON.stringify({ content: 'Hello ' }) },
      { event: 'token', data: JSON.stringify({ content: 'world!' }) },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'test' })
    })

    await waitFor(() => {
      expect(useGameStore.getState().streamingText).toBe('Hello world!')
    })
  })

  it('ignores token events with no content field', async () => {
    const events = [{ event: 'token', data: JSON.stringify({}) }]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'test' })
    })

    // Use setTimeout to yield control so the stream's macrotask (setTimeout inside
    // mockSSEStream) fires and all pending async work completes. waitFor can't help
    // here because we're asserting no change happened.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    expect(useGameStore.getState().streamingText).toBe('')
    expect(useGameStore.getState().error).toBeNull()
  })

  it('adds narrative entry and appends narrative text on narrative event', async () => {
    const events = [
      {
        event: 'narrative',
        data: JSON.stringify({ content: 'A dark cave looms ahead.' }),
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
        'A dark cave looms ahead.',
      )
    })

    const state = useGameStore.getState()
    expect(state.narrative).toBe('A dark cave looms ahead.')
  })

  it('handles done event — increments turn, resets processing/thinking, adds separator', async () => {
    // Set some state that done should reset
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

  it('sets token usage on token_usage event', async () => {
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

  it('updates token usage partially on token_usage event', async () => {
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
      // latest should retain the default of 0
      expect(state.tokenUsage.latest).toBe(0)
    })
  })

  it('sets npcThinking on npc_thinking event', async () => {
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

  it('applies state update on state_update event', async () => {
    const events = [
      {
        event: 'state_update',
        data: JSON.stringify({
          hp: { action: 'set', value: 15 },
          gold: { action: 'set', value: 100 },
        }),
      },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'check stats' })
    })

    await waitFor(() => {
      const state = useGameStore.getState()
      expect(state.worldState).not.toBeNull()
    })

    const state = useGameStore.getState()
    expect(state.worldState!.hp).toBe(15)
    expect(state.worldState!.gold).toBe(100)
  })

  it('sets error via store on error event', async () => {
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

  it('ignores unknown event types without crashing', async () => {
    const events = [
      { event: 'unknown_type', data: JSON.stringify({ foo: 'bar' }) },
    ]
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream(events, 10)),
    )

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'do thing' })
    })

    // setTimeout yields control so the stream's macrotask fires and all pending async
    // work completes. waitFor can't help because we're asserting no change occurred.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    // No crash — store remains in default state for key fields
    const state = useGameStore.getState()
    expect(state.error).toBeNull()
    expect(state.streamingText).toBe('')
    expect(state.tokenUsage.accumulated).toBe(0)
  })

  it('handles malformed JSON in event data without crashing', async () => {
    const sseText = 'event: token\ndata: {invalid json\n\n'
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        setTimeout(() => {
          controller.enqueue(encoder.encode(sseText))
          controller.close()
        }, 10)
      },
    })

    global.fetch = vi.fn().mockResolvedValue(mockFetchResponse(stream))

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'test' })
    })

    // setTimeout yields control so the stream's macrotask fires and all pending async
    // work completes. waitFor can't help because we're asserting no change occurred.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    expect(useGameStore.getState().streamingText).toBe('')
  })

  it('handles SSE events split across chunks', async () => {
    const encoder = new TextEncoder()
    let controller!: ReadableStreamDefaultController
    const stream = new ReadableStream({
      start(c) {
        controller = c
      },
    })

    global.fetch = vi.fn().mockResolvedValue(mockFetchResponse(stream))
    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'hello' })
    })

    // Wait for connect to start reading the stream
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10))
    })

    // Send partial event split across chunk boundaries — first two chunks
    // form a complete token event, third chunk is a done event
    act(() => {
      controller!.enqueue(encoder.encode('event: token\ndata: {"con'))
    })
    act(() => {
      controller!.enqueue(encoder.encode('tent":"Hello!"}\n\n'))
    })

    // Wait for token to be processed — done clears streamingText so
    // we must verify BEFORE sending done
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })
    expect(useGameStore.getState().streamingText).toContain('Hello!')

    // Now send done event to complete the turn
    act(() => {
      controller!.enqueue(encoder.encode('event: done\ndata: {}\n\n'))
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    // Done clears streamingText and increments turn count
    expect(useGameStore.getState().streamingText).toBe('')
    expect(useGameStore.getState().turnCount).toBe(1)
  })
})

// ---------------------------------------------------------------------------
//  Disconnect
// ---------------------------------------------------------------------------

describe('useGameStream — disconnect', () => {
  it('sets isConnecting to false when called during connection', async () => {
    // Use a never-resolving fetch to keep isConnecting=true
    global.fetch = vi.fn().mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'hello' })
    })

    expect(result.current.isConnecting).toBe(true)

    act(() => {
      result.current.disconnect()
    })

    expect(result.current.isConnecting).toBe(false)
  })

  it('is idempotent — calling twice does not throw', () => {
    const { result } = renderHook(() => useGameStream())

    expect(() => {
      act(() => {
        result.current.disconnect()
        result.current.disconnect()
      })
    }).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
//  Error handling
//
//  The hook retries up to 3 times with exponential backoff (1s, 2s, 4s)
//  before settling on an error. We use fake timers to collapse that wait.
// ---------------------------------------------------------------------------

describe('useGameStream — error handling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('sets error state when response is non-ok', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      body: null,
    })

    const { result } = renderHook(() => useGameStream())

    await act(async () => {
      result.current.connect({ input: 'fail' })
      await vi.advanceTimersByTimeAsync(RETRY_TOTAL_MS)
    })

    expect(result.current.error).toBe('HTTP 500')
    expect(result.current.isConnecting).toBe(false)
  })

  it('sets error state on network failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network failure'))

    const { result } = renderHook(() => useGameStream())

    await act(async () => {
      result.current.connect({ input: 'fail' })
      await vi.advanceTimersByTimeAsync(RETRY_TOTAL_MS)
    })

    expect(result.current.error).toBe('Network failure')
    expect(result.current.isConnecting).toBe(false)
  })

  it('handles non-Error thrown values gracefully', async () => {
    global.fetch = vi.fn().mockRejectedValue('raw string error')

    const { result } = renderHook(() => useGameStream())

    await act(async () => {
      result.current.connect({ input: 'fail' })
      await vi.advanceTimersByTimeAsync(RETRY_TOTAL_MS)
    })

    expect(result.current.error).toBe('Connection failed')
    expect(result.current.isConnecting).toBe(false)
  })

  it('handles null body on response gracefully', async () => {
    // When response.body is null, response.body!.getReader() raises a TypeError
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: null,
    })

    const { result } = renderHook(() => useGameStream())

    await act(async () => {
      result.current.connect({ input: 'test' })
      await vi.advanceTimersByTimeAsync(RETRY_TOTAL_MS)
    })

    expect(result.current.error).toBeTruthy()
    expect(result.current.isConnecting).toBe(false)
  })
})

// ---------------------------------------------------------------------------
//  Lifecycle
// ---------------------------------------------------------------------------

describe('useGameStream — lifecycle', () => {
  it('prevents double-connect (Strict Mode guard)', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      mockFetchResponse(mockSSEStream([], 0)),
    )
    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'a' })
    })
    act(() => {
      result.current.connect({ input: 'b' })
    })

    expect(global.fetch).toHaveBeenCalledTimes(1)

    // Let the delayed stream settle — avoids act() warning from the
    // setTimeout(0) inside mockSSEStream firing after synchronous check
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10))
    })
  })

  it('does not dispatch events to the store after unmount', async () => {
    let resolveFetch!: (value: unknown) => void
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve
    })
    global.fetch = vi.fn().mockReturnValue(fetchPromise)

    const { result, unmount } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'hello' })
    })

    // Unmount BEFORE stream events arrive
    unmount()

    // Now resolve the fetch with a stream that sends real events after a delay
    // The cancelled flag should prevent any dispatch to the store
    await act(async () => {
      resolveFetch!(
        mockFetchResponse(
          mockSSEStream(
            [
              { event: 'token', data: '{"content":"stale"}' },
              { event: 'done', data: '{}' },
            ],
            50,
          ),
        ),
      )
      // Wait long enough for the delayed stream to emit and be processed
      await new Promise((r) => setTimeout(r, 100))
    })

    // Store should NOT have been updated — cancellation prevents dispatch
    expect(useGameStore.getState().streamingText).toBe('')
    expect(useGameStore.getState().turnCount).toBe(0)
  })
})

// ---------------------------------------------------------------------------
//  Reconnection
// ---------------------------------------------------------------------------

describe('useGameStream — reconnection', () => {
  it('allows reconnection after a stream completes', async () => {
    // First stream: a done event
    const firstEvents = [{ event: 'done', data: JSON.stringify({}) }]
    // Second stream: a token event
    const secondEvents = [
      { event: 'token', data: JSON.stringify({ content: 'reconnected' }) },
    ]

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        mockFetchResponse(mockSSEStream(firstEvents, 10)),
      )
      .mockResolvedValueOnce(
        mockFetchResponse(mockSSEStream(secondEvents, 10)),
      )

    const { result } = renderHook(() => useGameStream())

    // First connection
    act(() => {
      result.current.connect({ input: 'first' })
    })

    // Wait for the first stream to complete (done event increments turn count)
    await waitFor(() => {
      expect(useGameStore.getState().turnCount).toBe(1)
    })

    // Second connection
    act(() => {
      result.current.connect({ input: 'second' })
    })

    // Wait for the second stream's token to appear
    await waitFor(() => {
      expect(useGameStore.getState().streamingText).toBe('reconnected')
    })

    // Fetch should have been called twice
    expect(global.fetch).toHaveBeenCalledTimes(2)
  })

  it('disconnect during pending fetch prevents stale state from resolving', async () => {
    let resolveFetch!: (value: unknown) => void
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve
    })
    global.fetch = vi.fn().mockReturnValue(fetchPromise)

    const { result } = renderHook(() => useGameStream())

    act(() => {
      result.current.connect({ input: 'test' })
    })

    // Disconnect before fetch resolves
    act(() => {
      result.current.disconnect()
    })

    // Now let the fetch resolve with an error response
    await act(async () => {
      resolveFetch!({ ok: false, status: 500, body: null })
      // Yield control so the attempt() function processes the resolved response
      await new Promise((r) => setTimeout(r, 20))
    })

    // State should not be updated — cancelled flag should prevent it
    expect(result.current.error).toBeNull()
    expect(result.current.isConnecting).toBe(false)
  })
})
