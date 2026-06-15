/**
 * LoadTab — saved characters and saved games browsing.
 *
 * Two sections: "Saved Characters" (from /api/characters) and
 * "Saved Games" (from /api/saves). Each card offers Load/Continue
 * and Delete actions with confirmation.
 *
 * Fetches data on mount and refreshes after delete operations.
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCharacterStore } from '../../stores/characterStore'
import type { CharacterListItem, SaveMeta } from '../../api/types'
import styles from './LoadTab.module.css'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format an ISO timestamp string into a readable date/time. */
function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ts
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LoadTab() {
  const navigate = useNavigate()

  // ---- Store state ----
  const savedCharacters = useCharacterStore((s) => s.savedCharacters)
  const savedGames = useCharacterStore((s) => s.savedGames)
  const fetchCharacters = useCharacterStore((s) => s.fetchCharacters)
  const fetchSaves = useCharacterStore((s) => s.fetchSaves)
  const loadCharacterById = useCharacterStore((s) => s.loadCharacterById)
  const deleteCharacterById = useCharacterStore((s) => s.deleteCharacterById)
  const loadSaveGame = useCharacterStore((s) => s.loadSaveGame)
  const deleteSaveGame = useCharacterStore((s) => s.deleteSaveGame)
  const loadCharacterIntoForm = useCharacterStore((s) => s.loadCharacterIntoForm)
  const setActiveTab = useCharacterStore((s) => s.setActiveTab)

  // ---- Local state ----
  const [charLoading, setCharLoading] = useState(true)
  const [savesLoading, setSavesLoading] = useState(true)
  const [charError, setCharError] = useState<string | null>(null)
  const [savesError, setSavesError] = useState<string | null>(null)
  const [charDeleteId, setCharDeleteId] = useState<string | null>(null)
  const [saveDeleteId, setSaveDeleteId] = useState<string | null>(null)
  const [confirmingChar, setConfirmingChar] = useState<string | null>(null)
  const [confirmingSave, setConfirmingSave] = useState<string | null>(null)

  // Prevent double-fetch
  const fetchedRef = useRef(false)

  // ---- Fetch on mount ----
  useEffect(() => {
    if (fetchedRef.current) return
    fetchedRef.current = true

    let cancelled = false

    setCharLoading(true)
    setSavesLoading(true)
    setCharError(null)
    setSavesError(null)

    fetchCharacters()
      .then(() => {
        if (!cancelled) setCharLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setCharError('Failed to load saved characters.')
          setCharLoading(false)
        }
      })

    fetchSaves()
      .then(() => {
        if (!cancelled) setSavesLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setSavesError('Failed to load saved games.')
          setSavesLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
    // Intentionally runs once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---- Handlers ----

  const handleLoadCharacter = useCallback(
    async (id: string) => {
      setCharError(null)
      await loadCharacterById(id)
      const char = useCharacterStore.getState().currentCharacter
      if (!char) {
        setCharError('Failed to load character.')
        return
      }
      loadCharacterIntoForm(char)
      setActiveTab('create')
    },
    [loadCharacterById, loadCharacterIntoForm, setActiveTab],
  )

  const handleDeleteCharacter = useCallback(
    async (id: string) => {
      setConfirmingChar(null)
      setCharDeleteId(id)
      try {
        await deleteCharacterById(id)
        // Refetch after delete
        await fetchCharacters()
      } catch {
        setCharError('Failed to delete character.')
      } finally {
        setCharDeleteId(null)
      }
    },
    [deleteCharacterById, fetchCharacters],
  )

  const handleContinueSave = useCallback(
    async (slug: string) => {
      await loadSaveGame(slug)
      navigate('/game')
    },
    [loadSaveGame, navigate],
  )

  const handleDeleteSave = useCallback(
    async (slug: string) => {
      setConfirmingSave(null)
      setSaveDeleteId(slug)
      try {
        await deleteSaveGame(slug)
        // Refetch after delete
        await fetchSaves()
      } catch {
        setSavesError('Failed to delete save.')
      } finally {
        setSaveDeleteId(null)
      }
    },
    [deleteSaveGame, fetchSaves],
  )

  // ---- Render helpers ----

  function renderCharacterCard(c: CharacterListItem) {
    const isDeleting = charDeleteId === c.id
    const isConfirming = confirmingChar === c.id

    return (
      <div key={c.id} className={`${styles.card} ${isDeleting ? styles.cardDeleting : ''}`}>
        <div className={styles.cardInfo}>
          <h3 className={styles.cardName}>{c.name}</h3>
          <p className={styles.cardMeta}>
            {c.class} &middot; Level {c.level}
            {c.timestamp ? <>&middot; {formatTimestamp(c.timestamp)}</> : null}
          </p>
        </div>
        <div className={styles.cardActions}>
          {isConfirming ? (
            <>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnConfirm}`}
                onClick={() => handleDeleteCharacter(c.id)}
                disabled={isDeleting}
                aria-label={`Confirm delete ${c.name}`}
              >
                {isDeleting ? 'Deleting…' : 'Confirm'}
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnCancel}`}
                onClick={() => setConfirmingChar(null)}
                aria-label="Cancel delete"
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnPrimary}`}
                onClick={() => handleLoadCharacter(c.id)}
                aria-label={`Load ${c.name}`}
              >
                Load
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnDanger}`}
                onClick={() => setConfirmingChar(c.id)}
                aria-label={`Delete ${c.name}`}
              >
                Delete
              </button>
            </>
          )}
        </div>
      </div>
    )
  }

  function renderSaveCard(s: SaveMeta) {
    const isDeleting = saveDeleteId === s.id
    const isConfirming = confirmingSave === s.id
    const displayName = s.name || s.character_name || 'Unknown Save'

    return (
      <div key={s.id} className={`${styles.card} ${isDeleting ? styles.cardDeleting : ''}`}>
        <div className={styles.cardInfo}>
          <h3 className={styles.cardName}>{displayName}</h3>
          <p className={styles.cardMeta}>
            {s.character_name ? <>{s.character_name} &middot; </> : null}
            Turn {s.turn_count ?? '?'}
            {s.timestamp ? <>&middot; {formatTimestamp(s.timestamp)}</> : null}
          </p>
        </div>
        <div className={styles.cardActions}>
          {isConfirming ? (
            <>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnConfirm}`}
                onClick={() => handleDeleteSave(s.id)}
                disabled={isDeleting}
                aria-label={`Confirm delete save ${displayName}`}
              >
                {isDeleting ? 'Deleting…' : 'Confirm'}
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnCancel}`}
                onClick={() => setConfirmingSave(null)}
                aria-label="Cancel delete save"
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnPrimary}`}
                onClick={() => handleContinueSave(s.id)}
                aria-label={`Continue ${displayName}`}
              >
                Continue
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnDanger}`}
                onClick={() => setConfirmingSave(s.id)}
                aria-label={`Delete save ${displayName}`}
              >
                Delete
              </button>
            </>
          )}
        </div>
      </div>
    )
  }

  // ---- Render ----

  return (
    <div className={styles.page}>
      {/* ---- Saved Characters Section ---- */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Saved Characters</h2>
        <hr className={styles.accentBar} />

        {charError && (
          <div className={styles.errorBanner} role="alert">
            <span aria-hidden="true">&#x26A0;&#xFE0F;</span>
            <span>{charError}</span>
          </div>
        )}

        {charLoading ? (
          <div className={styles.statusRow} role="status">
            <span className={styles.spinner} aria-hidden="true" />
            <span>Loading characters…</span>
          </div>
        ) : savedCharacters.length === 0 ? (
          <p className={styles.emptyState}>
            No saved characters yet. Create one and start your adventure!
          </p>
        ) : (
          <div className={styles.cardList}>
            {savedCharacters.map(renderCharacterCard)}
          </div>
        )}
      </section>

      {/* ---- Saved Games Section ---- */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Saved Games</h2>
        <hr className={styles.accentBar} />

        {savesError && (
          <div className={styles.errorBanner} role="alert">
            <span aria-hidden="true">&#x26A0;&#xFE0F;</span>
            <span>{savesError}</span>
          </div>
        )}

        {savesLoading ? (
          <div className={styles.statusRow} role="status">
            <span className={styles.spinner} aria-hidden="true" />
            <span>Loading saved games…</span>
          </div>
        ) : savedGames.length === 0 ? (
          <p className={styles.emptyState}>
            No saved games yet.
          </p>
        ) : (
          <div className={styles.cardList}>
            {savedGames.map(renderSaveCard)}
          </div>
        )}
      </section>
    </div>
  )
}
