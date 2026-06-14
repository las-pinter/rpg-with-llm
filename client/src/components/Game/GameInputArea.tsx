/**
 * GameInputArea — bottom input panel for player actions.
 *
 * Features a text input with "Act" submit button, quick action suggestion chips,
 * and save/load/new game action buttons. Reads from and writes to the game store.
 *
 * Submit behaviour:
 *  1. If `onSubmit` prop is provided, call it with the trimmed input.
 *  2. Otherwise, set `playerInput` and `processing: true` in the store.
 *  3. Clear the input field.
 */

import { useRef, useCallback, type FormEvent, type KeyboardEvent } from 'react'
import { useGameStore } from '../../stores/gameStore'
import styles from './GameInputArea.module.css'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Quick action suggestions displayed as clickable chips below the input. */
const QUICK_ACTIONS = [
  'Look around',
  'Check inventory',
  'Talk to NPCs',
  'Rest',
  'Attack',
  'Use magic',
] as const

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface GameInputAreaProps {
  /** Called when the user clicks Save Game. */
  onSave?: () => void
  /** Called when the user clicks Load Game. */
  onLoad?: () => void
  /** Called when the user clicks New Game. */
  onNewGame?: () => void
  /** Called when the user submits an action. If omitted, falls back to store. */
  onSubmit?: (input: string) => void
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function GameInputArea({
  onSave,
  onLoad,
  onNewGame,
  onSubmit,
}: GameInputAreaProps) {
  const processing = useGameStore((s) => s.processing)
  const isActive = useGameStore((s) => s.isActive)
  const setPlayerInput = useGameStore((s) => s.setPlayerInput)
  const setProcessing = useGameStore((s) => s.setProcessing)

  const inputRef = useRef<HTMLInputElement>(null)

  /** Handle form submission — Enter key or Act button click. */
  const handleSubmit = useCallback(() => {
    const value = inputRef.current?.value ?? ''
    const trimmed = value.trim()
    if (!trimmed || processing) return

    if (onSubmit) {
      onSubmit(trimmed)
    } else {
      setPlayerInput(trimmed)
      setProcessing(true)
    }

    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }, [processing, onSubmit, setPlayerInput, setProcessing])

  /** Handle form submit event (button click). */
  const onFormSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault()
      handleSubmit()
    },
    [handleSubmit],
  )

  /** Handle Enter key in the input field. */
  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  /** Fill the input field with a quick action suggestion. */
  const handleQuickAction = useCallback((action: string) => {
    if (inputRef.current) {
      inputRef.current.value = action
    }
  }, [])

  const isDisabled = processing || !isActive

  return (
    <div className={styles.container} role="region" aria-label="Game input area">
      {/* ---- Input row ---- */}
      <form className={styles.inputRow} onSubmit={onFormSubmit}>
        <input
          type="text"
          className={styles.inputField}
          placeholder="What do you do?"
          aria-label="Player action input"
          ref={inputRef}
          onKeyDown={onKeyDown}
          disabled={!isActive || processing}
        />
        <button
          type="submit"
          className={styles.actBtn}
          aria-label="Submit action"
          disabled={isDisabled}
        >
          Act
        </button>
      </form>

      {/* ---- Quick actions ---- */}
      <div className={styles.quickActionsRow} role="group" aria-label="Quick actions">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action}
            type="button"
            className={styles.quickChip}
            role="button"
            tabIndex={0}
            onClick={() => handleQuickAction(action)}
            disabled={processing || !isActive}
            aria-label={`Quick action: ${action}`}
          >
            {action}
          </button>
        ))}
      </div>

      {/* ---- Save / Load / New Game ---- */}
      <div className={styles.actionRow}>
        <button
          type="button"
          className={styles.actionBtn}
          onClick={onSave}
          disabled={!isActive}
          aria-label="Save game"
        >
          <span className={styles.actionBtnIcon} aria-hidden="true">◆</span>
          Save Game
        </button>
        <button
          type="button"
          className={styles.actionBtn}
          onClick={onLoad}
          aria-label="Load game"
        >
          <span className={styles.actionBtnIcon} aria-hidden="true">◇</span>
          Load Game
        </button>
        <button
          type="button"
          className={styles.actionBtn}
          onClick={onNewGame}
          aria-label="New game"
        >
          <span className={styles.actionBtnIcon} aria-hidden="true">✦</span>
          New Game
        </button>
      </div>
    </div>
  )
}
