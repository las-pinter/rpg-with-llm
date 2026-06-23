/**
 * ManualMode — point-buy character creation form.
 *
 * Traditional character creation: enter name, pick class, assign ability
 * scores via point-buy, write appearance and backstory, then POST to the
 * create-character endpoint. On success, stores the character and switches
 * creationMode to 'review'.
 */

import { useState, useCallback } from 'react'
import { useCharacterStore } from '../../stores/characterStore'
import { createCharacter } from '../../api/endpoints'
import type { CreateCharacterParams } from '../../api/endpoints'
import ClassSelector from './ClassSelector'
import AbilityGrid from './AbilityGrid'
import GearSelector from './GearSelector'
import styles from './ManualMode.module.css'

export default function ManualMode() {
  // ------------------------------------------------------------------
  // Store reads — granular selectors
  // ------------------------------------------------------------------
  const manualName = useCharacterStore((s) => s.manualName)
  const manualAppearance = useCharacterStore((s) => s.manualAppearance)
  const manualBackstory = useCharacterStore((s) => s.manualBackstory)
  const abilities = useCharacterStore((s) => s.abilities)
  const selectedClass = useCharacterStore((s) => s.selectedClass)
  const rules = useCharacterStore((s) => s.rules)

  // Store actions
  const setManualName = useCharacterStore((s) => s.setManualName)
  const setManualAppearance = useCharacterStore((s) => s.setManualAppearance)
  const setManualBackstory = useCharacterStore((s) => s.setManualBackstory)
  const setGeneratedCharacter = useCharacterStore((s) => s.setGeneratedCharacter)
  const setCreationMode = useCharacterStore((s) => s.setCreationMode)

  // ------------------------------------------------------------------
  // Local state
  // ------------------------------------------------------------------
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ------------------------------------------------------------------
  // Create handler
  // ------------------------------------------------------------------

  const handleCreate = useCallback(async () => {
    setError(null)

    const trimmedName = manualName.trim()
    if (!trimmedName) {
      setError('Please enter a character name.')
      return
    }

    setCreating(true)

    const gearItems = Object.values(useCharacterStore.getState().selectedGear)

    const params: CreateCharacterParams = {
      name: trimmedName,
      character_class: selectedClass,
      abilities: { ...abilities },
      inventory: gearItems,
      equipped_items: gearItems.map((item) => item.id),
    }

    const trimmedAppearance = manualAppearance.trim()
    if (trimmedAppearance) {
      params.appearance = trimmedAppearance
    }

    const trimmedBackstory = manualBackstory.trim()
    if (trimmedBackstory) {
      params.backstory = trimmedBackstory
    }

    try {
      const response = await createCharacter(params)
      if (response.ok) {
        setGeneratedCharacter(response.character)
        setCreationMode('review')
      } else {
        setError('Failed to create character — unexpected response.')
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Unknown error creating character.'
      setError(message)
    } finally {
      setCreating(false)
    }
  }, [
    manualName,
    manualAppearance,
    manualBackstory,
    abilities,
    selectedClass,
    setGeneratedCharacter,
    setCreationMode,
  ])

  // ------------------------------------------------------------------
  // Guard: no rules loaded
  // ------------------------------------------------------------------

  if (!rules) {
    return (
      <div className={styles.wrapper}>
        <p className={styles.emptyState}>
          No character creation rules loaded. Check your connection and try again.
        </p>
      </div>
    )
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div className={styles.wrapper}>
      {/* ---- Character Name ---- */}
      <div className={styles.fieldRow}>
        <label className={styles.fieldLabel} htmlFor="manual-name">
          Character Name
        </label>
        <input
          id="manual-name"
          className={styles.fieldInput}
          type="text"
          value={manualName}
          onChange={(e) => setManualName(e.target.value)}
          placeholder="Enter your hero&rsquo;s name…"
          aria-required="true"
        />
      </div>

      {/* ---- Class Selector ---- */}
      <div className={styles.section}>
        <ClassSelector />
      </div>

      {/* ---- Ability Scores ---- */}
      <AbilityGrid />

      {/* ---- Starting Gear ---- */}
      <div className={styles.section}>
        <GearSelector characterClass={selectedClass} />
      </div>

      {/* ---- Appearance ---- */}
      <div className={styles.fieldRow}>
        <label className={styles.fieldLabel} htmlFor="manual-appearance">
          Appearance
        </label>
        <textarea
          id="manual-appearance"
          className={styles.fieldTextarea}
          value={manualAppearance}
          onChange={(e) => setManualAppearance(e.target.value)}
          placeholder="Describe your character&rsquo;s appearance…"
          rows={3}
        />
      </div>

      {/* ---- Backstory ---- */}
      <div className={styles.fieldRow}>
        <label className={styles.fieldLabel} htmlFor="manual-backstory">
          Backstory
        </label>
        <textarea
          id="manual-backstory"
          className={styles.fieldTextarea}
          value={manualBackstory}
          onChange={(e) => setManualBackstory(e.target.value)}
          placeholder="Write your character&rsquo;s backstory…"
          rows={4}
        />
      </div>

      {/* ---- Create Button ---- */}
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.createBtn}
          onClick={handleCreate}
          disabled={creating}
          aria-label="Create character"
        >
          {creating ? (
            <>
              <span className={styles.spinner} aria-hidden="true" />
              Creating&hellip;
            </>
          ) : (
            'Create Character'
          )}
        </button>
      </div>

      {/* ---- Error Banner ---- */}
      {error && (
        <div className={styles.errorBanner} role="alert">
          <span className={styles.errorIcon} aria-hidden="true">
            &#x26A0;&#xFE0F;
          </span>
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}
