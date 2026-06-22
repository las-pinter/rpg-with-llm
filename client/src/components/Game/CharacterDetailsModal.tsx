/**
 * CharacterDetailsModal — read-only modal that displays the current
 * character sheet in a well-organised layout.
 *
 * Reads `currentCharacter` from the character store.  Returns null
 * when closed or when there is no character data.
 *
 * Follows the same overlay / focus-trap / Escape-to-close pattern as
 * StoryModal.
 */

import { useEffect, useCallback, useRef } from 'react'
import { useCharacterStore } from '../../stores/characterStore'
import styles from './CharacterDetailsModal.module.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CharacterDetailsModalProps {
  /** Whether the modal is visible. */
  isOpen: boolean
  /** Called to close / dismiss the modal. */
  onClose: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Ordered ability-score keys. */
const ABILITY_KEYS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** HP bar colour based on remaining-health ratio. */
function hpColorClass(ratio: number): string {
  if (ratio > 0.6) return styles.hpGreen
  if (ratio > 0.3) return styles.hpYellow
  return styles.hpRed
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CharacterDetailsModal({
  isOpen,
  onClose,
}: CharacterDetailsModalProps) {
  const character = useCharacterStore((s) => s.currentCharacter)
  const derivedSheet = useCharacterStore((s) => s.derivedSheet)

  const modalRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  // ---------- Focus first focusable element on modal open ----------
  useEffect(() => {
    if (!isOpen) return
    const raf = requestAnimationFrame(() => {
      const first = modalRef.current?.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      first?.focus()
    })
    return () => cancelAnimationFrame(raf)
  }, [isOpen])

  // ---------- Escape key + focus trap ----------
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCloseRef.current()
        return
      }

      if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }

        const isInside = modalRef.current.contains(document.activeElement)
        if (!isInside) {
          e.preventDefault()
          first.focus()
        }
      }
    },
    [],
  )

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, handleKeyDown])

  // ---------- Overlay click ----------
  const handleOverlayClick = useCallback(() => {
    onCloseRef.current()
  }, [])

  // ---------- Don't render when closed ----------
  if (!isOpen) return null

  // ---------- Empty state (no character) ----------
  if (!character) {
    return (
      <div
        className={styles.overlay}
        onClick={handleOverlayClick}
        role="dialog"
        aria-modal="true"
        aria-labelledby="character-details-title"
      >
        <div
          className={styles.modal}
          onClick={(e) => e.stopPropagation()}
          ref={modalRef}
        >
          {/* ---- Close button ---- */}
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Close character details dialog"
          >
            ✕
          </button>

          {/* ---- Title ---- */}
          <h2 id="character-details-title" className={styles.title}>
            Character Details
          </h2>

          {/* ---- Empty state ---- */}
          <div className={styles.emptyState}>
            <p className={styles.emptyText}>
              No character data available. Create a character first.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // ---------- Derived data ----------
  const hpValue: number =
    typeof character.resources?.hp?.value === 'number'
      ? character.resources.hp.value
      : 0
  const hpMax: number =
    typeof character.resources?.hp?.max === 'number'
      ? character.resources.hp.max
      : 0

  /** Use derived sheet AC when available, otherwise compute basic AC. */
  const dexScore: number =
    character.abilities['DEX'] ?? character.abilities['dex'] ?? 10
  const dexMod = Math.floor((dexScore - 10) / 2)
  const displayAc = derivedSheet?.ac ?? (10 + dexMod)

  const hpRatio = hpMax > 0 ? Math.min(hpValue / hpMax, 1) : 0
  const hpPercent = Math.round(Math.max(hpRatio, 0) * 100)

  // Build ordered list of ability entries (handle uppercase/lowercase keys)
  const abilityEntries = ABILITY_KEYS.map((key) => {
    const value =
      character.abilities[key] ?? character.abilities[key.toLowerCase()]
    return { key, value: value ?? '-' }
  })

  // ---------- Render ----------
  return (
    <div
      className={styles.overlay}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="character-details-title"
    >
      <div
        className={styles.modal}
        onClick={(e) => e.stopPropagation()}
        ref={modalRef}
      >
        {/* ---- Close button ---- */}
        <button
          type="button"
          className={styles.closeBtn}
          onClick={onClose}
          aria-label="Close character details dialog"
        >
          ✕
        </button>

        {/* ---- Header ---- */}
        <h2 id="character-details-title" className={styles.title}>
          {character.name}
        </h2>
        <p className={styles.subtitle}>
          {character.character_class} (Level {character.level})
        </p>

        {/* ---- Scrollable content ---- */}
        <div className={styles.content} data-testid="character-content">
          {/* ---- Attributes ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Attributes</h3>
            <div className={styles.attributesRow}>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>HP</span>
                <div className={styles.hpBarBg}>
                  <div
                    className={`${styles.hpBarFill} ${hpColorClass(hpRatio)}`}
                    style={{ width: `${hpPercent}%` }}
                    role="progressbar"
                    aria-valuenow={hpValue}
                    aria-valuemin={0}
                    aria-valuemax={hpMax}
                    aria-label={`${hpValue} of ${hpMax} hit points`}
                  />
                </div>
                <span className={styles.statValue}>
                  {hpValue}/{hpMax}
                </span>
              </div>

              <div className={styles.statCard}>
                <span className={styles.statLabel}>AC</span>
                <span className={styles.statValue}>{displayAc}</span>
              </div>

              <div className={styles.statCard}>
                <span className={styles.statLabel}>XP</span>
                <span className={styles.statValue}>{character.xp}</span>
              </div>

              <div className={styles.statCard}>
                <span className={styles.statLabel}>Gold</span>
                <span className={styles.statValue}>{character.gold}</span>
              </div>
            </div>
          </section>

          {/* ---- Abilities ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Abilities</h3>
            <div className={styles.abilitiesGrid}>
              {abilityEntries.map(({ key, value }) => (
                <div key={key} className={styles.abilityCard}>
                  <span className={styles.abilityLabel}>{key}</span>
                  <span className={styles.abilityScore}>{value}</span>
                </div>
              ))}
            </div>
          </section>

          {/* ---- Details ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Details</h3>
            {character.appearance && (
              <div className={styles.detailBlock}>
                <span className={styles.detailLabel}>Appearance</span>
                <p className={styles.detailText}>{character.appearance}</p>
              </div>
            )}
            {character.personality && (
              <div className={styles.detailBlock}>
                <span className={styles.detailLabel}>Personality</span>
                <p className={styles.detailText}>{character.personality}</p>
              </div>
            )}
            {character.backstory && (
              <div className={styles.detailBlock}>
                <span className={styles.detailLabel}>Backstory</span>
                <p className={styles.detailText}>{character.backstory}</p>
              </div>
            )}
          </section>

          {/* ---- Skills ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Skills</h3>
            {character.skills.length > 0 ? (
              <div className={styles.skillsList}>
                {character.skills.map((skill, i) => (
                  <span
                    key={`${skill}-${i}`}
                    className={styles.skillTag}
                  >
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className={styles.emptySmall}>No skills</p>
            )}
          </section>

          {/* ---- Inventory ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Inventory</h3>
            {character.inventory.length > 0 ? (
              <ul className={styles.itemList}>
                {character.inventory.map((item, i) => (
                  <li key={`${item.id}-${i}`} className={styles.itemEntry}>
                    {item.name}
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.emptySmall}>Nothing carried</p>
            )}
          </section>

          {/* ---- Plot Hooks ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Plot Hooks</h3>
            {character.hooks.length > 0 ? (
              <ul className={styles.hookList}>
                {character.hooks.map((hook, i) => (
                  <li key={`${hook}-${i}`} className={styles.hookEntry}>
                    {hook}
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.emptySmall}>None</p>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
