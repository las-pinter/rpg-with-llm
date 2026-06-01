/** Hook to fetch, populate, and persist LLM provider settings via the backend API. */

import { useEffect, useRef } from 'react'
import { useConnectionStore } from '../stores/connectionStore'
import { getSettings, saveSettings as apiSaveSettings } from '../api/endpoints'
import type { Settings } from '../api/types'
import type { ConnectionState } from '../stores/connectionStore'

/**
 * Map a backend Settings object (all snake_case) to store fields.
 *
 * Most keys match directly, but a few store fields use camelCase
 * (baseUrl, providerType, apiKey) while the backend uses snake_case.
 */
function mapSettingsToStore(settings: Settings): Partial<ConnectionState> {
  return {
    baseUrl: settings.base_url,
    model: settings.model,
    providerType: settings.provider_type,
    apiKey: settings.api_key,
    dm_max_tokens: settings.dm_max_tokens,
    dm_temperature: settings.dm_temperature,
    dm_timeout: settings.dm_timeout,
    npc_max_tokens: settings.npc_max_tokens,
    npc_temperature: settings.npc_temperature,
    npc_timeout: settings.npc_timeout,
    summarizer_max_tokens: settings.summarizer_max_tokens,
    summarizer_temperature: settings.summarizer_temperature,
    summarizer_timeout: settings.summarizer_timeout,
    timeout: settings.timeout,
    max_tokens: settings.max_tokens,
    temperature: settings.temperature,
  }
}

/**
 * Extract settings-relevant fields from store state, mapping camelCase
 * store keys back to the snake_case keys the backend expects.
 */
function extractSettingsFromStore(state: ConnectionState): Record<string, unknown> {
  return {
    base_url: state.baseUrl,
    model: state.model,
    provider_type: state.providerType,
    api_key: state.apiKey,
    dm_max_tokens: state.dm_max_tokens,
    dm_temperature: state.dm_temperature,
    dm_timeout: state.dm_timeout,
    npc_max_tokens: state.npc_max_tokens,
    npc_temperature: state.npc_temperature,
    npc_timeout: state.npc_timeout,
    summarizer_max_tokens: state.summarizer_max_tokens,
    summarizer_temperature: state.summarizer_temperature,
    summarizer_timeout: state.summarizer_timeout,
    timeout: state.timeout,
    max_tokens: state.max_tokens,
    temperature: state.temperature,
  }
}

export function useSettings() {
  const setSettings = useConnectionStore((s) => s.setSettings)
  const setLoading = useConnectionStore((s) => s.setLoading)
  const setError = useConnectionStore((s) => s.setError)
  const loading = useConnectionStore((s) => s.loading)
  const error = useConnectionStore((s) => s.error)

  // Prevents double-fetch in React Strict Mode
  const fetchedRef = useRef(false)

  useEffect(() => {
    if (fetchedRef.current) return
    fetchedRef.current = true

    // Guard against re-entrant fetch if another effect already started
    if (useConnectionStore.getState().loading) return

    let cancelled = false

    setLoading(true)
    setError(null)

    getSettings()
      .then((response) => {
        if (cancelled) return
        if (response.ok) {
          setSettings(mapSettingsToStore(response.settings))
        } else {
          setError('Failed to load settings')
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load settings')
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
    // Intentionally runs once on mount — getSettings is a module-level static import
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const saveSettings = async (): Promise<void> => {
    const state = useConnectionStore.getState()
    const settings = extractSettingsFromStore(state)
    const response = await apiSaveSettings(settings)
    if (!response.ok) {
      throw new Error('Failed to save settings')
    }
  }

  return { loading, error, saveSettings }
}
