/**
 * GearSelector — starting gear selection during character creation.
 *
 * Fetches gear options from the backend for a given character class and
 * displays each category (weapon, armor, pack) with radio-button-like
 * choices. Selections are stored in the character store so they can be
 * included in the final create / generate call.
 */

import { useState, useEffect } from 'react'
import { useCharacterStore } from '../../stores/characterStore'
import { getStartingGear } from '../../api/endpoints'
import type { StartingGearResponse } from '../../api/endpoints'
import { ItemType, type Item } from '../../api/types'
import styles from './GearSelector.module.css'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Icons for each gear category key. */
const CATEGORY_ICONS: Record<string, string> = {
  weapon: '⚔️',
  armor: '🛡️',
  pack: '📦',
}

/** Human-readable label for each category. */
const CATEGORY_LABELS: Record<string, string> = {
  weapon: 'Choose Your Weapon',
  armor: 'Choose Your Armor',
  pack: 'Choose Your Pack',
}

/** Subtitle hint for each category (what stat to compare). */
const CATEGORY_HINTS: Record<string, string> = {
  weapon: 'Damage & Weight',
  armor: 'Armor Class & Weight',
  pack: 'Capacity & Value',
}

/** Extract a human-readable stat line from an item's properties. */
function itemStats(item: Item): string {
  const props = item.properties ?? {}
  const parts: string[] = []

  // Weapon damage
  if (item.item_type === ItemType.WEAPON && props.damage) {
    parts.push(String(props.damage))
  }

  // Armor class
  if (item.item_type === ItemType.ARMOR && props.ac) {
    parts.push(`AC ${props.ac}`)
  }

  // Weight (always show)
  parts.push(`${item.weight} lb`)

  // Value / gold for packs
  if (item.value > 0) {
    parts.push(`${item.value} gp`)
  }

  return parts.join(', ')
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface GearSelectorProps {
  /** The character class to fetch gear options for. */
  characterClass: string
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function GearSelector({ characterClass }: GearSelectorProps) {
  // ------------------------------------------------------------------
  // Store reads
  // ------------------------------------------------------------------
  const selectedGear = useCharacterStore((s) => s.selectedGear)
  const setSelectedGear = useCharacterStore((s) => s.setSelectedGear)

  // ------------------------------------------------------------------
  // Local state
  // ------------------------------------------------------------------
  const [gearOptions, setGearOptions] = useState<Record<string, Item[]> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ------------------------------------------------------------------
  // Fetch gear options when class changes
  // ------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false

    async function fetchGear() {
      if (!characterClass) return

      setLoading(true)
      setError(null)

      try {
        const response: StartingGearResponse = await getStartingGear(characterClass)
        if (cancelled) return

        if (response.ok && response.gear_options) {
          setGearOptions(response.gear_options)

          // Auto-select first option in each category if nothing selected yet
          const currentGear = useCharacterStore.getState().selectedGear
          const newSelections = { ...currentGear }
          for (const [category, items] of Object.entries(response.gear_options)) {
            if (items.length > 0 && !newSelections[category]) {
              newSelections[category] = items[0]
            }
          }
          useCharacterStore.getState().setState({ selectedGear: newSelections })
        } else {
          setError(response.error ?? 'Failed to load gear options.')
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load gear options.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchGear()

    return () => {
      cancelled = true
    }
  }, [characterClass])

  // ------------------------------------------------------------------
  // Selection handler
  // ------------------------------------------------------------------
  function handleSelect(category: string, item: Item) {
    setSelectedGear(category, item)
  }

  // ------------------------------------------------------------------
  // Render: loading
  // ------------------------------------------------------------------
  if (loading) {
    return (
      <div className={styles.wrapper}>
        <div className={styles.loading}>
          <span className={styles.spinner} aria-hidden="true" />
          <span>Loading gear options&hellip;</span>
        </div>
      </div>
    )
  }

  // ------------------------------------------------------------------
  // Render: error
  // ------------------------------------------------------------------
  if (error) {
    return (
      <div className={styles.wrapper}>
        <p className={styles.error} role="alert">
          {error}
        </p>
      </div>
    )
  }

  // ------------------------------------------------------------------
  // Render: empty / no options
  // ------------------------------------------------------------------
  if (!gearOptions || Object.keys(gearOptions).length === 0) {
    return (
      <div className={styles.wrapper}>
        <p className={styles.empty}>No starting gear options available.</p>
      </div>
    )
  }

  // ------------------------------------------------------------------
  // Render: gear categories
  // ------------------------------------------------------------------
  return (
    <div className={styles.wrapper}>
      {Object.entries(gearOptions).map(([category, items]) => (
        <div key={category} className={styles.category}>
          {/* ---- Category header ---- */}
          <div className={styles.categoryHeader}>
            <span className={styles.categoryIcon} aria-hidden="true">
              {CATEGORY_ICONS[category] ?? '📜'}
            </span>
            <div>
              <span className={styles.categoryTitle}>
                {CATEGORY_LABELS[category] ?? category}
              </span>
              <span className={styles.categoryHint}>
                {CATEGORY_HINTS[category] ?? ''}
              </span>
            </div>
          </div>

          {/* ---- Item options ---- */}
          <div className={styles.optionsList} role="radiogroup" aria-label={CATEGORY_LABELS[category] ?? category}>
            {items.map((item) => {
              const isSelected = selectedGear[category]?.id === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  className={`${styles.option} ${isSelected ? styles.optionSelected : ''}`}
                  onClick={() => handleSelect(category, item)}
                >
                  <span className={styles.radioIndicator} aria-hidden="true">
                    {isSelected ? '●' : '○'}
                  </span>
                  <span className={styles.optionName}>{item.name}</span>
                  <span className={styles.optionStats}>{itemStats(item)}</span>
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
