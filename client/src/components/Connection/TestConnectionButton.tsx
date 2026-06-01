/**
 * TestConnectionButton — validates input, calls health API, shows status.
 *
 * Renders a "Test Connection" button that:
 * 1. Validates baseUrl (required) and apiKey (required for remote providers)
 * 2. Calls /api/health with an AbortController timeout
 * 3. On success: sets health result, marks connection as tested, auto-saves settings
 * 4. On failure: sets health error
 * 5. Displays ConnectionStatus below the button
 */

import { useCallback } from 'react'
import { useConnectionStore } from '../../stores/connectionStore'
import { checkHealth, saveSettings } from '../../api/endpoints'
import ConnectionStatus from './ConnectionStatus'
import styles from './TestConnectionButton.module.css'

/** Providers that work without an API key (local inference). */
const PROVIDERS_WITHOUT_API_KEY = ['ollama', 'llama.cpp']

export default function TestConnectionButton() {
  const checking = useConnectionStore((state) => state.checking)

  const handleTestConnection = useCallback(async () => {
    const store = useConnectionStore.getState()

    // ---- Validation ----

    if (!store.baseUrl || store.baseUrl.trim() === '') {
      store.setHealthResult(false, null, 'Base URL is required')
      store.setConnectionTested(false)
      return
    }

    const apiKeyRequired =
      store.providerType !== '' &&
      !PROVIDERS_WITHOUT_API_KEY.includes(store.providerType)
    if (apiKeyRequired && (!store.apiKey || store.apiKey.trim() === '')) {
      store.setHealthResult(
        false,
        null,
        `API key is required for ${store.providerType}`,
      )
      store.setConnectionTested(false)
      return
    }

    // ---- Prepare timeout via AbortController ----

    const timeoutSeconds = store.timeout ?? 300
    const timeoutMs = timeoutSeconds * 1000
    const controller = new AbortController()
    const timerId = setTimeout(() => controller.abort(), timeoutMs)

    store.setChecking(true)

    // ---- Health check with timeout race ----

    try {
      const response = await Promise.race([
        checkHealth({
          base_url: store.baseUrl.trim(),
          model: store.model,
          ...(store.apiKey ? { api_key: store.apiKey } : {}),
          ...(store.providerType ? { provider_type: store.providerType } : {}),
        }),
        new Promise<never>((_, reject) => {
          controller.signal.addEventListener(
            'abort',
            () => {
              reject(new Error(`Request timed out after ${timeoutSeconds}s`))
            },
            { once: true },
          )
        }),
      ])

      clearTimeout(timerId)

      if (response.ok) {
        store.setHealthResult(true, response.latency_ms, null)
        store.setConnectionTested(true)

        // Auto-save settings on success (non-fatal if save fails)
        try {
          await saveSettings({
            base_url: store.baseUrl.trim(),
            model: store.model,
            provider_type: store.providerType,
            api_key: store.apiKey ?? null,
            timeout: store.timeout,
            max_tokens: store.max_tokens,
            temperature: store.temperature,
            dm_max_tokens: store.dm_max_tokens,
            dm_temperature: store.dm_temperature,
            dm_timeout: store.dm_timeout,
            npc_max_tokens: store.npc_max_tokens,
            npc_temperature: store.npc_temperature,
            npc_timeout: store.npc_timeout,
            summarizer_max_tokens: store.summarizer_max_tokens,
            summarizer_temperature: store.summarizer_temperature,
            summarizer_timeout: store.summarizer_timeout,
          })
        } catch {
          // Save is secondary — connection worked, this is non-fatal
        }
      } else {
        store.setHealthResult(false, null, response.error ?? 'Connection failed')
        store.setConnectionTested(false)
      }
    } catch (err) {
      clearTimeout(timerId)
      const message =
        err instanceof Error
          ? err.message
          : typeof err === 'object' && err !== null && 'error' in err
            ? String((err as Record<string, unknown>).error)
            : 'Connection failed'
      store.setHealthResult(false, null, message)
      store.setConnectionTested(false)
    } finally {
      store.setChecking(false)
    }
  }, [])

  return (
    <div className={styles.wrapper}>
      <button
        type="button"
        className={styles.button}
        onClick={handleTestConnection}
        disabled={checking}
      >
        {checking ? 'Testing...' : 'Test Connection'}
      </button>
      <ConnectionStatus />
    </div>
  )
}
