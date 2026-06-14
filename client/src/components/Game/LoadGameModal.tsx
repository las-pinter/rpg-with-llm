/**
 * LoadGameModal — modal dialog for loading and deleting saved games.
 *
 * State machine with phases:
 *   LOADING    → spinner while fetching save list
 *   EMPTY      → "No saved games found." + Close
 *   LIST       → scrollable list of save cards with Load / Delete
 *   FETCH_ERROR → "Failed to load saves." + Try Again
 *
 * Each card can show:
 *   idle         → name, meta, Load / Delete buttons
 *   loading      → inline spinner (Load clicked, waiting on server)
 *   confirm      → "Delete 'name'?" with Yes / Cancel
 *   deleting     → spinner during delete API call
 *   deleted      → "Deleted!" feedback for 1.2 s before card removal
 *   load-error   → inline error message on the card
 */

import { useState, useEffect, useLayoutEffect, useCallback, useRef } from 'react'
import { listSaves, loadGame, deleteSave } from '../../api/endpoints'
import type { SaveMeta } from '../../api/types'
import styles from './LoadGameModal.module.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface LoadGameModalProps {
  /** Whether the modal is visible. */
  isOpen: boolean
  /** Called to close / dismiss the modal. */
  onClose: () => void
  /** Called after a successful game load. */
  onLoaded?: (state: Record<string, unknown>, character?: Record<string, unknown>) => void
}

type LoadPhase = 'loading' | 'list' | 'empty' | 'fetchError'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format an ISO timestamp into a readable string. */
function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return ts
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LoadGameModal({ isOpen, onClose, onLoaded }: LoadGameModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)

  // ------ Top-level state ------
  const [phase, setPhase] = useState<LoadPhase>('loading')
  const [saves, setSaves] = useState<SaveMeta[]>([])
  const [fetchError, setFetchError] = useState('')

  // ------ Per-card state ------
  const [loadingSlug, setLoadingSlug] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<{ slug: string; message: string } | null>(null)
  const [confirmDeleteSlug, setConfirmDeleteSlug] = useState<string | null>(null)
  const [deletingSlug, setDeletingSlug] = useState<string | null>(null)
  const [deletedSlug, setDeletedSlug] = useState<string | null>(null)

  // Stable callback refs
  const onCloseRef = useRef(onClose)
  const onLoadedRef = useRef(onLoaded)
  useEffect(() => { onCloseRef.current = onClose }, [onClose])
  useEffect(() => { onLoadedRef.current = onLoaded }, [onLoaded])

  // Timer ref for "Deleted!" auto-clear
  const deletedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (deletedTimerRef.current !== null) {
        clearTimeout(deletedTimerRef.current)
      }
    }
  }, [])

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

  // ---------- Fetch saves ----------
  const fetchSaves = useCallback(async () => {
    setPhase('loading')
    setFetchError('')
    setSaves([])
    try {
      const resp = await listSaves()
      if (resp.ok) {
        if (resp.saves.length === 0) {
          setPhase('empty')
        } else {
          setSaves(resp.saves)
          setPhase('list')
        }
      } else {
        setPhase('fetchError')
        setFetchError('Failed to load saves.')
      }
    } catch {
      setPhase('fetchError')
      setFetchError('Failed to load saves.')
    }
  }, [])

  // ---------- Reset state when modal opens ----------
  useLayoutEffect(() => {
    if (isOpen) {
      setPhase('loading')
      setSaves([])
      setFetchError('')
      setLoadingSlug(null)
      setLoadError(null)
      setConfirmDeleteSlug(null)
      setDeletingSlug(null)
      setDeletedSlug(null)

      void fetchSaves()
    }

    return () => {
      if (deletedTimerRef.current !== null) {
        clearTimeout(deletedTimerRef.current)
        deletedTimerRef.current = null
      }
    }
  }, [isOpen, fetchSaves])

  // ---------- Escape key + focus trap ----------
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (loadingSlug || deletingSlug) return
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
      }
    },
    [loadingSlug, deletingSlug],
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
    if (loadingSlug || deletingSlug) return
    onCloseRef.current()
  }, [loadingSlug, deletingSlug])

  // ---------- Load a save ----------
  const handleLoad = useCallback(async (slug: string) => {
    setLoadError(null)
    setLoadingSlug(slug)
    try {
      const resp = await loadGame(slug)
      if (resp.ok) {
        onLoadedRef.current?.(resp.state, resp.character)
        onCloseRef.current()
      } else {
        setLoadError({ slug, message: 'Failed to load game.' })
        setLoadingSlug(null)
      }
    } catch {
      setLoadError({ slug, message: 'Failed to load game.' })
      setLoadingSlug(null)
    }
  }, [])

  // ---------- Delete flow ----------
  const handleRequestDelete = useCallback((slug: string) => {
    setConfirmDeleteSlug(slug)
    setLoadError(null)
  }, [])

  const handleCancelDelete = useCallback(() => {
    setConfirmDeleteSlug(null)
  }, [])

  const handleConfirmDelete = useCallback(
    async (slug: string) => {
      setDeletingSlug(slug)
      setConfirmDeleteSlug(null)
      setLoadError(null)
      try {
        const resp = await deleteSave(slug)
        if (resp.ok) {
          setDeletedSlug(slug)
          setDeletingSlug(null)
          deletedTimerRef.current = setTimeout(() => {
            setSaves((prev) => prev.filter((s) => s.id !== slug))
            setDeletedSlug(null)
          }, 1200)
        } else {
          setLoadError({ slug, message: 'Failed to delete save.' })
          setDeletingSlug(null)
        }
      } catch {
        setLoadError({ slug, message: 'Failed to delete save.' })
        setDeletingSlug(null)
      }
    },
    [],
  )

  // ---------- Render helpers ----------

  /** Render a single save card. */
  function renderSaveCard(save: SaveMeta): React.ReactNode {
    const isDeleted = deletedSlug === save.id
    const isLoading = loadingSlug === save.id
    const isDeleting = deletingSlug === save.id
    const isConfirming = confirmDeleteSlug === save.id
    const showError = loadError != null && !isLoading && !isDeleting && !isConfirming

    return (
      <div
        key={save.id}
        className={`${styles.saveCard} ${isDeleted ? styles.saveCardDeleted : ''}`}
        data-id={save.id}
      >
        {/* ---- Deleted feedback ---- */}
        {isDeleted && (
          <div className={styles.deletedOverlay}>
            <span className={styles.deletedText}>Deleted!</span>
          </div>
        )}

        {/* ---- Idle state ---- */}
        {!isDeleted && !isDeleting && !isConfirming && (
          <div className={styles.saveCardInner}>
            <div className={styles.saveCardInfo}>
              <span className={styles.saveName}>{save.name}</span>
              {save.character_name && (
                <span className={styles.saveCharacter}>{save.character_name}</span>
              )}
              <span className={styles.saveMeta}>
                {save.turn_count != null && `Turn ${save.turn_count}`}
                {save.turn_count != null && save.timestamp && ' · '}
                {save.timestamp && formatTimestamp(save.timestamp)}
              </span>
            </div>

            <div className={styles.saveCardActions}>
              {isLoading ? (
                <span className={styles.cardSpinner} aria-hidden="true" />
              ) : (
                <>
                  <button
                    type="button"
                    className={styles.loadBtn}
                    onClick={() => handleLoad(save.id)}
                    disabled={isLoading || isDeleting || loadingSlug != null || deletingSlug != null}
                  >
                    Load
                  </button>
                  <button
                    type="button"
                    className={styles.deleteBtn}
                    onClick={() => handleRequestDelete(save.id)}
                    disabled={isLoading || isDeleting || loadingSlug != null || deletingSlug != null}
                  >
                    Delete
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {/* ---- Delete confirm overlay ---- */}
        {!isDeleted && isConfirming && (
          <div className={styles.confirmOverlay}>
            <span className={styles.confirmText}>
              Delete &lsquo;{save.name}&rsquo;?
            </span>
            <div className={styles.confirmActions}>
              <button
                type="button"
                className={styles.confirmYesBtn}
                onClick={() => handleConfirmDelete(save.id)}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting…' : 'Yes, delete'}
              </button>
              <button
                type="button"
                className={styles.confirmNoBtn}
                onClick={handleCancelDelete}
                disabled={isDeleting}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* ---- Deleting spinner ---- */}
        {!isDeleted && isDeleting && (
          <div className={styles.deletingState}>
            <span className={styles.cardSpinner} aria-hidden="true" />
            <span className={styles.deletingText}>Deleting…</span>
          </div>
        )}

        {/* ---- Inline error ---- */}
        {showError && loadError?.slug === save.id && (
          <div className={styles.cardError}>
            {loadError.message}
          </div>
        )}
      </div>
    )
  }

  // ---------- Don't render when closed ----------
  if (!isOpen) return null

  // ---------- Render ----------
  return (
    <div
      className={styles.overlay}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="load-game-title"
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
          onClick={loadingSlug || deletingSlug ? undefined : onClose}
          aria-label="Close load dialog"
          disabled={loadingSlug != null || deletingSlug != null}
        >
          ✕
        </button>

        {/* ---- Title ---- */}
        <h2 id="load-game-title" className={styles.title}>Load Game</h2>

        {/* ---- LOADING phase ---- */}
        {phase === 'loading' && (
          <div className={styles.centeredState}>
            <span className={styles.spinner} aria-hidden="true" />
            <p className={styles.statusText}>Loading saves…</p>
          </div>
        )}

        {/* ---- EMPTY phase ---- */}
        {phase === 'empty' && (
          <div className={styles.centeredState}>
            <p className={styles.emptyText}>No saved games found.</p>
            <button type="button" className={styles.closeEmptyBtn} onClick={onClose}>
              Close
            </button>
          </div>
        )}

        {/* ---- FETCH_ERROR phase ---- */}
        {phase === 'fetchError' && (
          <div className={styles.centeredState}>
            <p className={styles.errorMessage}>{fetchError}</p>
            <button
              type="button"
              className={styles.retryBtn}
              onClick={fetchSaves}
            >
              Try Again
            </button>
          </div>
        )}

        {/* ---- LIST phase ---- */}
        {phase === 'list' && (
          <div className={styles.saveList}>
            {saves.map(renderSaveCard)}
          </div>
        )}
      </div>
    </div>
  )
}
