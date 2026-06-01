/**
 * ModelSelector — fetch models from provider and select/type a model name.
 *
 * Renders a "Fetch Models" button, a model <select> dropdown populated
 * from the fetched list, and a text <input> for manual entry. Both the
 * select and input control the same `model` field in the connection store.
 */

import { useState, useCallback } from 'react'
import { useConnectionStore } from '../../stores/connectionStore'
import { listModels } from '../../api/endpoints'
import styles from './ModelSelector.module.css'

export default function ModelSelector() {
  const model = useConnectionStore((state) => state.model)
  const models = useConnectionStore((state) => state.models)
  const providerType = useConnectionStore((state) => state.providerType)
  const baseUrl = useConnectionStore((state) => state.baseUrl)
  const apiKey = useConnectionStore((state) => state.apiKey)
  const loading = useConnectionStore((state) => state.loading)
  const error = useConnectionStore((state) => state.error)

  const setModel = useConnectionStore((state) => state.setModel)
  const setModels = useConnectionStore((state) => state.setModels)
  const setLoading = useConnectionStore((state) => state.setLoading)
  const setError = useConnectionStore((state) => state.setError)

  const [fetchedOnce, setFetchedOnce] = useState(false)

  const handleFetchModels = useCallback(async () => {
    if (!baseUrl.trim()) {
      setError('Base URL is required to fetch models')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await listModels({
        base_url: baseUrl,
        model,
        ...(apiKey ? { api_key: apiKey } : {}),
        ...(providerType ? { provider_type: providerType } : {}),
      })

      if (response.ok && response.models) {
        setModels(response.models.map((m) => m.id))
        setFetchedOnce(true)
      } else {
        setError(response.error ?? 'Failed to fetch models')
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'An unexpected error occurred',
      )
    } finally {
      setLoading(false)
    }
  }, [baseUrl, model, apiKey, providerType, setModels, setLoading, setError])

  function handleSelectChange(e: React.ChangeEvent<HTMLSelectElement>) {
    setModel(e.target.value)
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    setModel(e.target.value)
  }

  const hasModels = models.length > 0
  const showEmptyResult = fetchedOnce && !loading && models.length === 0

  return (
    <div className={styles.container}>
      {/* ---- Fetch Button ---- */}
      <div className={styles.fetchRow}>
        <button
          type="button"
          className={styles.fetchButton}
          onClick={handleFetchModels}
          disabled={loading}
        >
          {loading ? 'Fetching...' : 'Fetch Models'}
        </button>
      </div>

      {/* ---- Error ---- */}
      {error && (
        <div className={styles.error} role="alert">
          {error}
        </div>
      )}

      {/* ---- Model Select ---- */}
      <div className={styles.field}>
        <label className={styles.label} htmlFor="model-select">
          Model
        </label>
        {hasModels ? (
          <select
            id="model-select"
            className={styles.select}
            value={model}
            onChange={handleSelectChange}
          >
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        ) : (
          <select
            id="model-select"
            className={styles.select}
            value=""
            disabled
          >
            <option value="">No models loaded</option>
          </select>
        )}
      </div>

      {/* ---- Manual model input ---- */}
      <div className={styles.field}>
        <label className={styles.label} htmlFor="model-input">
          Or type a model name
        </label>
        <input
          id="model-input"
          className={styles.input}
          type="text"
          value={model}
          onChange={handleInputChange}
          placeholder="e.g. llama3.2"
        />
      </div>

      {/* ---- Empty result message ---- */}
      {showEmptyResult && (
        <p className={styles.status}>No models found.</p>
      )}
    </div>
  )
}
