/**
 * StoryModal — read-only modal that displays the adventure story so far.
 *
 * Reads `story_summary` (preferred) or `story_log` (fallback) from the
 * world state in the game store.  Simple content-only display with no
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

/** Regex for "[Turn N] text" story log format. */
const TURN_HEADER_RE = /^\[Turn\s+(\d+)\]\s*(.*)$/

interface ParsedEntry {
  type: 'paragraph' | 'turnHeader'
  text: string
  turnNumber?: number
}

/**
 * Parse story_log entries into displayable blocks.
 * Entries matching "[Turn N] text" get a turn header followed by the text;
 * everything else renders as a plain paragraph.
 */
function parseStoryLog(entries: unknown[]): ParsedEntry[] {
  const result: ParsedEntry[] = []

  for (const raw of entries) {
    if (typeof raw !== 'string' || raw.length === 0) continue

    const match = raw.match(TURN_HEADER_RE)
    if (match) {
      const turnNumber = Number(match[1])
      const text = (match[2] ?? '').trim()
      result.push({ type: 'turnHeader', text: `Turn ${turnNumber}`, turnNumber })
      if (text.length > 0) {
        result.push({ type: 'paragraph', text })
      }
    } else {
      result.push({ type: 'paragraph', text: raw })
    }
  }

  return result
}

/**
 * Safely extract story data from worldState.
 * Returns an array of prepared ParsedEntry items or null (meaning empty).
 */
function extractStoryData(
  worldState: Record<string, unknown> | null,
): ParsedEntry[] | null {
  if (worldState == null) return null

  // Prefer story_summary
  const summary = worldState.story_summary
  if (Array.isArray(summary) && summary.length > 0) {
    const entries: ParsedEntry[] = []
    for (const item of summary) {
      if (typeof item === 'string' && item.length > 0) {
        entries.push({ type: 'paragraph', text: item })
      }
    }
    return entries.length > 0 ? entries : null
  }

  // Fallback to story_log
  const log = worldState.story_log
  if (Array.isArray(log) && log.length > 0) {
    const entries = parseStoryLog(log)
    return entries.length > 0 ? entries : null
  }

  return null
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StoryModal({ isOpen, onClose }: StoryModalProps) {
  const worldState = useGameStore((s) => s.worldState)
  const characterName = useCharacterStore(
    (s) => s.currentCharacter?.name ?? null,
  )

  const modalRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => { onCloseRef.current = onClose }, [onClose])

  // Derive story entries from the world state
  const parsedEntries: ParsedEntry[] | null = extractStoryData(worldState)
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
              No story entries yet. Begin your adventure!
            </p>
          </div>
        )}

        {/* ---- Content ---- */}
        {!isEmpty && (
          <div className={styles.storyContent} data-testid="story-content">
            {parsedEntries.map((entry, idx) =>
              entry.type === 'turnHeader' ? (
                <h3
                  key={`h-${entry.turnNumber ?? idx}-${idx}`}
                  className={styles.turnHeader}
                >
                  {entry.text}
                </h3>
              ) : (
                <p
                  key={`p-${idx}`}
                  className={styles.storyEntry}
                >
                  {entry.text}
                </p>
              ),
            )}
          </div>
        )}
      </div>
    </div>
  )
}
