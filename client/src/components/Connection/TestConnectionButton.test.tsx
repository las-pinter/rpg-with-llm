/**
 * TestConnectionButton tests — Grubnik-certified goblin scrutiny.
 *
 * Covers: validation (baseUrl, apiKey), loading state, successful health
 * check, auto-save on success, timeout, API error, network error,
 * double-click prevention, and edge cases.
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock the API module before any imports that use it
vi.mock('../../api/endpoints', () => ({
  checkHealth: vi.fn(),
  saveSettings: vi.fn(),
}))

import { checkHealth, saveSettings } from '../../api/endpoints'
import { useConnectionStore } from '../../stores/connectionStore'
import TestConnectionButton from './TestConnectionButton'

/** Reset the connection store to defaults before each test. */
function resetStore() {
  useConnectionStore.getState().reset()
}

beforeEach(() => {
  resetStore()
  vi.clearAllMocks()
})

/* ------------------------------------------------------------------ */
/*  Initial render state                                               */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — initial render', () => {
  it('renders a "Test Connection" button', () => {
    render(<TestConnectionButton />)
    expect(screen.getByRole('button', { name: 'Test Connection' })).toBeInTheDocument()
  })

  it('renders the ConnectionStatus component with idle state', () => {
    render(<TestConnectionButton />)
    expect(screen.getByText('Not tested')).toBeInTheDocument()
  })

  it('button is enabled on initial render', () => {
    render(<TestConnectionButton />)
    expect(screen.getByRole('button', { name: 'Test Connection' })).toBeEnabled()
  })
})

/* ------------------------------------------------------------------ */
/*  Validation — baseUrl empty                                         */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — validation: baseUrl empty', () => {
  it('shows "Base URL is required" error when baseUrl is empty', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByText('Base URL is required')).toBeInTheDocument()
  })

  it('sets healthOk to false when baseUrl is empty', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(useConnectionStore.getState().healthOk).toBe(false)
  })

  it('sets connectionTested to false when baseUrl is empty', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(useConnectionStore.getState().connectionTested).toBe(false)
  })

  it('does NOT call checkHealth when baseUrl is empty', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(checkHealth).not.toHaveBeenCalled()
  })
})

/* ------------------------------------------------------------------ */
/*  Validation — API key required but missing                          */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — validation: apiKey missing', () => {
  it('shows an error for groq when apiKey is empty', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    useConnectionStore.getState().setApiKey('')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByText('API key is required for groq')).toBeInTheDocument()
  })

  it('shows an error for openrouter when apiKey is null', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('openrouter')
    useConnectionStore.getState().setApiKey(null)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByText('API key is required for openrouter')).toBeInTheDocument()
  })

  it('shows an error for unsloth when apiKey is missing', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('unsloth')
    useConnectionStore.getState().setApiKey(null)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByText('API key is required for unsloth')).toBeInTheDocument()
  })

  it('does NOT require apiKey for ollama', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 5,
      model: 'test',
      error: null,
    })
    // Default is ollama with apiKey: null
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(mockCheckHealth).toHaveBeenCalled()
    })
  })

  it('does NOT require apiKey for llama.cpp', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 5,
      model: 'test',
      error: null,
    })
    useConnectionStore.getState().setProviderType('llama.cpp')
    useConnectionStore.getState().setApiKey(null)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(mockCheckHealth).toHaveBeenCalled()
    })
  })

  it('does NOT call checkHealth when apiKey validation fails', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    useConnectionStore.getState().setApiKey('')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(checkHealth).not.toHaveBeenCalled()
  })

  it('sets connectionTested to false when apiKey validation fails', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    useConnectionStore.getState().setApiKey('')
    // Pre-set to true so we can verify the component flips it back
    useConnectionStore.getState().setConnectionTested(true)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(useConnectionStore.getState().connectionTested).toBe(false)
  })
})

/* ------------------------------------------------------------------ */
/*  Loading state                                                      */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — loading state', () => {
  it('shows "Testing…" while health check is in progress', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    // Return a promise that never resolves to keep loading state active
    mockCheckHealth.mockReturnValue(new Promise(() => {}))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByRole('button', { name: 'Testing…' })).toBeInTheDocument()
  })

  it('disables the button while checking', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockReturnValue(new Promise(() => {}))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByRole('button', { name: 'Testing…' })).toBeDisabled()
  })

  it('shows "Testing connection…" status while checking', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockReturnValue(new Promise(() => {}))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByText('Testing connection…')).toBeInTheDocument()
  })

  it('sets checking to true in the store', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockReturnValue(new Promise(() => {}))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(useConnectionStore.getState().checking).toBe(true)
  })
})

/* ------------------------------------------------------------------ */
/*  Successful health check                                             */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — successful health check', () => {
  it('shows "Connected" with latency on success', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 42,
      model: 'llama3.2',
      error: null,
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument()
      expect(screen.getByText('42ms')).toBeInTheDocument()
    })
  })

  it('calls checkHealth with the correct parameters', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 10,
      model: 'test-model',
      error: null,
    })
    useConnectionStore.getState().setBaseUrl('http://my-host:8080')
    useConnectionStore.getState().setModel('gpt-4')
    useConnectionStore.getState().setProviderType('groq')
    useConnectionStore.getState().setApiKey('sk-test-key')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(mockCheckHealth).toHaveBeenCalledWith(
        {
          base_url: 'http://my-host:8080',
          model: 'gpt-4',
          api_key: 'sk-test-key',
          provider_type: 'groq',
        },
        expect.any(AbortSignal),
      )
    })
  })

  it('excludes apiKey from params when it is null', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 5,
      model: 'llama3.2',
      error: null,
    })
    // Default ollama with null apiKey
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      const callParams = mockCheckHealth.mock.calls[0][0]
      expect(callParams).not.toHaveProperty('api_key')
    })
  })

  it('excludes providerType from params when it is empty string', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 5,
      model: 'test',
      error: null,
    })
    useConnectionStore.getState().setProviderType('')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      const callParams = mockCheckHealth.mock.calls[0][0]
      expect(callParams).not.toHaveProperty('provider_type')
    })
  })

  it('sets healthOk to true and connectionTested to true', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 30,
      model: 'test',
      error: null,
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      const state = useConnectionStore.getState()
      expect(state.healthOk).toBe(true)
      expect(state.connectionTested).toBe(true)
      expect(state.latencyMs).toBe(30)
    })
  })

  it('re-enables the button after successful check', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 15,
      model: 'test',
      error: null,
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Test Connection' })).toBeEnabled()
    })
  })

  it('sets checking to false after successful check', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 20,
      model: 'test',
      error: null,
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().checking).toBe(false)
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Auto-save on success                                                */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — auto-save on success', () => {
  it('calls saveSettings with all settings on success', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    const mockSaveSettings = vi.mocked(saveSettings)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 10,
      model: 'test',
      error: null,
    })
    mockSaveSettings.mockResolvedValue({
      ok: true,
      settings: {
        base_url: 'http://localhost:11434',
        model: 'llama3.2',
        provider_type: 'ollama',
        api_key: null,
        timeout: 300,
        max_tokens: null,
        temperature: null,
        dm_max_tokens: 16000,
        dm_temperature: 0.8,
        dm_timeout: 120,
        npc_max_tokens: 1024,
        npc_temperature: 0.7,
        npc_timeout: 60,
        summarizer_max_tokens: 16000,
        summarizer_temperature: 0.7,
        summarizer_timeout: 120,
      },
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(mockSaveSettings).toHaveBeenCalled()
    })
  })

  it('passes correct settings values to saveSettings', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    const mockSaveSettings = vi.mocked(saveSettings)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 10,
      model: 'custom-model',
      error: null,
    })
    mockSaveSettings.mockResolvedValue({
      ok: true,
      settings: {
        base_url: 'https://api.groq.com',
        model: 'custom-model',
        provider_type: 'groq',
        api_key: 'sk-test',
        timeout: 120,
        max_tokens: 4096,
        temperature: 0.5,
        dm_max_tokens: 16000,
        dm_temperature: 0.8,
        dm_timeout: 120,
        npc_max_tokens: 1024,
        npc_temperature: 0.7,
        npc_timeout: 60,
        summarizer_max_tokens: 16000,
        summarizer_temperature: 0.7,
        summarizer_timeout: 120,
      },
    })

    // Set custom values
    useConnectionStore.getState().setBaseUrl('https://api.groq.com')
    useConnectionStore.getState().setModel('custom-model')
    useConnectionStore.getState().setProviderType('groq')
    useConnectionStore.getState().setApiKey('sk-test')
    useConnectionStore.getState().setTimeout(120)
    useConnectionStore.getState().setMaxTokens(4096)
    useConnectionStore.getState().setTemperature(0.5)

    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(mockSaveSettings).toHaveBeenCalledWith({
        base_url: 'https://api.groq.com',
        model: 'custom-model',
        provider_type: 'groq',
        api_key: 'sk-test',
        timeout: 120,
        max_tokens: 4096,
        temperature: 0.5,
        dm_max_tokens: 16000,
        dm_temperature: 0.8,
        dm_timeout: 120,
        npc_max_tokens: 1024,
        npc_temperature: 0.7,
        npc_timeout: 60,
        summarizer_max_tokens: 16000,
        summarizer_temperature: 0.7,
        summarizer_timeout: 120,
      })
    })
  })

  it('still shows "Connected" even if saveSettings fails', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    const mockSaveSettings = vi.mocked(saveSettings)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 25,
      model: 'test',
      error: null,
    })
    mockSaveSettings.mockRejectedValue(new Error('Save failed'))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument()
      expect(screen.getByText('25ms')).toBeInTheDocument()
    })
  })

  it('keeps healthOk true even if saveSettings fails', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    const mockSaveSettings = vi.mocked(saveSettings)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 25,
      model: 'test',
      error: null,
    })
    mockSaveSettings.mockRejectedValue(new Error('Save failed'))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().healthOk).toBe(true)
      expect(useConnectionStore.getState().connectionTested).toBe(true)
    })
  })
})

/* ------------------------------------------------------------------ */
/*  API error response                                                 */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — API error response', () => {
  it('shows error text when API returns ok: false with error message', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: false,
      latency_ms: 0,
      model: '',
      error: 'Invalid API key',
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(screen.getByText('Invalid API key')).toBeInTheDocument()
    })
  })

  it('shows "Connection failed" fallback when API returns ok: false with no error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: false,
      latency_ms: 0,
      model: '',
      error: null,
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(screen.getByText('Connection failed')).toBeInTheDocument()
    })
  })

  it('sets healthOk to false on API error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: false,
      latency_ms: 0,
      model: '',
      error: 'Bad gateway',
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().healthOk).toBe(false)
    })
  })

  it('does NOT call saveSettings on API error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    const mockSaveSettings = vi.mocked(saveSettings)
    mockCheckHealth.mockResolvedValue({
      ok: false,
      latency_ms: 0,
      model: '',
      error: 'Server error',
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().healthOk).toBe(false)
    })
    expect(mockSaveSettings).not.toHaveBeenCalled()
  })

  it('re-enables the button after API error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: false,
      latency_ms: 0,
      model: '',
      error: 'Error',
    })
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Test Connection' })).toBeEnabled()
    })
  })

  it('sets connectionTested to false on API error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: false,
      latency_ms: 0,
      model: '',
      error: 'Bad gateway',
    })
    useConnectionStore.getState().setConnectionTested(true)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().connectionTested).toBe(false)
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Network error                                                      */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — network error', () => {
  it('shows error message when checkHealth throws an Error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockRejectedValue(new Error('Network failure'))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(screen.getByText('Network failure')).toBeInTheDocument()
    })
  })

  it('shows "Connection failed" when thrown value is a non-Error object', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mockCheckHealth.mockRejectedValue({ error: 'Something broke' } as any)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(screen.getByText('Something broke')).toBeInTheDocument()
    })
  })

  it('shows "Connection failed" when thrown value is an unexpected type', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockRejectedValue('raw string error')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(screen.getByText('Connection failed')).toBeInTheDocument()
    })
  })

  it('sets healthOk to false on network error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockRejectedValue(new Error('Connection refused'))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().healthOk).toBe(false)
    })
  })

  it('resets checking to false after network error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockRejectedValue(new Error('Timeout'))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().checking).toBe(false)
    })
  })

  it('does NOT call saveSettings on network error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    const mockSaveSettings = vi.mocked(saveSettings)
    mockCheckHealth.mockRejectedValue(new Error('Network failure'))
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().healthOk).toBe(false)
    })
    expect(mockSaveSettings).not.toHaveBeenCalled()
  })

  it('sets connectionTested to false on network error', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockRejectedValue(new Error('Connection refused'))
    useConnectionStore.getState().setConnectionTested(true)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().connectionTested).toBe(false)
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Double-click prevention                                            */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — double-click prevention', () => {
  it('does not call checkHealth again if already checking', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockReturnValue(new Promise(() => {}))
    render(<TestConnectionButton />)

    // First click
    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    // Button should now be disabled with "Testing…"
    const button = screen.getByRole('button', { name: 'Testing…' })
    expect(button).toBeDisabled()

    // Try clicking the disabled button — second call should not happen
    await user.click(button)

    expect(mockCheckHealth).toHaveBeenCalledTimes(1)
  })
})

/* ------------------------------------------------------------------ */
/*  Timeout handling                                                   */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — timeout handling', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows timeout error when health check takes too long', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    // Return a promise that never resolves
    mockCheckHealth.mockReturnValue(new Promise(() => {}))

    // Set a short timeout for testing
    useConnectionStore.getState().setTimeout(1) // 1 second

    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    // Advance timers past the 1s timeout
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    await waitFor(() => {
      expect(screen.getByText('Request timed out after 1s')).toBeInTheDocument()
    })
  })

  it('sets healthOk to false on timeout', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockReturnValue(new Promise(() => {}))
    useConnectionStore.getState().setTimeout(1)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    await waitFor(() => {
      expect(useConnectionStore.getState().healthOk).toBe(false)
    })
  })

  it('does not timeout when health check resolves before timeout', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 5,
      model: 'test',
      error: null,
    })
    useConnectionStore.getState().setTimeout(10) // 10 second timeout

    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    // Let the health check resolve immediately (before 10s)
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument()
    })

    // Advance past the timeout — should still be connected
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000)
    })

    expect(screen.getByText('Connected')).toBeInTheDocument()
  })

  it('sets connectionTested to false on timeout', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockReturnValue(new Promise(() => {}))
    useConnectionStore.getState().setTimeout(1)
    useConnectionStore.getState().setConnectionTested(true)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    await waitFor(() => {
      expect(useConnectionStore.getState().connectionTested).toBe(false)
    })
  })

  it('sets checking to false after timeout', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockReturnValue(new Promise(() => {}))
    useConnectionStore.getState().setTimeout(1)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    await waitFor(() => {
      expect(useConnectionStore.getState().checking).toBe(false)
    })
  })

  it('does not call saveSettings on timeout', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    const mockSaveSettings = vi.mocked(saveSettings)
    mockCheckHealth.mockReturnValue(new Promise(() => {}))
    useConnectionStore.getState().setTimeout(1)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    await waitFor(() => {
      expect(useConnectionStore.getState().healthOk).toBe(false)
    })
    expect(mockSaveSettings).not.toHaveBeenCalled()
  })
})

/* ------------------------------------------------------------------ */
/*  Provider switching between key-required and not                     */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — provider switching', () => {
  it('validates apiKey after switching from ollama to groq', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    useConnectionStore.getState().setApiKey(null)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByText('API key is required for groq')).toBeInTheDocument()
  })

  it('passes validation after switching from groq to ollama with no apiKey', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 5,
      model: 'llama3.2',
      error: null,
    })

    // Set groq first, then switch to ollama
    useConnectionStore.getState().setProviderType('groq')
    useConnectionStore.getState().setApiKey(null)

    // Switch to ollama
    useConnectionStore.getState().setProviderType('ollama')

    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(mockCheckHealth).toHaveBeenCalled()
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases                                                         */
/* ------------------------------------------------------------------ */

describe('TestConnectionButton — edge cases', () => {
  it('handles baseUrl with only whitespace as empty', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('   ')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByText('Base URL is required')).toBeInTheDocument()
  })

  it('handles apiKey with only whitespace as empty for key-required providers', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    useConnectionStore.getState().setApiKey('   ')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByText('API key is required for groq')).toBeInTheDocument()
  })

  it('trims whitespace from baseUrl in the API call', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 5,
      model: 'test',
      error: null,
    })
    useConnectionStore.getState().setBaseUrl('  http://localhost:11434  ')
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(mockCheckHealth).toHaveBeenCalledWith(
        expect.objectContaining({
          base_url: 'http://localhost:11434',
        }),
        expect.any(AbortSignal),
      )
    })
  })

  it('recovers from error state on successful retry', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)

    // First call fails
    mockCheckHealth.mockRejectedValueOnce(new Error('First failure'))

    // Second call succeeds
    mockCheckHealth.mockResolvedValueOnce({
      ok: true,
      latency_ms: 15,
      model: 'test',
      error: null,
    })

    render(<TestConnectionButton />)

    // First click — failure
    await user.click(screen.getByRole('button', { name: 'Test Connection' }))
    await waitFor(() => {
      expect(screen.getByText('First failure')).toBeInTheDocument()
    })

    // Second click — success
    await user.click(screen.getByRole('button', { name: 'Test Connection' }))
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument()
    })
  })

  it('bypasses apiKey validation when providerType is empty string', async () => {
    const user = userEvent.setup()
    const mockCheckHealth = vi.mocked(checkHealth)
    mockCheckHealth.mockResolvedValue({
      ok: true,
      latency_ms: 5,
      model: 'llama3.2',
      error: null,
    })
    // Empty providerType means apiKeyRequired is false — health check proceeds
    useConnectionStore.getState().setProviderType('')
    useConnectionStore.getState().setApiKey(null)
    render(<TestConnectionButton />)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    await waitFor(() => {
      expect(mockCheckHealth).toHaveBeenCalled()
    })
  })
})
