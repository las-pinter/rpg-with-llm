/** Game state — current turn, narrative, and world state during gameplay. */

import { create } from 'zustand'

export interface GameState {
  /** The accumulated narrative text. */
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

export type GameStore = GameState & GameActions

const initialState: GameState = {
  narrative: '',
  worldState: null,
  playerInput: '',
  processing: false,
  isActive: false,
  error: null,
}

export const useGameStore = create<GameStore>()((set) => ({
  ...initialState,
  appendNarrative: (text) => set((state) => ({ narrative: state.narrative + text })),
  setNarrative: (narrative) => set({ narrative }),
  setWorldState: (worldState) => set({ worldState }),
  setPlayerInput: (playerInput) => set({ playerInput }),
  setProcessing: (processing) => set({ processing }),
  setIsActive: (isActive) => set({ isActive }),
  setError: (error) => set({ error }),
  reset: () => set(initialState),
}))
