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
}

export interface ConnectionActions {
  setBaseUrl: (url: string) => void
  setModel: (model: string) => void
  setProviderType: (type: string) => void
  setApiKey: (key: string | null) => void
  setChecking: (checking: boolean) => void
  setHealthResult: (ok: boolean, latencyMs: number | null, error: string | null) => void
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
      reset: () => set(initialState),
    }),
    {
      name: 'rpg-connection',
      partialize: (state) => ({
        baseUrl: state.baseUrl,
        model: state.model,
        providerType: state.providerType,
        apiKey: state.apiKey,
      }),
    }
  )
)
