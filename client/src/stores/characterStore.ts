/** Character state — current player character and list of saved characters. */

import { create } from 'zustand'
import type { Character } from '../api/types'

export interface CharacterState {
  /** Currently loaded/selected character, or null if none. */
  currentCharacter: Character | null
  /** List of saved characters. */
  savedCharacters: Character[]
  /** Whether a character operation is in progress. */
  loading: boolean
  /** Error from the last character operation. */
  error: string | null
}

export interface CharacterActions {
  setCurrentCharacter: (character: Character | null) => void
  setSavedCharacters: (characters: Character[]) => void
  addSavedCharacter: (character: Character) => void
  removeSavedCharacter: (name: string) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

export type CharacterStore = CharacterState & CharacterActions

const initialState: CharacterState = {
  currentCharacter: null,
  savedCharacters: [],
  loading: false,
  error: null,
}

export const useCharacterStore = create<CharacterStore>()((set) => ({
  ...initialState,
  setCurrentCharacter: (currentCharacter) => set({ currentCharacter }),
  setSavedCharacters: (savedCharacters) => set({ savedCharacters }),
  addSavedCharacter: (character) =>
    set((state) => ({
      savedCharacters: [...state.savedCharacters, character],
    })),
  removeSavedCharacter: (name) =>
    set((state) => ({
      savedCharacters: state.savedCharacters.filter((c) => c.name !== name),
    })),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  reset: () => set(initialState),
}))
