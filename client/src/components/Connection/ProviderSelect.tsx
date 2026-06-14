/**
 * ProviderSelect — LLM provider configuration form group.
 *
 * Lets the user pick a provider type, set the base URL, and optionally
 * enter an API key with show/hide visibility toggle.
 */

import { useState } from 'react'
import { useConnectionStore } from '../../stores/connectionStore'
import styles from './ProviderSelect.module.css'

const PROVIDER_OPTIONS = [
  { value: 'ollama', label: 'Ollama' },
  { value: 'groq', label: 'Groq' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'unsloth', label: 'Unsloth' },
  { value: 'llama.cpp', label: 'llama.cpp' },
] as const

/** Providers that work without an API key (local inference). */
const PROVIDERS_WITHOUT_API_KEY = ['ollama', 'llama.cpp']

export default function ProviderSelect() {
  const providerType = useConnectionStore((state) => state.providerType)
  const baseUrl = useConnectionStore((state) => state.baseUrl)
  const apiKey = useConnectionStore((state) => state.apiKey)

  const [showApiKey, setShowApiKey] = useState(false)

  const apiKeyRequired = !PROVIDERS_WITHOUT_API_KEY.includes(providerType)

  function handleProviderChange(e: React.ChangeEvent<HTMLSelectElement>) {
    useConnectionStore.getState().setProviderType(e.target.value)
  }

  function handleBaseUrlChange(e: React.ChangeEvent<HTMLInputElement>) {
    useConnectionStore.getState().setBaseUrl(e.target.value)
  }

  function handleApiKeyChange(e: React.ChangeEvent<HTMLInputElement>) {
    useConnectionStore.getState().setApiKey(e.target.value || null)
  }

  function toggleApiKeyVisibility() {
    setShowApiKey((prev) => !prev)
  }

  return (
    <div className={styles.container}>
      {/* ---- Provider Type ---- */}
      <div className={styles.field}>
        <label className={styles.label} htmlFor="provider-type">
          Provider
        </label>
        <select
          id="provider-type"
          className={styles.select}
          value={providerType}
          onChange={handleProviderChange}
        >
          {PROVIDER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* ---- Base URL ---- */}
      <div className={styles.field}>
        <label className={styles.label} htmlFor="base-url">
          Base URL
        </label>
        <input
          id="base-url"
          className={styles.input}
          type="text"
          value={baseUrl}
          onChange={handleBaseUrlChange}
          placeholder="http://localhost:11434"
        />
      </div>

      {/* ---- API Key ---- */}
      <div className={styles.field}>
        <label className={styles.label} htmlFor="api-key">
          API Key
        </label>
        <div className={styles.apiKeyWrapper}>
          <input
            id="api-key"
            className={styles.apiKeyInput}
            type={showApiKey ? 'text' : 'password'}
            value={apiKey ?? ''}
            onChange={handleApiKeyChange}
            placeholder={
              apiKeyRequired ? 'Enter API key…' : 'Not required for this provider'
            }
            disabled={!apiKeyRequired}
          />
          {apiKeyRequired && (
            <button
              type="button"
              className={styles.toggleButton}
              onClick={toggleApiKeyVisibility}
              aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
              title={showApiKey ? 'Hide API key' : 'Show API key'}
            >
              {showApiKey ? (
                /* Eye-off icon */
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                /* Eye-open icon */
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          )}
        </div>
        {!apiKeyRequired && (
          <p className={styles.hint}>
            {providerType === 'ollama'
              ? 'Ollama runs locally — no API key needed.'
              : 'llama.cpp runs locally — no API key needed.'}
          </p>
        )}
      </div>
    </div>
  )
}
