/**
 * ReviewSheet — character sheet display with edit/regenerate/start actions.
 *
 * Shows the fully-constructed character with ability scores, stats, skills,
 * appearance (editable in edit mode), backstory (editable in edit mode),
 * and inventory. Provides Edit/Save toggle, Regenerate (re-calls generate
 * API), and Start Adventure (navigates to /game).
 */

import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCharacterStore } from '../../stores/characterStore'
import { useConnectionStore } from '../../stores/connectionStore'
import { generateCharacter } from '../../api/endpoints'
import type { GenerateCharacterParams } from '../../api/endpoints'
import styles from './ReviewSheet.module.css'

/** Maps ability keys to compact labels for the character sheet grid. */
const ABILITY_LABELS: Record<string, string> = {
  STR: 'STR',
  DEX: 'DEX',
  CON: 'CON',
  INT: 'INT',
  WIS: 'WIS',
  CHA: 'CHA',
  str: 'STR',
  dex: 'DEX',
  con: 'CON',
  int: 'INT',
  wis: 'WIS',
  cha: 'CHA',
}

export default function ReviewSheet() {
  const navigate = useNavigate()

  // ------------------------------------------------------------------
  // Store reads — granular selectors
  // ------------------------------------------------------------------
  const character = useCharacterStore((s) => s.generatedCharacter)
  const isEditing = useCharacterStore((s) => s.isEditing)
  const storyAnswers = useCharacterStore((s) => s.storyAnswers)
  const abilities = useCharacterStore((s) => s.abilities)
  const selectedClass = useCharacterStore((s) => s.selectedClass)

  // Store actions
  const setIsEditing = useCharacterStore((s) => s.setIsEditing)
  const setGeneratedCharacter = useCharacterStore((s) => s.setGeneratedCharacter)
  const setCurrentCharacter = useCharacterStore((s) => s.setCurrentCharacter)

  // Connection store (for regenerate provider config)
  const connBaseUrl = useConnectionStore((s) => s.baseUrl)
  const connModel = useConnectionStore((s) => s.model)
  const connProviderType = useConnectionStore((s) => s.providerType)
  const connApiKey = useConnectionStore((s) => s.apiKey)

  // ------------------------------------------------------------------
  // Local state
  // ------------------------------------------------------------------
  const [editBackstory, setEditBackstory] = useState('')
  const [editAppearance, setEditAppearance] = useState('')
  const [regenerating, setRegenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ------------------------------------------------------------------
  // Edit handlers
  // ------------------------------------------------------------------

  const handleEdit = useCallback(() => {
    if (!character) return
    setEditBackstory(character.backstory)
    setEditAppearance(character.appearance)
    setIsEditing(true)
  }, [character, setIsEditing])

  const handleSave = useCallback(() => {
    if (!character) return
    setGeneratedCharacter({
      ...character,
      backstory: editBackstory,
      appearance: editAppearance,
    })
    setIsEditing(false)
  }, [character, editBackstory, editAppearance, setGeneratedCharacter, setIsEditing])

  const handleCancelEdit = useCallback(() => {
    setIsEditing(false)
  }, [setIsEditing])

  // ------------------------------------------------------------------
  // Regenerate handler
  // ------------------------------------------------------------------

  const handleRegenerate = useCallback(async () => {
    if (!character) return
    setError(null)
    setRegenerating(true)

    // Build answers object from store
    const answersObj: Record<number, string> = {}
    storyAnswers.forEach((answer, idx) => {
      if (answer && answer.trim().length > 0) {
        answersObj[idx] = answer
      }
    })

    // Build provider config from connection store
    const provider: GenerateCharacterParams['provider'] = {
      base_url: connBaseUrl,
      model: connModel,
    }
    if (connProviderType) {
      provider.provider_type = connProviderType
    }
    if (connApiKey) {
      provider.api_key = connApiKey
    }

    const params: GenerateCharacterParams = {
      answers: answersObj,
      name: character.name,
      character_class: selectedClass || character.character_class,
      provider,
    }

    if (Object.keys(abilities).length > 0) {
      params.abilities = abilities
    }

    try {
      const response = await generateCharacter(params)
      if (response.ok) {
        setGeneratedCharacter(response.character)
        setIsEditing(false)
      } else {
        setError('Failed to regenerate character — unexpected response.')
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Unknown error regenerating character.'
      setError(message)
    } finally {
      setRegenerating(false)
    }
  }, [
    character,
    storyAnswers,
    selectedClass,
    abilities,
    connBaseUrl,
    connModel,
    connProviderType,
    connApiKey,
    setGeneratedCharacter,
  ])

  // ------------------------------------------------------------------
  // Start Adventure handler
  // ------------------------------------------------------------------

  const handleStartAdventure = useCallback(() => {
    if (character) {
      setCurrentCharacter(character)
    }
    navigate('/game')
  }, [navigate, character, setCurrentCharacter])

  // ------------------------------------------------------------------
  // Empty state
  // ------------------------------------------------------------------

  if (!character) {
    return (
      <div className={styles.wrapper}>
        <p className={styles.emptyState}>
          No character to review. Create one first!
        </p>
      </div>
    )
  }

  // ------------------------------------------------------------------
  // Derived data
  // ------------------------------------------------------------------

  const abilityEntries = Object.entries(character.abilities).filter(
    ([, value]) => typeof value === 'number',
  )

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div className={styles.wrapper}>
      {/* ---- Character Header ---- */}
      <div className={styles.header}>
        <h2 className={styles.charName}>{character.name}</h2>
        <span className={styles.charClass}>
          Lvl {character.level} {character.character_class}
        </span>
      </div>
      <hr className={styles.accentBar} />

      {/* ---- Ability Scores ---- */}
      <div className={styles.sectionTitle}>Ability Scores</div>
      <div className={styles.abilityGrid}>
        {abilityEntries.map(([key, value]) => {
          const label = ABILITY_LABELS[key] ?? key.toUpperCase()
          return (
            <div key={key} className={styles.abilityCard}>
              <span className={styles.abilityLabel}>{label}</span>
              <span className={styles.abilityValue}>{value}</span>
            </div>
          )
        })}
      </div>

      {/* ---- Stats Row ---- */}
      <div className={styles.statsRow}>
        <div className={styles.stat}>
          <span className={styles.statLabel}>HP</span>
          <span className={styles.statValue}>
            {character.hp}
            {character.max_hp !== character.hp && (
              <span className={styles.statMax}> / {character.max_hp}</span>
            )}
          </span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>AC</span>
          <span className={styles.statValue}>{character.ac}</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Gold</span>
          <span className={styles.statValue}>{character.gold}</span>
        </div>
      </div>

      {/* ---- Skills ---- */}
      {character.skills.length > 0 && (
        <>
          <div className={styles.sectionTitle}>Skills</div>
          <div className={styles.skillsRow}>
            {character.skills.map((skill) => (
              <span key={skill} className={styles.skillBadge}>
                {skill}
              </span>
            ))}
          </div>
        </>
      )}

      {/* ---- Appearance ---- */}
      <div className={styles.sectionTitle}>Appearance</div>
      {isEditing ? (
        <textarea
          className={styles.editTextarea}
          value={editAppearance}
          onChange={(e) => setEditAppearance(e.target.value)}
          aria-label="Edit appearance"
          rows={3}
        />
      ) : (
        <p className={styles.narrativeText}>
          {character.appearance || (
            <span className={styles.emptyHint}>No appearance described.</span>
          )}
        </p>
      )}

      {/* ---- Backstory ---- */}
      <div className={styles.sectionTitle}>Backstory</div>
      {isEditing ? (
        <textarea
          className={styles.editTextarea}
          value={editBackstory}
          onChange={(e) => setEditBackstory(e.target.value)}
          aria-label="Edit backstory"
          rows={4}
        />
      ) : (
        <p className={styles.narrativeText}>
          {character.backstory || (
            <span className={styles.emptyHint}>No backstory written.</span>
          )}
        </p>
      )}

      {/* ---- Inventory ---- */}
      {character.inventory.length > 0 && (
        <>
          <div className={styles.sectionTitle}>Inventory</div>
          <ul className={styles.inventoryList}>
            {character.inventory.map((item, idx) => (
              <li key={`${item}-${idx}`} className={styles.inventoryItem}>
                {item}
              </li>
            ))}
          </ul>
        </>
      )}

      {/* ---- Action Buttons ---- */}
      <hr className={styles.accentBar} />
      <div className={styles.actions}>
        {isEditing ? (
          <>
            <button
              type="button"
              className={styles.actionBtn}
              onClick={handleSave}
              aria-label="Save character changes"
            >
              Save
            </button>
            <button
              type="button"
              className={`${styles.actionBtn} ${styles.cancelBtn}`}
              onClick={handleCancelEdit}
              aria-label="Cancel editing"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            className={styles.actionBtn}
            onClick={handleEdit}
            aria-label="Edit character"
          >
            Edit
          </button>
        )}

        <button
          type="button"
          className={`${styles.actionBtn} ${styles.regenerateBtn}`}
          onClick={handleRegenerate}
          disabled={regenerating}
          aria-label="Regenerate character"
        >
          {regenerating ? (
            <>
              <span className={styles.spinner} aria-hidden="true" />
              Regenerating&hellip;
            </>
          ) : (
            'Regenerate'
          )}
        </button>

        <button
          type="button"
          className={`${styles.actionBtn} ${styles.startBtn}`}
          onClick={handleStartAdventure}
          aria-label="Start adventure with this character"
        >
          Start Adventure &rarr;
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
