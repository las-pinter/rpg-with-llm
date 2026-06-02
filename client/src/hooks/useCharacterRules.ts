/** Hook to fetch character creation rules on mount and populate the store. */

import { useEffect, useRef } from 'react'
import { useCharacterStore } from '../stores/characterStore'
import { getCharacterRules } from '../api/endpoints'

export function useCharacterRules() {
  const setRules = useCharacterStore((s) => s.setRules)
  const setRulesLoading = useCharacterStore((s) => s.setRulesLoading)
  const setRulesError = useCharacterStore((s) => s.setRulesError)
  const initDefaults = useCharacterStore((s) => s.initDefaults)
  const rulesLoading = useCharacterStore((s) => s.rulesLoading)
  const rulesError = useCharacterStore((s) => s.rulesError)

  // Prevents double-fetch in React Strict Mode
  const fetchedRef = useRef(false)

  useEffect(() => {
    if (fetchedRef.current) return
    fetchedRef.current = true

    // Guard against re-entrant fetch if another effect already started
    if (useCharacterStore.getState().rulesLoading) return

    let cancelled = false

    setRulesLoading(true)
    setRulesError(null)

    getCharacterRules()
      .then((response) => {
        if (cancelled) return
        if (response.ok) {
          setRules(response.rules)
          // Initialise defaults after rules are set
          initDefaults()
        } else {
          setRulesError('Failed to load character rules')
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setRulesError(
          err instanceof Error ? err.message : 'Failed to load character rules',
        )
      })
      .finally(() => {
        if (!cancelled) {
          setRulesLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
    // Intentionally runs once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { loading: rulesLoading, error: rulesError }
}
