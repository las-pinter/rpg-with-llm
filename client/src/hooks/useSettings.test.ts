/**
 * useSettings tests — fetch on mount, error handling, save round-trip.
 *
 * Covers: initial fetch, store population, API error, network error,
 * loading states, saveSettings success/failure, and non-Error throws.
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'

// Mock API module before any imports that use it
vi.mock('../api/endpoints', () => ({
  getSettings: vi.fn(),
  saveSettings: vi.fn(),
}))

import { getSettings, saveSettings } from '../api/endpoints'
import { useConnectionStore } from '../stores/connectionStore'
import { useSettings } from './useSettings'

/** Reset the connection store to defaults before each test. */
function resetStore() {
  useConnectionStore.getState().reset()
}

const mockSettings = {
  base_url: 'http://localhost:11434',
  model: 'llama3.2',
  provider_type: 'ollama',
  api_key: null,
  dm_max_tokens: 16000,
  dm_temperature: 0.8,
  dm_timeout: 120,
  npc_max_tokens: 1024,
  npc_temperature: 0.7,
  npc_timeout: 60,
  summarizer_max_tokens: 16000,
  summarizer_temperature: 0.7,
  summarizer_timeout: 120,
  timeout: 300,
  max_tokens: null,
  temperature: null,
} as const

beforeEach(() => {
  resetStore()
  vi.clearAllMocks()
})

afterEach(() => {
  vi.resetAllMocks()
})

/* ------------------------------------------------------------------ */
/*  Initial fetch — happy path                                        */
/* ------------------------------------------------------------------ */

describe('useSettings — initial fetch', () => {
  it('fetches settings on mount and populates store', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: { ...mockSettings, base_url: 'http://example.com', model: 'gpt-4' },
    })

    renderHook(() => useSettings())

    await waitFor(() => {
      expect(useConnectionStore.getState().baseUrl).toBe('http://example.com')
    })
    expect(useConnectionStore.getState().model).toBe('gpt-4')
    expect(useConnectionStore.getState().loading).toBe(false)
    expect(useConnectionStore.getState().error).toBeNull()
  })

  it('maps all snake_case backend fields to store correctly', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: {
        base_url: 'http://test:8080',
        model: 'test-model',
        provider_type: 'groq',
        api_key: 'sk-test',
        dm_max_tokens: 999,
        dm_temperature: 0.5,
        dm_timeout: 60,
        npc_max_tokens: 512,
        npc_temperature: 0.3,
        npc_timeout: 30,
        summarizer_max_tokens: 8000,
        summarizer_temperature: 0.4,
        summarizer_timeout: 90,
        timeout: 600,
        max_tokens: 4096,
        temperature: 0.2,
      },
    })

    renderHook(() => useSettings())

    await waitFor(() => {
      const state = useConnectionStore.getState()
      expect(state.baseUrl).toBe('http://test:8080')
      expect(state.model).toBe('test-model')
      expect(state.providerType).toBe('groq')
      expect(state.apiKey).toBe('sk-test')
      expect(state.dm_max_tokens).toBe(999)
      expect(state.dm_temperature).toBe(0.5)
      expect(state.dm_timeout).toBe(60)
      expect(state.npc_max_tokens).toBe(512)
      expect(state.npc_temperature).toBe(0.3)
      expect(state.npc_timeout).toBe(30)
      expect(state.summarizer_max_tokens).toBe(8000)
      expect(state.summarizer_temperature).toBe(0.4)
      expect(state.summarizer_timeout).toBe(90)
      expect(state.timeout).toBe(600)
      expect(state.max_tokens).toBe(4096)
      expect(state.temperature).toBe(0.2)
    })
  })

  it('clears any previous error before fetching', async () => {
    useConnectionStore.getState().setError('stale error')
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    renderHook(() => useSettings())

    await waitFor(() => {
      expect(useConnectionStore.getState().error).toBeNull()
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Fetch guards — double-fetch and re-entrant protection            */
/* ------------------------------------------------------------------ */

describe('useSettings — fetch guards', () => {
  it('fetches settings exactly once during mount lifecycle', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    renderHook(() => useSettings())

    await waitFor(() => {
      expect(useConnectionStore.getState().loading).toBe(false)
    })

    expect(getSettings).toHaveBeenCalledTimes(1)
  })

  it('does not fetch if store is already loading (re-entrant guard)', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    act(() => {
      useConnectionStore.getState().setLoading(true)
    })

    renderHook(() => useSettings())

    // Small delay to let any effect run
    await new Promise((r) => setTimeout(r, 50))

    expect(getSettings).not.toHaveBeenCalled()
  })
})

/* ------------------------------------------------------------------ */
/*  Loading states                                                    */
/* ------------------------------------------------------------------ */

describe('useSettings — loading states', () => {
  it('sets loading to true during fetch', async () => {
    const neverResolve = new Promise<{ ok: boolean; settings: typeof mockSettings }>(
      () => {
        /* never resolves */
      },
    )
    vi.mocked(getSettings).mockReturnValue(neverResolve)

    renderHook(() => useSettings())

    await waitFor(() => {
      expect(useConnectionStore.getState().loading).toBe(true)
    })
  })

  it('sets loading to false after fetch completes', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    renderHook(() => useSettings())

    await waitFor(() => {
      expect(useConnectionStore.getState().loading).toBe(false)
    })
  })

  it('returns loading and error from the hook', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    const { result } = renderHook(() => useSettings())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBeNull()
    expect(result.current.saveSettings).toBeInstanceOf(Function)
  })
})

/* ------------------------------------------------------------------ */
/*  Error handling                                                   */
/* ------------------------------------------------------------------ */

describe('useSettings — error handling', () => {
  it('handles API ok:false response gracefully', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: false,
      settings: mockSettings,
    })

    renderHook(() => useSettings())

    await waitFor(() => {
      expect(useConnectionStore.getState().error).toBe('Failed to load settings')
    })
    expect(useConnectionStore.getState().loading).toBe(false)
  })

  it('handles network error gracefully', async () => {
    vi.mocked(getSettings).mockRejectedValue(new Error('Network failure'))

    renderHook(() => useSettings())

    await waitFor(() => {
      expect(useConnectionStore.getState().error).toBe('Network failure')
    })
    expect(useConnectionStore.getState().loading).toBe(false)
  })

  it('handles non-Error thrown values gracefully', async () => {
    vi.mocked(getSettings).mockRejectedValue('raw string error')

    renderHook(() => useSettings())

    await waitFor(() => {
      expect(useConnectionStore.getState().error).toBe('Failed to load settings')
    })
    expect(useConnectionStore.getState().loading).toBe(false)
  })

  it('does not update state after unmount (cancelled flag)', async () => {
    const differentSettings = {
      ...mockSettings,
      base_url: 'http://should-not-be-set',
      model: 'should-not-be-set',
    }
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: differentSettings,
    })

    const { unmount } = renderHook(() => useSettings())
    unmount()

    // Wait for any pending promises to settle
    await vi.waitFor(() => {
      // Store should still have defaults — not the mock values — because
      // the cancelled flag prevented state updates after unmount
      expect(useConnectionStore.getState().baseUrl).toBe('http://localhost:11434')
      expect(useConnectionStore.getState().model).toBe('llama3.2')
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases                                                        */
/* ------------------------------------------------------------------ */

describe('useSettings — edge cases', () => {
  it('handles settings response with missing fields without crashing', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: {} as any,
    })

    renderHook(() => useSettings())

    await waitFor(() => {
      expect(useConnectionStore.getState().loading).toBe(false)
    })
  })
})

/* ------------------------------------------------------------------ */
/*  saveSettings function                                             */
/* ------------------------------------------------------------------ */

describe('useSettings — saveSettings', () => {
  it('sends store state to backend with correct keys', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })
    vi.mocked(saveSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    const { result } = renderHook(() => useSettings())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    // Mutate some store values
    act(() => {
      useConnectionStore.getState().setBaseUrl('http://custom:8080')
      useConnectionStore.getState().setModel('custom-model')
      useConnectionStore.getState().setProviderType('openrouter')
      useConnectionStore.getState().setApiKey('sk-custom')
    })

    await act(async () => {
      await result.current.saveSettings()
    })

    expect(saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        base_url: 'http://custom:8080',
        model: 'custom-model',
        provider_type: 'openrouter',
        api_key: 'sk-custom',
      }),
    )
  })

  it('sends agent-specific fields to backend', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })
    vi.mocked(saveSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    const { result } = renderHook(() => useSettings())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    act(() => {
      useConnectionStore.getState().setSettings({
        dm_max_tokens: 32000,
        npc_max_tokens: 2048,
        summarizer_max_tokens: 9999,
      })
    })

    await act(async () => {
      await result.current.saveSettings()
    })

    expect(saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        dm_max_tokens: 32000,
        npc_max_tokens: 2048,
        summarizer_max_tokens: 9999,
      }),
    )
  })

  it('throws when backend returns ok:false', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })
    vi.mocked(saveSettings).mockResolvedValue({
      ok: false,
      settings: mockSettings,
    })

    const { result } = renderHook(() => useSettings())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await expect(result.current.saveSettings()).rejects.toThrow(
      'Failed to save settings',
    )
  })

  it('returns a promise from saveSettings', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })
    vi.mocked(saveSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    const { result } = renderHook(() => useSettings())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    const promise = result.current.saveSettings()
    expect(promise).toBeInstanceOf(Promise)
    await promise
  })

  it('maps all fields correctly when saving settings', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })
    vi.mocked(saveSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    const { result } = renderHook(() => useSettings())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    act(() => {
      useConnectionStore.getState().setSettings({
        baseUrl: 'http://full-map:9090',
        model: 'full-map-model',
        providerType: 'openrouter',
        apiKey: 'sk-full-map',
        dm_max_tokens: 1111,
        dm_temperature: 0.11,
        dm_timeout: 222,
        npc_max_tokens: 3333,
        npc_temperature: 0.44,
        npc_timeout: 555,
        summarizer_max_tokens: 6666,
        summarizer_temperature: 0.55,
        summarizer_timeout: 777,
        timeout: 8888,
        max_tokens: 9999,
        temperature: 0.66,
      })
    })

    await act(async () => {
      await result.current.saveSettings()
    })

    expect(saveSettings).toHaveBeenCalledWith({
      base_url: 'http://full-map:9090',
      model: 'full-map-model',
      provider_type: 'openrouter',
      api_key: 'sk-full-map',
      dm_max_tokens: 1111,
      dm_temperature: 0.11,
      dm_timeout: 222,
      npc_max_tokens: 3333,
      npc_temperature: 0.44,
      npc_timeout: 555,
      summarizer_max_tokens: 6666,
      summarizer_temperature: 0.55,
      summarizer_timeout: 777,
      timeout: 8888,
      max_tokens: 9999,
      temperature: 0.66,
    })
  })

  it('preserves null values through saveSettings mapping', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })
    vi.mocked(saveSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })

    const { result } = renderHook(() => useSettings())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.saveSettings()
    })

    expect(saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        api_key: null,
        max_tokens: null,
        temperature: null,
      }),
    )
  })

  it('throws network error when saveSettings API rejects', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ok: true,
      settings: mockSettings,
    })
    vi.mocked(saveSettings).mockRejectedValue(new Error('Network failure'))

    const { result } = renderHook(() => useSettings())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await expect(result.current.saveSettings()).rejects.toThrow('Network failure')
  })
})
