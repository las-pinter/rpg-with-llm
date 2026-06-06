/** Game state — structured narrative, streaming, tokens, and world state during gameplay. */

import { create } from 'zustand'

export interface NarrativeEntry {
  /** Unique ID for this entry. */
  id: string
  /** Entry type classification. */
  type: 'player' | 'narrative' | 'tool_result' | 'separator' | 'error'
  /** The text content of the entry. */
  content: string
  /** Date.now() when created. */
  timestamp: number
}

export interface TokenUsage {
  /** Total tokens consumed so far. */
  accumulated: number
  /** Tokens from the most recent turn. */
  latest: number
}

export interface GameState {
  /** The accumulated narrative text (legacy, for backward compatibility). */
  narrative: string
  /** The raw world state from the server. */
  worldState: Record<string, unknown> | null
  /** The current player input. */
  playerInput: string
  /** Whether the DM is processing a turn. */
  processing: boolean
  /** Whether the game session is active. */
  isActive: boolean
  /** Error from the last game operation. */
  error: string | null
}

interface ExpandedGameState extends GameState {
  /** Structured narrative entries replacing plain string narrative. */
  narrativeEntries: NarrativeEntry[]
  /** Current SSE streaming text being built. */
  streamingText: string
  /** DM is thinking indicator. */
  isThinking: boolean
  /** NPC currently thinking, or null. */
  npcThinking: { npcId: string; hint: string } | null
  /** How many turns have been played. */
  turnCount: number
  /** Token consumption tracking. */
  tokenUsage: TokenUsage
  /** Whether to auto-scroll narrative on new entries. */
  autoScroll: boolean
  /** Toggle token display visibility. */
  showTokens: boolean
}

export interface GameActions {
  appendNarrative: (text: string) => void
  setNarrative: (narrative: string) => void
  setWorldState: (state: Record<string, unknown> | null) => void
  setPlayerInput: (input: string) => void
  setProcessing: (processing: boolean) => void
  setIsActive: (isActive: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

interface ExpandedGameActions extends GameActions {
  addNarrativeEntry: (entry: Omit<NarrativeEntry, 'id' | 'timestamp'>) => void
  setNarrativeEntries: (entries: NarrativeEntry[]) => void
  setStreamingText: (text: string) => void
  setIsThinking: (thinking: boolean) => void
  setNpcThinking: (npcId: string | null, hint?: string) => void
  incrementTurnCount: () => void
  setTokenUsage: (usage: Partial<TokenUsage>) => void
  toggleAutoScroll: () => void
  setShowTokens: (show: boolean) => void
  applyStateUpdate: (
    updates: Record<string, { action: 'set' | 'add' | 'append' | 'remove'; value?: unknown }>,
  ) => void
  resetGame: () => void
}

export type GameStore = ExpandedGameState & ExpandedGameActions

const initialState: ExpandedGameState = {
  narrative: '',
  worldState: null,
  playerInput: '',
  processing: false,
  isActive: false,
  error: null,
  narrativeEntries: [],
  streamingText: '',
  isThinking: false,
  npcThinking: null,
  turnCount: 0,
  tokenUsage: { accumulated: 0, latest: 0 },
  autoScroll: true,
  showTokens: false,
}

/** Segments that are NEVER allowed in dot-path access — blocks prototype pollution vectors. */
const FORBIDDEN_SEGMENTS = new Set(['__proto__', 'prototype', 'constructor'])

/** Safe path segments — matches valid JS identifier dot-paths. */
const safePathRegex = /^([a-zA-Z_$][\w$]*)+(\.([a-zA-Z_$][\w$]*))*$/

function validatePath(path: string): boolean {
  if (!safePathRegex.test(path)) return false
  const segments = path.split('.')
  return !segments.some((seg) => FORBIDDEN_SEGMENTS.has(seg))
}

function setByDotPath(obj: Record<string, unknown>, path: string, value: unknown): void {
  const segments = path.split('.')
  let current: Record<string, unknown> = obj

  for (let i = 0; i < segments.length - 1; i += 1) {
    const segment = segments[i]

    if (!Object.hasOwn(current, segment)) {
      current[segment] = Object.create(null) // break proto chain
    }

    current = current[segment] as Record<string, unknown>
  }

  const lastKey = segments[segments.length - 1]!
  current[lastKey] = value
}

function applyAction(
  target: Record<string, unknown>,
  path: string,
  action: 'set' | 'add' | 'append' | 'remove',
  value?: unknown,
): void {
  const segments = path.split('.')
  let current: Record<string, unknown> = target

  for (let i = 0; i < segments.length - 1; i += 1) {
    const segment = segments[i]

    if (!Object.hasOwn(current, segment)) {
      current[segment] = Object.create(null) // break proto chain
    }

    current = current[segment] as Record<string, unknown>
  }

  const key = segments[segments.length - 1]!

  switch (action) {
    case 'set':
      current[key] = value ?? null
      break
    case 'add':
      if (typeof current[key] === 'number') {
        current[key] += (value as number) ?? 0
      } else {
        current[key] = (value as number) ?? 0
      }
      break
    case 'append':
      if (Array.isArray(current[key])) {
        ;(current[key] as unknown[]).push(value)
      } else if (typeof current[key] === 'string') {
        current[key] = (current[key] as string) + String(value ?? '')
      } else {
        current[key] = value
      }
      break
    case 'remove':
      // Traverse using hasOwn to avoid prototype chain
      for (let i = 0; i < segments.length - 1; i += 1) {
        if (!Object.hasOwn(current, segments[i]!)) return
        current = current[segments[i]!] as Record<string, unknown>
      }
      delete current[key]
      break
  }
}

export const useGameStore = create<GameStore>()((set, get) => ({
  ...initialState,

  // Legacy actions (backward-compatible)
  appendNarrative: (text) => set((state) => ({ narrative: state.narrative + text })),
  setNarrative: (narrative) => set({ narrative }),
  setWorldState: (worldState) => set({ worldState }),
  setPlayerInput: (playerInput) => set({ playerInput }),
  setProcessing: (processing) => set({ processing }),
  setIsActive: (isActive) => set({ isActive }),
  setError: (error) => set({ error }),

  // New structured narrative actions
  addNarrativeEntry: ({ type, content }) => {
    const id = crypto.randomUUID()
    const timestamp = Date.now()

    set((state) => ({
      narrativeEntries: [
        ...state.narrativeEntries,
        { id, type, content, timestamp },
      ],
    }))
  },

  // Bulk-set narrative entries (used when loading a saved game)
  setNarrativeEntries: (entries) => set({ narrativeEntries: entries }),

  // Streaming and thinking state
  setStreamingText: (text) => set({ streamingText: text }),
  setIsThinking: (thinking) => set({ isThinking: thinking }),

  setNpcThinking: (npcId, hint = '') => {
    if (npcId === null) {
      set({ npcThinking: null })
    } else {
      set({ npcThinking: { npcId, hint } })
    }
  },

  // Turn and token tracking
  incrementTurnCount: () => set((state) => ({ turnCount: state.turnCount + 1 })),

  setTokenUsage: (usage) =>
    set((state) => ({
      tokenUsage: {
        accumulated: usage.accumulated ?? state.tokenUsage.accumulated,
        latest: usage.latest ?? state.tokenUsage.latest,
      },
    })),

  // UI toggles
  toggleAutoScroll: () => set((state) => ({ autoScroll: !state.autoScroll })),
  setShowTokens: (show) => set({ showTokens: show }),

  // Apply state changes — mirrors vanilla JS _applyStateChanges
  applyStateUpdate: (updates) => {
    const oldState = get().worldState
    // Deep clone to produce a new reference — React's Object.is sees a change
    const worldState: Record<string, unknown> =
      oldState !== null ? JSON.parse(JSON.stringify(oldState)) : {}

    for (const [path, { action, value }] of Object.entries(updates)) {
      if (!validatePath(path)) continue

      switch (action) {
        case 'set':
          setByDotPath(worldState, path, value ?? null)
          break
        case 'add':
          applyAction(worldState, path, action, value)
          break
        case 'append':
          applyAction(worldState, path, action, value)
          break
        case 'remove':
          applyAction(worldState, path, action, value)
          break
      }
    }

    // New reference ensures React re-renders
    set({ worldState })
  },

  // Full reset (legacy — resets everything to initial state)
  reset: () => set(initialState),

  // Game-specific reset (keeps autoScroll/showTokens settings)
  resetGame: () => {
    const autoScroll = get().autoScroll
    const showTokens = get().showTokens

    set({
      ...initialState,
      narrativeEntries: [],
      tokenUsage: { accumulated: 0, latest: 0 },
      autoScroll,
      showTokens,
    })
  },
}))
