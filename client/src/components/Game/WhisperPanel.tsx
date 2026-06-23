/**
 * WhisperPanel — DM consultation overlay (slide-in sidebar / mobile bottom sheet).
 *
 * Lets the player ask the DM out-of-character questions mid-game.
 * Uses a chat-log interface with streaming response support.
 *
 * Patterns match StoryModal:
 *  - No createPortal, position: fixed overlay
 *  - Escape key + focus trap via document.addEventListener
 *  - Overlay click dismiss, inner panel e.stopPropagation()
 *  - CSS modules with dark fantasy theme tokens
 */

import { useCallback, useEffect, useRef } from 'react'
import { useGameStore } from '@/stores/gameStore'
import { consult } from '@/api/endpoints'
import type { ConsultParams } from '@/api/types'
import styles from './WhisperPanel.module.css'

export function WhisperPanel() {
  const consultationOpen = useGameStore((s) => s.consultationOpen)
  const consultationHistory = useGameStore((s) => s.consultationHistory)
  const consultationStreaming = useGameStore((s) => s.consultationStreaming)
  const setConsultationOpen = useGameStore((s) => s.setConsultationOpen)
  const addConsultationEntry = useGameStore((s) => s.addConsultationEntry)
  const setConsultationStreaming = useGameStore((s) => s.setConsultationStreaming)
  const abortRef = useRef<AbortController | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // ---------- Escape key + focus trap ----------
  useEffect(() => {
    if (!consultationOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setConsultationOpen(false)
        return
      }

      if (e.key === 'Tab' && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        if (focusable.length === 0) return

        const first = focusable[0]
        const last = focusable[focusable.length - 1]

        const isFocusInside = panelRef.current.contains(document.activeElement)
        if (!isFocusInside) {
          e.preventDefault()
          first?.focus()
          return
        }

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault()
            last?.focus()
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault()
            first?.focus()
          }
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    // Focus the input when the panel opens
    inputRef.current?.focus()

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [consultationOpen, setConsultationOpen])

  // ---------- Abort in-flight request on close ----------
  useEffect(() => {
    if (!consultationOpen) {
      abortRef.current?.abort()
      abortRef.current = null
    }
  }, [consultationOpen])

  // ---------- Handlers ----------

  const handleOverlayClick = useCallback(() => {
    setConsultationOpen(false)
  }, [setConsultationOpen])

  const handleSubmit = useCallback(async () => {
    const input = inputRef.current?.value?.trim()
    if (!input || consultationStreaming) return

    // Clear the input field
    if (inputRef.current) inputRef.current.value = ''

    // Add user message to history
    addConsultationEntry('user', input)
    setConsultationStreaming(true)

    // Create abort controller for this request
    abortRef.current = new AbortController()

    try {
      const params: ConsultParams = { input }
      const response = await consult(params, abortRef.current.signal)

      if (response.ok && response.answer) {
        addConsultationEntry('assistant', response.answer)
      } else {
        addConsultationEntry(
          'assistant',
          'The DM is momentarily distracted. Please try again.',
        )
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // Silent abort — user closed the panel, no error shown
        return
      }
      addConsultationEntry(
        'assistant',
        'The DM is momentarily distracted. Please try again.',
      )
    } finally {
      setConsultationStreaming(false)
      abortRef.current = null
    }
  }, [consultationStreaming, addConsultationEntry, setConsultationStreaming])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  // ---------- Render ----------

  if (!consultationOpen) return null

  return (
    <div className={styles.overlay} onClick={handleOverlayClick}>
      <div
        ref={panelRef}
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="whisper-title"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ---- Header ---- */}
        <div className={styles.header}>
          <h2 id="whisper-title" className={styles.title}>
            Whisper — DM Consultation
          </h2>
          <button
            type="button"
            className={styles.closeButton}
            onClick={() => setConsultationOpen(false)}
            aria-label="Close consultation"
          >
            ✕
          </button>
        </div>

        {/* ---- Chat log ---- */}
        <div className={styles.chatLog} aria-live="polite">
          {consultationHistory.length === 0 ? (
            <p className={styles.emptyState}>
              No consultations yet. Ask a question!
            </p>
          ) : (
            consultationHistory.map((entry, i) => (
              <div
                key={i}
                className={`${styles.message} ${
                  entry.role === 'user'
                    ? styles.userMessage
                    : styles.assistantMessage
                }`}
              >
                <span className={styles.messageLabel}>
                  {entry.role === 'user' ? 'You' : 'DM'}
                </span>
                <p className={styles.messageContent}>{entry.content}</p>
              </div>
            ))
          )}

          {/* ---- Streaming indicator ---- */}
          {consultationStreaming && (
            <div
              className={`${styles.message} ${styles.assistantMessage} ${styles.streamingMessage}`}
            >
              <span className={styles.messageLabel}>DM</span>
              <p className={styles.messageContent}>Thinking...</p>
            </div>
          )}
        </div>

        {/* ---- Input area ---- */}
        <div className={styles.inputArea}>
          <input
            ref={inputRef}
            type="text"
            className={styles.input}
            placeholder="Ask the DM a question..."
            onKeyDown={handleKeyDown}
            disabled={consultationStreaming}
            aria-label="Consultation question"
          />
          <button
            type="button"
            className={styles.submitButton}
            onClick={handleSubmit}
            disabled={consultationStreaming}
            aria-label="Ask question"
          >
            Ask
          </button>
        </div>
      </div>
    </div>
  )
}
