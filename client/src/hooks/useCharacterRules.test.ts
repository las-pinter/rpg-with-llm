/**
 * useCharacterRules tests — fetch on mount, error handling, store population.
 *
 * Covers: initial fetch, store population, initDefaults on success,
 * re-entrant guard, API error, network error, loading states,
 * unmount cancellation, and non-Error throws.
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'

// Mock API module before any imports that use it
vi.mock('../api/endpoints', () => ({
  getCharacterRules: vi.fn(),
}))

import { getCharacterRules } from '../api/endpoints'
import { useCharacterStore } from '../stores/characterStore'
import { useCharacterRules } from './useCharacterRules'
import type { CharacterRulesResponse } from '../api/types'

/** Reset the character store to defaults before each test. */
function resetStore() {
  useCharacterStore.getState().reset()
}

const mockRules = {
  valid_classes: ['Fighter', 'Rogue', 'Mage', 'Cleric'],
  standard_abilities: ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
  class_templates: {
    Cleric: {
      abilities: { STR: 13, DEX: 8, CON: 14, INT: 10, WIS: 15, CHA: 12 },
    },
  },
  point_buy: {
    costs: {
      '8': 0, '9': 1, '10': 2, '11': 3,
      '12': 4, '13': 5, '14': 7, '15': 9,
    },
    max_points: 27,
    min_score: 8,
    max_score: 15,
  },
  assisted_creation_questions: [
    'Where were you born?',
    'What drove you to adventure?',
  ],
}



const mockApiResponse: CharacterRulesResponse = {
  ok: true,
  rules: mockRules,
}

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

describe('useCharacterRules — initial fetch', () => {
  it('fetches rules on mount and populates store', async () => {
    vi.mocked(getCharacterRules).mockResolvedValue(mockApiResponse)

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      const state = useCharacterStore.getState()
      expect(state.rules).not.toBeNull()
    })

    const state = useCharacterStore.getState()
    expect(state.rules?.valid_classes).toEqual(mockRules.valid_classes)
    expect(state.rules?.standard_abilities).toEqual(mockRules.standard_abilities)
    expect(state.rulesLoading).toBe(false)
    expect(state.rulesError).toBeNull()
  })

  it('calls initDefaults after rules are loaded', async () => {
    vi.mocked(getCharacterRules).mockResolvedValue({
      ok: true,
      rules: {
        ...mockRules,
        // Put Cleric first so initDefaults picks the Cleric template
        valid_classes: ['Cleric', 'Fighter', 'Mage', 'Rogue'],
      },
    } as CharacterRulesResponse)

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      const state = useCharacterStore.getState()
      // initDefaults should have been called, setting abilities
      // from the first class template (Cleric)
      expect(state.abilities).toEqual({
        STR: 13, DEX: 8, CON: 14, INT: 10, WIS: 15, CHA: 12,
      })
    })

    const state = useCharacterStore.getState()
    expect(state.selectedClass).toBe('Cleric')
    expect(state.storyAnswers).toHaveLength(2)
    expect(state.currentQuestion).toBe(0)
    expect(state.creationMode).toBe('campfire')
  })

  it('clears any previous error before fetching', async () => {
    useCharacterStore.getState().setRulesError('stale error')
    vi.mocked(getCharacterRules).mockResolvedValue(mockApiResponse)

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      expect(useCharacterStore.getState().rulesError).toBeNull()
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Fetch guards — double-fetch and re-entrant protection            */
/* ------------------------------------------------------------------ */

describe('useCharacterRules — fetch guards', () => {
  it('fetches rules exactly once during mount lifecycle', async () => {
    vi.mocked(getCharacterRules).mockResolvedValue(mockApiResponse)

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      expect(useCharacterStore.getState().rulesLoading).toBe(false)
    })

    expect(getCharacterRules).toHaveBeenCalledTimes(1)
  })

  it('does not fetch if store is already loading (re-entrant guard)', async () => {
    vi.mocked(getCharacterRules).mockResolvedValue(mockApiResponse)

    act(() => {
      useCharacterStore.getState().setRulesLoading(true)
    })

    renderHook(() => useCharacterRules())

    // Small delay to let any effect run
    await new Promise((r) => setTimeout(r, 50))

    expect(getCharacterRules).not.toHaveBeenCalled()
  })
})

/* ------------------------------------------------------------------ */
/*  Loading states                                                    */
/* ------------------------------------------------------------------ */

describe('useCharacterRules — loading states', () => {
  it('sets rulesLoading to true during fetch', async () => {
    const neverResolve: Promise<never> = new Promise(() => {
      /* never resolves */
    })
    vi.mocked(getCharacterRules).mockReturnValue(neverResolve)

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      expect(useCharacterStore.getState().rulesLoading).toBe(true)
    })
  })

  it('sets rulesLoading to false after fetch completes', async () => {
    vi.mocked(getCharacterRules).mockResolvedValue(mockApiResponse)

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      expect(useCharacterStore.getState().rulesLoading).toBe(false)
    })
  })

  it('returns loading and error from the hook', async () => {
    vi.mocked(getCharacterRules).mockResolvedValue(mockApiResponse)

    const { result } = renderHook(() => useCharacterRules())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBeNull()
  })
})

/* ------------------------------------------------------------------ */
/*  Error handling                                                   */
/* ------------------------------------------------------------------ */

describe('useCharacterRules — error handling', () => {
  it('handles API ok:false response gracefully', async () => {
    vi.mocked(getCharacterRules).mockResolvedValue({
      ok: false,
      rules: mockRules,
    } as CharacterRulesResponse)

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      expect(useCharacterStore.getState().rulesError).toBe(
        'Failed to load character rules',
      )
    })
    expect(useCharacterStore.getState().rulesLoading).toBe(false)
    // Rules should not be set when API returns ok:false
    expect(useCharacterStore.getState().rules).toBeNull()
  })

  it('handles network error gracefully', async () => {
    vi.mocked(getCharacterRules).mockRejectedValue(
      new Error('Network failure'),
    )

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      expect(useCharacterStore.getState().rulesError).toBe('Network failure')
    })
    expect(useCharacterStore.getState().rulesLoading).toBe(false)
  })

  it('handles non-Error thrown values gracefully', async () => {
    vi.mocked(getCharacterRules).mockRejectedValue('raw string error')

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      expect(useCharacterStore.getState().rulesError).toBe(
        'Failed to load character rules',
      )
    })
    expect(useCharacterStore.getState().rulesLoading).toBe(false)
  })

  it('does not update state after unmount (cancelled flag)', async () => {
    const differentRules = {
      ...mockRules,
      valid_classes: ['Should'],
    }
    vi.mocked(getCharacterRules).mockResolvedValue({
      ok: true,
      rules: differentRules,
    } as CharacterRulesResponse)

    const { unmount } = renderHook(() => useCharacterRules())
    unmount()

    // Wait for any pending promises to settle
    await vi.waitFor(() => {
      // Store should still have defaults — not the mock values — because
      // the cancelled flag prevented the .then() from setting rules.
      // rulesLoading stays true because the cancelled flag also
      // prevents the .finally() handler from clearing it.
      expect(useCharacterStore.getState().rules).toBeNull()
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases                                                        */
/* ------------------------------------------------------------------ */

describe('useCharacterRules — edge cases', () => {
  it('handles rules response with empty arrays without crashing', async () => {
    vi.mocked(getCharacterRules).mockResolvedValue({
      ok: true,
      rules: {
        valid_classes: [],
        standard_abilities: [],
        class_templates: {},
        point_buy: {
          costs: {},
          max_points: 27,
          min_score: 8,
          max_score: 15,
        },
        assisted_creation_questions: [],
      },
    } as CharacterRulesResponse)

    renderHook(() => useCharacterRules())

    await waitFor(() => {
      expect(useCharacterStore.getState().rulesLoading).toBe(false)
    })

    // initDefaults() with empty rules should set abilities to {}
    // (standard_abilities is empty, so no abilities are initialized),
    // selectedClass would be '' (no valid_classes)
    expect(useCharacterStore.getState().abilities).toEqual({})
    expect(useCharacterStore.getState().selectedClass).toBe('')
    expect(useCharacterStore.getState().remainingPoints).toBe(27)
    expect(useCharacterStore.getState().storyAnswers).toEqual([])
  })
})
