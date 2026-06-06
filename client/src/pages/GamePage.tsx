/**
 * GamePage — full game layout wiring all game components together.
 *
 * Layout (CSS Grid):
 * ┌──────────────────────────────────────────┐
 * │  Main Content Area         │  Sidebar    │
 * │  ┌────────────────────┐    │  ┌────────┐ │
 * │  │ GameHeader (title  │    │  │GameStat│ │
 * │  │ + action buttons)  │    │  │usSide- │ │
 * │  ├────────────────────┤    │  │ bar    │ │
 * │  │ NarrativeStream    │    │  │        │ │
 * │  │ (scrollable)       │    │  │        │ │
 * │  ├────────────────────┤    │  │        │ │
 * │  │ ThinkingIndicator  │    │  │        │ │
 * │  │ NpcThinkingInd.    │    │  │        │ │
 * │  ├────────────────────┤    │  └────────┘ │
 * │  │ GameInputArea      │    │             │
 * │  └────────────────────┘    │             │
 * └────────────────────────────┘─────────────┘
 *
 * Game Start Flow:
 *  1. On mount, check for currentCharacter in the character store.
 *  2. If no character → "Create a character first" with link to /character.
 *  3. If character exists but !isActive → auto-connect with "start" input.
 *  4. If loading a saved game → LoadGameModal's onLoaded sets state and connects.
 *
 * Cleanup: disconnect() is handled internally by useGameStream on unmount.
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGameStore } from '../stores/gameStore'
import { useCharacterStore } from '../stores/characterStore'
import { useConnectionStore } from '../stores/connectionStore'
import { useGameStream } from '../hooks/useGameStream'
import type { Character } from '../api/types'
import {
  NarrativeStream,
  ThinkingIndicator,
  NpcThinkingIndicator,
  GameStatusSidebar,
  GameInputArea,
  SaveGameModal,
  LoadGameModal,
  StoryModal,
  CharacterDetailsModal,
} from '../components/Game'
import styles from './GamePage.module.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type OpenModal = 'save' | 'load' | 'story' | 'characterDetails' | null

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

/** Build provider config from the connection store. */
function buildProvider(): Record<string, unknown> | undefined {
  const { baseUrl, model, providerType, apiKey } = useConnectionStore.getState()
  if (!baseUrl || !model) return undefined
  return {
    base_url: baseUrl,
    model,
    provider_type: providerType,
    api_key: apiKey ?? undefined,
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function GamePage() {
  const navigate = useNavigate()

  // ---- Stores ----
  const character = useCharacterStore((s) => s.currentCharacter)
  const isActive = useGameStore((s) => s.isActive)
  const worldState = useGameStore((s) => s.worldState)
  const storeError = useGameStore((s) => s.error)

  // ---- Actions ----
  const setProcessing = useGameStore((s) => s.setProcessing)
  const setIsActive = useGameStore((s) => s.setIsActive)

  // ---- Game stream hook ----
  const { connect, disconnect, isConnecting, error: streamError } = useGameStream()
  const displayError = streamError ?? storeError

  // ---- Browser-level beforeunload: warn on refresh/close when game is active ----
  useEffect(() => {
    if (!isActive) return

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isActive])

  // ---- Modal state ----
  const [openModal, setOpenModal] = useState<OpenModal>(null)
  const closeModal = useCallback(() => setOpenModal(null), [])

  // ---- Track if we've auto-started the game ----
  const startedRef = useRef(false)

  // ---- Ref for worldState to avoid handleSubmit recreation on every SSE event ----
  const worldStateRef = useRef(worldState)
  useEffect(() => {
    worldStateRef.current = worldState
  }, [worldState])

  // ==================================================================
  // Game Start: auto-connect if character exists but game not active
  // ==================================================================
  useEffect(() => {
    if (character && !isActive && !startedRef.current) {
      startedRef.current = true

      connect({
        input: 'start',
        character: character as unknown as Record<string, unknown>,
        provider: buildProvider(),
      })
      setIsActive(true)
    }
    return () => {
      startedRef.current = false // allow StrictMode retry
    }
  }, [character, isActive, connect])

  // ==================================================================
  // Submit: user sends a turn
  // ==================================================================
  const handleSubmit = useCallback(
    (input: string) => {
      useGameStore.getState().addNarrativeEntry({ type: 'player', content: input })
      setProcessing(true)
      useGameStore.getState().setIsThinking(true)
      connect({
        input,
        character: character as unknown as Record<string, unknown>,
        state: worldStateRef.current ?? undefined,
        provider: buildProvider(),
      })
    },
    [connect, character, setProcessing],
  )

  // ==================================================================
  // Modal openers
  // ==================================================================
  const openSaveModal = useCallback(() => setOpenModal('save'), [])
  const openLoadModal = useCallback(() => setOpenModal('load'), [])
  const openStoryModal = useCallback(() => setOpenModal('story'), [])
  const openCharDetailsModal = useCallback(() => setOpenModal('characterDetails'), [])

  // ==================================================================
  // New Game: disconnect and go to character page
  // ==================================================================
  const handleNewGame = useCallback(() => {
    disconnect()
    setIsActive(false)
    navigate('/character')
  }, [disconnect, navigate, setIsActive])

  // ==================================================================
  // Load Game: called by LoadGameModal.onLoaded
  // ==================================================================
  const handleLoaded = useCallback(
    (state: Record<string, unknown>, loadedCharacter?: Record<string, unknown>) => {
      // Clean slate and populate stores with loaded data
      useGameStore.getState().resetGame()
      useGameStore.getState().setWorldState(state)

      // Populate narrative entries from saved story log
      const storyLog = state.story_log as string[] | undefined
      if (storyLog && Array.isArray(storyLog)) {
        for (const entry of storyLog) {
          useGameStore.getState().addNarrativeEntry({ type: 'narrative', content: entry })
        }
      }
      const storySummary = state.story_summary as string[] | undefined
      if (storySummary && Array.isArray(storySummary)) {
        for (const entry of storySummary) {
          useGameStore.getState().addNarrativeEntry({ type: 'narrative', content: entry })
        }
      }

      // Restore player input entries from saved user_input_history
      const userInputHistory = state.user_input_history as string[] | undefined
      if (userInputHistory && Array.isArray(userInputHistory)) {
        for (const input of userInputHistory) {
          useGameStore.getState().addNarrativeEntry({ type: 'player', content: input })
        }
      }

      // Restore full narrative entries (including tool results, separators, etc.)
      // from the rich _narrative_entries payload if available
      const narrativeEntries = state._narrative_entries as
        | Array<{ type: string; content: string }>
        | undefined
      if (narrativeEntries && Array.isArray(narrativeEntries) && narrativeEntries.length > 0) {
        // If we have rich entries, use them instead of the individual adds above
        useGameStore.getState().setNarrativeEntries(
          narrativeEntries.map((e) => ({
            id: crypto.randomUUID(),
            type: e.type as 'player' | 'narrative' | 'tool_result' | 'separator' | 'error',
            content: e.content,
            timestamp: Date.now(),
          })),
        )
      }

      if (loadedCharacter) {
        // Loaded character comes from API response — cast through as any
        useCharacterStore
          .getState()
          .setCurrentCharacter(loadedCharacter as unknown as Character)
      }

      startedRef.current = true
      connect({
        input: 'start',
        state,
        character: (loadedCharacter as Record<string, unknown>) ?? undefined,
        provider: buildProvider(),
      })
      setIsActive(true)
      setOpenModal(null)
    },
    [connect, setIsActive],
  )

  // ==================================================================
  // Render: Empty State (no character)
  // ==================================================================
  if (!character) {
    return (
      <div className={styles.page}>
        <div className={styles.emptyState}>
          <span className={styles.emptyIcon} aria-hidden="true">
            ⚔️
          </span>
          <h2 className={styles.emptyTitle}>No Character Found</h2>
          <p className={styles.emptyText}>
            Create a character first before starting your adventure.
          </p>
          <button
            type="button"
            className={styles.startBtn}
            onClick={() => navigate('/character')}
          >
            Create Character
          </button>
        </div>
      </div>
    )
  }

  // ==================================================================
  // Render: Connecting State
  // ==================================================================
  if (isConnecting && !isActive) {
    return (
      <div className={styles.page}>
        <div className={styles.connectingState}>
          <div className={styles.coinFlip} aria-hidden="true">
            🪙
          </div>
          <h2 className={styles.connectingTitle}>Entering the Realm...</h2>
          <p className={styles.connectingText}>
            The Dungeon Master is weaving your tale...
          </p>
        </div>
      </div>
    )
  }

  // ==================================================================
  // Render: Full Game Layout
  // ==================================================================
  return (
    <div className={styles.gameLayout}>
      {/* ====== Main Content Column ====== */}
      <div className={styles.mainArea}>
        {/* Header bar */}
        <div className={styles.gameHeader}>
          <h2 className={styles.gameTitle}>
            <span aria-hidden="true">⚔️</span> Adventure Log
          </h2>
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.headerBtn}
              onClick={openStoryModal}
              aria-label="View adventure story"
              title="Adventure Story"
            >
              📖 Story
            </button>
            <button
              type="button"
              className={styles.headerBtn}
              onClick={openCharDetailsModal}
              aria-label="View character details"
              title="Character Details"
            >
              🧙 Character
            </button>
          </div>
        </div>

        {/* Error banner */}
        {displayError && (
          <div className={styles.errorBanner} role="alert">
            <span aria-hidden="true">⚠️</span> {displayError}
          </div>
        )}

        {/* Narrative area (scrollable) */}
        <div className={styles.narrativeArea}>
          <NarrativeStream />
        </div>

        {/* Thinking indicators */}
        <div className={styles.thinkingArea}>
          <ThinkingIndicator />
          <NpcThinkingIndicator />
        </div>

        {/* Input area */}
        <GameInputArea
          onSave={openSaveModal}
          onLoad={openLoadModal}
          onNewGame={handleNewGame}
          onSubmit={handleSubmit}
        />
      </div>

      {/* ====== Sidebar Column ====== */}
      <div className={styles.sidebarArea}>
        <GameStatusSidebar />
      </div>

      {/* ====== Modals ====== */}
      <SaveGameModal isOpen={openModal === 'save'} onClose={closeModal} />
      <LoadGameModal
        isOpen={openModal === 'load'}
        onClose={closeModal}
        onLoaded={handleLoaded}
      />
      <StoryModal isOpen={openModal === 'story'} onClose={closeModal} />
      <CharacterDetailsModal
        isOpen={openModal === 'characterDetails'}
        onClose={closeModal}
      />
    </div>
  )
}
