/**
 * StoryModal — read-only modal that displays the adventure story so far.
 *
 * Reads narrative entries from the game store — the structured array of
 * {type, content, id, timestamp} objects that replaces the old story_log /
 * story_summary approach.  Simple content-only display with no
 * loading/saving/success/error phases.
 */

import { useEffect, useCallback, useRef } from 'react'
import { useGameStore } from '../../stores/gameStore'
import { useCharacterStore } from '../../stores/characterStore'
import styles from './StoryModal.module.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StoryModalProps {
  /** Whether the modal is visible. */
  isOpen: boolean
  /** Called to close / dismiss the modal. */
  onClose: () => void
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface ParsedEntry {
  type: 'paragraph'
  text: string
}

/**
 * Convert narrative entries into displayable paragraphs.
 * Separator entries are skipped; all others render as plain text.
 */
function extractStoryData(
  entries: { type: string; content: string }[],
): ParsedEntry[] | null {
  if (entries.length === 0) return null

  const result: ParsedEntry[] = []
  for (const entry of entries) {
    if (entry.type === 'separator') continue
    if (entry.content.length === 0) continue
    result.push({ type: 'paragraph', text: entry.content })
  }

  return result.length > 0 ? result : null
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StoryModal({ isOpen, onClose }: StoryModalProps) {
  const narrativeEntries = useGameStore((s) => s.narrativeEntries)
  const characterName = useCharacterStore(
    (s) => s.currentCharacter?.name ?? null,
  )

  const modalRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => { onCloseRef.current = onClose }, [onClose])

  // Derive story entries from the narrative entries store
  const parsedEntries: ParsedEntry[] | null = extractStoryData(narrativeEntries)
  const isEmpty = parsedEntries == null

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

        const isFocusInside = modalRef.current.contains(document.activeElement)
        if (!isFocusInside) {
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

  // ---------- Render ----------
  return (
    <div
      className={styles.overlay}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="story-modal-title"
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
          aria-label="Close story dialog"
        >
          ✕
        </button>

        {/* ---- Title ---- */}
        <h2 id="story-modal-title" className={styles.title}>
          <span className={styles.titleIcon} aria-hidden="true">📖</span>
          {' '}Adventure Story
        </h2>

        {characterName && (
          <p className={styles.subtitle}>
            Adventure Log for {characterName}
          </p>
        )}

        {/* ---- Empty state ---- */}
        {isEmpty && (
          <div className={styles.emptyState}>
            <p className={styles.emptyText}>
              No story entries available.
            </p>
          </div>
        )}

        {/* ---- Content ---- */}
        {!isEmpty && (
          <div className={styles.storyContent} data-testid="story-content">
            {parsedEntries.map((entry, idx) => (
              <p
                key={`p-${idx}`}
                className={styles.storyEntry}
              >
                {entry.text}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
