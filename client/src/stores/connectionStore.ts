/** Connection state — LLM provider configuration with persist middleware. */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface ConnectionState {
  /** Base URL of the LLM provider. */
  baseUrl: string
  /** Model name to use. */
  model: string
  /** Provider type (ollama, groq, openrouter, etc.). */
  providerType: string
  /** Optional API key. */
  apiKey: string | null
  /** Whether a health check is in progress. */
  checking: boolean
  /** Health check result. */
  healthOk: boolean | null
  /** Health check error message. */
  healthError: string | null
  /** Latency from the last health check in ms. */
  latencyMs: number | null

  // Agent-specific generation settings
  dm_max_tokens: number
  dm_temperature: number
  dm_timeout: number
  npc_max_tokens: number
  npc_temperature: number
  npc_timeout: number
  summarizer_max_tokens: number
  summarizer_temperature: number
  summarizer_timeout: number

  // Provider-level settings
  timeout: number
  max_tokens: number | null
  temperature: number | null

  // NPC / summarizer toggles
  npcEnabled: boolean
  summarizerEnabled: boolean

  // Connection status
  connectionTested: boolean

  // Models list (populated after fetchModels())
  models: string[]

  // General loading / error
  loading: boolean
  error: string | null
}

export interface ConnectionActions {
  setBaseUrl: (url: string) => void
  setModel: (model: string) => void
  setProviderType: (type: string) => void
  setApiKey: (key: string | null) => void
  setChecking: (checking: boolean) => void
  setHealthResult: (ok: boolean, latencyMs: number | null, error: string | null) => void
  setTimeout: (timeout: number) => void
  setMaxTokens: (maxTokens: number | null) => void
  setTemperature: (temperature: number | null) => void
  setNpcEnabled: (enabled: boolean) => void
  setSummarizerEnabled: (enabled: boolean) => void
  setConnectionTested: (tested: boolean) => void
  setModels: (models: string[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setSettings: (settings: Partial<ConnectionState>) => void
  reset: () => void
}

export type ConnectionStore = ConnectionState & ConnectionActions

const initialState: ConnectionState = {
  baseUrl: 'http://localhost:11434',
  model: 'llama3.2',
  providerType: 'ollama',
  apiKey: null,
  checking: false,
  healthOk: null,
  healthError: null,
  latencyMs: null,

  // Agent-specific defaults (mirroring backend _DEFAULT_SETTINGS)
  dm_max_tokens: 16000,
  dm_temperature: 0.8,
  dm_timeout: 120,
  npc_max_tokens: 1024,
  npc_temperature: 0.7,
  npc_timeout: 60,
  summarizer_max_tokens: 16000,
  summarizer_temperature: 0.7,
  summarizer_timeout: 120,

  // Provider-level defaults
  timeout: 300,
  max_tokens: null,
  temperature: null,

  // Toggle defaults
  npcEnabled: true,
  summarizerEnabled: true,

  // Status defaults
  connectionTested: false,
  models: [],
  loading: false,
  error: null,
}

export const useConnectionStore = create<ConnectionStore>()(
  persist(
    (set) => ({
      ...initialState,
      setBaseUrl: (baseUrl) => set({ baseUrl }),
      setModel: (model) => set({ model }),
      setProviderType: (providerType) => set({ providerType }),
      setApiKey: (apiKey) => set({ apiKey }),
      setChecking: (checking) => set({ checking }),
      setHealthResult: (ok, latencyMs, healthError) =>
        set({ healthOk: ok, latencyMs, healthError, checking: false }),
      setTimeout: (timeout) => set({ timeout }),
      setMaxTokens: (maxTokens) => set({ max_tokens: maxTokens }),
      setTemperature: (temperature) => set({ temperature }),
      setNpcEnabled: (npcEnabled) => set({ npcEnabled }),
      setSummarizerEnabled: (summarizerEnabled) => set({ summarizerEnabled }),
      setConnectionTested: (connectionTested) => set({ connectionTested }),
      setModels: (models) => set({ models }),
      setLoading: (loading) => set({ loading }),
      setError: (error) => set({ error }),
      setSettings: (settings) => set(settings),
      reset: () => set(initialState),
    }),
    {
      name: 'rpg-connection',
      partialize: (state) => ({
        baseUrl: state.baseUrl,
        model: state.model,
        providerType: state.providerType,
        apiKey: state.apiKey,
        timeout: state.timeout,
        max_tokens: state.max_tokens,
        temperature: state.temperature,
        dm_max_tokens: state.dm_max_tokens,
        dm_temperature: state.dm_temperature,
        dm_timeout: state.dm_timeout,
        npc_max_tokens: state.npc_max_tokens,
        npc_temperature: state.npc_temperature,
        npc_timeout: state.npc_timeout,
        summarizer_max_tokens: state.summarizer_max_tokens,
        summarizer_temperature: state.summarizer_temperature,
        summarizer_timeout: state.summarizer_timeout,
        npcEnabled: state.npcEnabled,
        summarizerEnabled: state.summarizerEnabled,
      }),
    },
  ),
)
