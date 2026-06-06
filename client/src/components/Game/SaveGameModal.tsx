/**
 * SaveGameModal — modal dialog for saving the current game.
 *
 * State machine with four phases:
 *   INPUT  → user enters a name and clicks Save
 *   SAVING → loading spinner, buttons disabled
 *   SUCCESS → green checkmark, auto-closes after 1.2 s
 *   ERROR   → shows error message with Try Again / Cancel
 *
 * Reads worldState and character data from the game store, calls
 * the backend save endpoint, and reports back the resulting slug.
 */

import { useState, useEffect, useLayoutEffect, useCallback, useRef, type FormEvent } from 'react'
import { useGameStore } from '../../stores/gameStore'
import { useCharacterStore } from '../../stores/characterStore'
import { saveGame } from '../../api/endpoints'
import styles from './SaveGameModal.module.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SaveGameModalProps {
  /** Whether the modal is visible. */
  isOpen: boolean
  /** Called to close / dismiss the modal. */
  onClose: () => void
  /** Called after a successful save with the backend slug. */
  onSaved?: (slug: string) => void
}

type SavePhase = 'input' | 'saving' | 'success' | 'error'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Generate a default save name from the store's current state. */
function generateSaveName(): string {
  const gameStore = useGameStore.getState()
  const charStore = useCharacterStore.getState()
  const charName =
    charStore.currentCharacter?.name ??
    (gameStore.worldState?._character as Record<string, unknown> | undefined)
      ?.name as string | undefined
  const turnCount = gameStore.turnCount

  const prefix = charName ?? 'Adventure'
  return `${prefix} - Turn ${turnCount}`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SaveGameModal({ isOpen, onClose, onSaved }: SaveGameModalProps) {
  const worldState = useGameStore((s) => s.worldState)

  const modalRef = useRef<HTMLDivElement>(null)
  const [phase, setPhase] = useState<SavePhase>('input')
  const [saveName, setSaveName] = useState(generateSaveName)
  const [errorMessage, setErrorMessage] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const autoCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Keep stable refs to callbacks so timers / handlers always call the latest version
  const onCloseRef = useRef(onClose)
  const onSavedRef = useRef(onSaved)
  useEffect(() => { onCloseRef.current = onClose }, [onClose])
  useEffect(() => { onSavedRef.current = onSaved }, [onSaved])

  // ---------- Reset state whenever the modal opens ----------
  useLayoutEffect(() => {
    if (isOpen) {
      setPhase('input')
      setErrorMessage('')
      setSaveName(generateSaveName())

      // Focus the input after the modal paints
      requestAnimationFrame(() => {
        inputRef.current?.focus()
        inputRef.current?.select()
      })
    }

    // Clean up auto-close timer on unmount / close
    return () => {
      if (autoCloseTimer.current !== null) {
        clearTimeout(autoCloseTimer.current)
        autoCloseTimer.current = null
      }
    }
  }, [isOpen])

  // ---------- Escape key closes + focus trap ----------
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && phase !== 'saving') {
        onClose()
        return
      }

      // Focus trap — cycle Tab / Shift+Tab through focusable elements
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
      }
    },
    [onClose, phase],
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
    if (phase !== 'saving') onClose()
  }, [onClose, phase])

  // ---------- Save logic ----------
  const handleSave = useCallback(async () => {
    const trimmed = saveName.trim()
    if (!trimmed) {
      setPhase('error')
      setErrorMessage('Please enter a save name.')
      return
    }

    setPhase('saving')
    setErrorMessage('')

    try {
      // Build state payload — embed character inside state for single-file save
      const stateData: Record<string, unknown> = worldState
        ? JSON.parse(JSON.stringify(worldState))
        : {}

      const currentChar = useCharacterStore.getState().currentCharacter
      if (currentChar) {
        const charData = { ...currentChar }
        if (charData.id != null) charData.id = String(charData.id)
        stateData._character = charData
        stateData.character_name = charData.name ?? ''
        stateData.character_id = charData.id
      }

      // Include narrative entries so the full conversation survives save/load
      const narrativeEntries = useGameStore.getState().narrativeEntries
      if (narrativeEntries.length > 0) {
        stateData._narrative_entries = narrativeEntries
      }

      const resp = await saveGame({
        state: stateData,
        name: trimmed,
      })

      if (resp.ok) {
        setPhase('success')
        autoCloseTimer.current = setTimeout(() => {
          onSavedRef.current?.(resp.slug)
          onCloseRef.current()
        }, 1200)
      } else {
        setPhase('error')
        setErrorMessage('Save failed — the server returned an error.')
      }
    } catch (err: unknown) {
      setPhase('error')
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred.'
      setErrorMessage(msg)
    }
  }, [saveName, worldState, onClose, onSaved])

  // ---------- Form submit ----------
  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault()
      if (phase === 'input') {
        void handleSave()
      }
    },
    [phase, handleSave],
  )

  // ---------- Don't render when closed ----------
  if (!isOpen) return null

  // ---------- Render ----------
  return (
    <div
      className={styles.overlay}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label="Save game"
    >
      <div className={styles.modal} onClick={(e) => e.stopPropagation()} ref={modalRef}>
        {/* ---- Close button ---- */}
        <button
          type="button"
          className={styles.closeBtn}
          onClick={phase !== 'saving' ? onClose : undefined}
          aria-label="Close save dialog"
          disabled={phase === 'saving'}
        >
          ✕
        </button>

        {/* ---- Title ---- */}
        <h2 className={styles.title}>Save Game</h2>

        {/* ---- INPUT phase ---- */}
        {phase === 'input' && (
          <form onSubmit={handleSubmit} className={styles.form}>
            <label className={styles.label} htmlFor="save-name-input">
              Save Name
            </label>
            <input
              ref={inputRef}
              id="save-name-input"
              type="text"
              className={styles.input}
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder="Enter a name for this save..."
              autoComplete="off"
            />
            <div className={styles.buttonRow}>
              <button type="submit" className={styles.saveBtn}>
                Save
              </button>
              <button
                type="button"
                className={styles.cancelBtn}
                onClick={onClose}
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* ---- SAVING phase ---- */}
        {phase === 'saving' && (
          <div className={styles.centeredState}>
            <span className={styles.spinner} aria-hidden="true" />
            <p className={styles.statusText}>Saving...</p>
          </div>
        )}

        {/* ---- SUCCESS phase ---- */}
        {phase === 'success' && (
          <div className={styles.centeredState}>
            <span className={styles.checkmark} aria-hidden="true">
              ✓
            </span>
            <p className={styles.statusText}>Game saved!</p>
          </div>
        )}

        {/* ---- ERROR phase ---- */}
        {phase === 'error' && (
          <div className={styles.errorState}>
            <p className={styles.errorMessage}>{errorMessage}</p>
            <div className={styles.buttonRow}>
              <button
                type="button"
                className={styles.saveBtn}
                onClick={handleSave}
              >
                Try Again
              </button>
              <button
                type="button"
                className={styles.cancelBtn}
                onClick={onClose}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
