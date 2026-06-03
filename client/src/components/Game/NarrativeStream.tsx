/**
 * NarrativeStream — scrollable narrative display pane.
 *
 * Renders structured NarrativeEntry items from the game store with unique
 * visual styles per entry type. Supports auto-scroll that pauses when the
 * user scrolls up, with a floating "scroll to bottom" button.
 */

import { useRef, useEffect, useState, useCallback } from 'react'
import { useGameStore } from '../../stores/gameStore'
import type { NarrativeEntry } from '../../stores/gameStore'
import styles from './NarrativeStream.module.css'

/** How close (px) to the bottom edge before we consider it "near bottom". */
const SCROLL_THRESHOLD = 100

// ---------------------------------------------------------------------------
// Sub-components: one per entry type
// ---------------------------------------------------------------------------

function PlayerEntry({ content }: { content: string }) {
  return (
    <div className={styles.playerEntry}>
      <div className={styles.playerBubble}>{content}</div>
    </div>
  )
}

function NarrativeEntryBlock({ content }: { content: string }) {
  if (!content) return null
  const paragraphs = content.split('\n').filter(Boolean)
  return (
    <div className={styles.narrativeEntry}>
      {paragraphs.length > 0
        ? paragraphs.map((p, i) => (
            <p key={i} className={styles.narrativeParagraph}>
              {p}
            </p>
          ))
        : content && (
            <p className={styles.narrativeParagraph}>{content}</p>
          )}
    </div>
  )
}

function ToolResultEntry({ content }: { content: string }) {
  return (
    <div className={styles.toolResultEntry}>
      <em>{content}</em>
    </div>
  )
}

function SeparatorEntry() {
  return (
    <div className={styles.separatorEntry}>
      <span className={styles.separatorIcon} aria-hidden="true">
        ✦
      </span>
    </div>
  )
}

function ErrorEntry({ content }: { content: string }) {
  return (
    <div className={styles.errorEntry} role="alert">
      {content}
    </div>
  )
}

function NarrativeEntryRow({ entry }: { entry: NarrativeEntry }) {
  switch (entry.type) {
    case 'player':
      return <PlayerEntry content={entry.content} />
    case 'narrative':
      return <NarrativeEntryBlock content={entry.content} />
    case 'tool_result':
      return <ToolResultEntry content={entry.content} />
    case 'separator':
      return <SeparatorEntry />
    case 'error':
      return <ErrorEntry content={entry.content} />
    default:
      return null
  }
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function NarrativeStream() {
  const scrollRef = useRef<HTMLDivElement>(null)
  const shouldAutoScroll = useRef(true)
  const entries = useGameStore((s) => s.narrativeEntries)
  const [isNearBottom, setIsNearBottom] = useState(true)

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    const near = distance <= SCROLL_THRESHOLD
    shouldAutoScroll.current = near
    setIsNearBottom(near)
  }, [])

  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    shouldAutoScroll.current = true
    setIsNearBottom(true)
  }, [])

  // Intentionally depends only on entries.length — entries are append-only.
  // If this changes, add entries to the dependency array and consider
  // the impact on re-renders.
  useEffect(() => {
    if (shouldAutoScroll.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [entries.length])

  // Empty state
  if (entries.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <span className={styles.emptyText}>The adventure awaits...</span>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div
        ref={scrollRef}
        className={styles.scrollArea}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-label="Story narrative"
      >
        {entries.map((entry) => (
          <NarrativeEntryRow key={entry.id} entry={entry} />
        ))}
      </div>

      {!isNearBottom && (
        <button
          type="button"
          className={styles.scrollBtn}
          onClick={scrollToBottom}
          aria-label="Scroll to bottom"
        >
          ↓ Scroll to bottom
        </button>
      )}
    </div>
  )
}
