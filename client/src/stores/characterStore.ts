/** Character state — creation flow, point-buy logic, campfire story, review, and load tab. */

import { create } from 'zustand'
import type {
  Character,
  CharacterRules,
  SaveMeta,
  CharacterListItem,
  CharactersListResponse,
  SavesListResponse,
} from '../api/types'
import {
  listCharacters,
  listSaves,
  loadCharacterById as apiLoadCharacterById,
  deleteCharacterById as apiDeleteCharacterById,
  loadGame,
  deleteSave,
} from '../api/endpoints'
import { useGameStore } from './gameStore'

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

export interface CharacterState {
  /** Currently loaded/selected character for gameplay, or null. */
  currentCharacter: Character | null
  /** List of saved characters (metadata only). */
  savedCharacters: CharacterListItem[]
  /** List of saved games. */
  savedGames: SaveMeta[]
  /** Whether a character operation is in progress. */
  loading: boolean
  /** General error message. */
  error: string | null

  /** Character creation rules fetched from the backend. */
  rules: CharacterRules | null
  /** Whether rules are currently being fetched. */
  rulesLoading: boolean
  /** Error from the rules fetch. */
  rulesError: string | null

  // ------------------------------------------------------------------
  // Point-buy ability scores
  // ------------------------------------------------------------------

  /** Current ability scores during point-buy. */
  abilities: Record<string, number>
  /** Currently selected class for point-buy defaults. */
  selectedClass: string
  /** Remaining point-buy points. */
  remainingPoints: number

  // ------------------------------------------------------------------
  // Creation mode
  // ------------------------------------------------------------------

  /** Which creation sub-mode is active. */
  creationMode: 'campfire' | 'manual' | 'review'
  /** Which top-level tab is active: 'create' or 'load'. */
  activeTab: 'create' | 'load'

  // ------------------------------------------------------------------
  // Campfire story
  // ------------------------------------------------------------------

  /** Array of story answer strings (one per question). */
  storyAnswers: string[]
  /** Index of the currently visible story question. */
  currentQuestion: number

  // ------------------------------------------------------------------
  // Generated / created character
  // ------------------------------------------------------------------

  /** Character returned from generate or create API (pre-adventure). */
  generatedCharacter: Character | null
  /** Whether the review sheet is in edit mode. */
  isEditing: boolean

  // ------------------------------------------------------------------
  // Manual creation form fields
  // ------------------------------------------------------------------

  manualName: string
  manualAppearance: string
  manualBackstory: string
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export interface CharacterActions {
  // ---- Simple setters ----

  setCurrentCharacter: (character: Character | null) => void
  setSavedCharacters: (characters: CharacterListItem[]) => void
  setSavedGames: (saves: SaveMeta[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setRules: (rules: CharacterRules) => void
  setRulesLoading: (loading: boolean) => void
  setRulesError: (error: string | null) => void
  setAbilities: (abilities: Record<string, number>) => void
  setSelectedClass: (selectedClass: string) => void
  setRemainingPoints: (points: number) => void
  setCreationMode: (mode: 'campfire' | 'manual' | 'review') => void
  setActiveTab: (tab: 'create' | 'load') => void
  setStoryAnswers: (answers: string[]) => void
  setCurrentQuestion: (index: number) => void
  setGeneratedCharacter: (character: Character | null) => void
  setIsEditing: (editing: boolean) => void
  setManualName: (name: string) => void
  setManualAppearance: (appearance: string) => void
  setManualBackstory: (backstory: string) => void

  /** Multi-field update (like setSettings in connectionStore). */
  setState: (partial: Partial<CharacterState>) => void

  /** Reset all state to initial values. */
  reset: () => void

  // ---- Point-buy logic ----

  /** Get the point-buy cost for a given ability score. */
  getCost: (score: number) => number
  /** Whether an ability can be increased (within point-buy limits). */
  canIncrease: (abil: string) => boolean
  /** Whether an ability can be decreased (above min score). */
  canDecrease: (abil: string) => boolean
  /** Increase ability score by 1 (point-buy permitting). */
  increaseAbility: (abil: string) => void
  /** Decrease ability score by 1. */
  decreaseAbility: (abil: string) => void
  /** Apply class default ability scores and recalculate remaining points. */
  applyClassDefaults: () => void
  /** Initialise defaults from loaded rules. */
  initDefaults: () => void

  // ---- Campfire navigation ----

  /** Store the answer at the given index (or currentQuestion if omitted). */
  saveCurrentAnswer: (answer: string, index?: number) => void
  /** Move to the next story question. */
  nextQuestion: () => void
  /** Move to the previous story question. */
  prevQuestion: () => void
  /** Jump to a specific story question by index. */
  goToQuestion: (index: number) => void

  // ---- Load tab ----

  /** Fetch saved characters list from the backend. Returns API response for callers that need it. */
  fetchCharacters: () => Promise<CharactersListResponse>
  /** Fetch saved games list from the backend. Returns API response for callers that need it. */
  fetchSaves: () => Promise<SavesListResponse>
  /** Load a character by ID and set it as currentCharacter. */
  loadCharacterById: (id: string) => Promise<void>
  /** Delete a character by ID and refresh the list. */
  deleteCharacterById: (id: string) => Promise<void>
  /** Load a saved game by slug. */
  loadSaveGame: (slug: string) => Promise<void>
  /** Delete a saved game and refresh the list. */
  deleteSaveGame: (slug: string) => Promise<void>
}

// ---------------------------------------------------------------------------
// Store type
// ---------------------------------------------------------------------------

export type CharacterStore = CharacterState & CharacterActions

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

const initialState: CharacterState = {
  currentCharacter: null,
  savedCharacters: [],
  savedGames: [],
  loading: false,
  error: null,
  rules: null,
  rulesLoading: false,
  rulesError: null,
  abilities: {},
  selectedClass: '',
  remainingPoints: 27,
  creationMode: 'campfire',
  activeTab: 'create',
  storyAnswers: [],
  currentQuestion: 0,
  generatedCharacter: null,
  isEditing: false,
  manualName: '',
  manualAppearance: '',
  manualBackstory: '',
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useCharacterStore = create<CharacterStore>()((set, get) => ({
  ...initialState,

  // ---- Simple setters ----

  setCurrentCharacter: (currentCharacter) => set({ currentCharacter }),
  setSavedCharacters: (savedCharacters) => set({ savedCharacters }),
  setSavedGames: (savedGames) => set({ savedGames }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setRules: (rules) => set({ rules }),
  setRulesLoading: (rulesLoading) => set({ rulesLoading }),
  setRulesError: (rulesError) => set({ rulesError }),
  setAbilities: (abilities) => set({ abilities }),
  setSelectedClass: (selectedClass) => set({ selectedClass }),
  setRemainingPoints: (remainingPoints) => set({ remainingPoints }),
  setCreationMode: (creationMode) => set({ creationMode }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setStoryAnswers: (storyAnswers) => set({ storyAnswers }),
  setCurrentQuestion: (currentQuestion) => set({ currentQuestion }),
  setGeneratedCharacter: (generatedCharacter) => set({ generatedCharacter }),
  setIsEditing: (isEditing) => set({ isEditing }),
  setManualName: (manualName) => set({ manualName }),
  setManualAppearance: (manualAppearance) => set({ manualAppearance }),
  setManualBackstory: (manualBackstory) => set({ manualBackstory }),

  setState: (partial) => set(partial),

  reset: () => set(initialState),

  // ---- Point-buy logic ----

  getCost: (score) => {
    const { rules } = get()
    const costs = rules?.point_buy?.costs ?? {}
    return costs[String(score)] ?? 0
  },

  canIncrease: (abil) => {
    const { abilities, rules, remainingPoints } = get()
    // Treat missing scores as min_score (matches UI default in AbilityGrid)
    const minScore = rules?.point_buy?.min_score ?? 8
    const score = abilities[abil] ?? minScore
    if (typeof score !== 'number' || isNaN(score)) return false
    const maxScore = rules?.point_buy?.max_score ?? 15
    if (score >= maxScore) return false
    const getCost = get().getCost
    const nextScore = score + 1
    const nextCost = getCost(nextScore)
    const currentCost = getCost(score)
    const pointCost = nextCost - currentCost
    return remainingPoints >= pointCost
  },

  canDecrease: (abil) => {
    const { abilities, rules } = get()
    // Treat missing scores as min_score (matches UI default in AbilityGrid)
    const minScore = rules?.point_buy?.min_score ?? 8
    const score = abilities[abil] ?? minScore
    if (typeof score !== 'number' || isNaN(score)) return false
    return score > minScore
  },

  increaseAbility: (abil) => {
    const state = get()
    if (!state.canIncrease(abil)) return
    const oldScore = state.abilities[abil]
    const getCost = state.getCost
    const oldCost = getCost(oldScore)
    const newScore = oldScore + 1
    const newCost = getCost(newScore)
    const pointCost = newCost - oldCost
    set({
      abilities: { ...state.abilities, [abil]: newScore },
      remainingPoints: state.remainingPoints - pointCost,
    })
  },

  decreaseAbility: (abil) => {
    const state = get()
    if (!state.canDecrease(abil)) return
    const oldScore = state.abilities[abil]
    const getCost = state.getCost
    const oldCost = getCost(oldScore)
    const newScore = oldScore - 1
    const newCost = getCost(newScore)
    const pointRefund = oldCost - newCost
    set({
      abilities: { ...state.abilities, [abil]: newScore },
      remainingPoints: state.remainingPoints + pointRefund,
    })
  },

  applyClassDefaults: () => {
    const state = get()
    const { rules, selectedClass } = state
    const templates = rules?.class_templates
    if (!templates) return
    const template = templates[selectedClass]
    if (!template) return
    const getCost = state.getCost
    const templateAbilities = { ...template.abilities }
    let remainingPoints = rules?.point_buy?.max_points ?? 27
    for (const score of Object.values(templateAbilities)) {
      remainingPoints -= getCost(score)
    }
    set({
      abilities: templateAbilities,
      remainingPoints,
    })
  },

  initDefaults: () => {
    const state = get()
    const rules = state.rules
    if (!rules) return

    // Default to flat 8s
    const defaultAbilities: Record<string, number> = {}
    for (const abil of rules.standard_abilities) {
      defaultAbilities[abil] = 8
    }

    const firstClass = rules.valid_classes[0]
    let abilities = { ...defaultAbilities }
    let selectedClass = firstClass ?? ''
    let remainingPoints = rules.point_buy.max_points

    // Override with first class template if available
    if (firstClass && rules.class_templates[firstClass]) {
      const template = rules.class_templates[firstClass]
      abilities = { ...abilities, ...template.abilities }
      const getCost = state.getCost
      for (const score of Object.values(template.abilities)) {
        remainingPoints -= getCost(score)
      }
    }

    set({
      abilities,
      selectedClass,
      remainingPoints,
      storyAnswers: new Array(rules.assisted_creation_questions.length).fill(''),
      currentQuestion: 0,
  creationMode: 'campfire',
  activeTab: 'create',
      generatedCharacter: null,
      isEditing: false,
      manualName: '',
      manualAppearance: '',
      manualBackstory: '',
    })
  },

  // ---- Campfire navigation ----

  saveCurrentAnswer: (answer, index) => {
    const { currentQuestion, storyAnswers } = get()
    const idx = index ?? currentQuestion
    if (idx < 0) return
    const updated = [...storyAnswers]
    // Grow the array if idx is beyond bounds (e.g. before initDefaults)
    while (updated.length <= idx) {
      updated.push('')
    }
    updated[idx] = answer
    set({ storyAnswers: updated })
  },

  nextQuestion: () => {
    const { currentQuestion, storyAnswers } = get()
    const total = storyAnswers.length
    if (currentQuestion < total - 1) {
      set({ currentQuestion: currentQuestion + 1 })
    }
  },

  prevQuestion: () => {
    const { currentQuestion } = get()
    if (currentQuestion > 0) {
      set({ currentQuestion: currentQuestion - 1 })
    }
  },

  goToQuestion: (index) => {
    set({ currentQuestion: index })
  },

  // ---- Load tab ----

  fetchCharacters: async () => {
    const response = await listCharacters()
    if (response.ok) {
      set({ savedCharacters: response.characters })
    }
    return response
  },

  fetchSaves: async () => {
    const response = await listSaves()
    if (response.ok) {
      set({ savedGames: response.saves })
    }
    return response
  },

  loadCharacterById: async (id) => {
    set({ loading: true, error: null })
    try {
      const response = await apiLoadCharacterById(id)
      if (response.ok) {
        set({ currentCharacter: response.character, loading: false })
      } else {
        set({ error: 'Failed to load character', loading: false })
      }
    } catch (err: unknown) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load character',
        loading: false,
      })
    }
  },

  deleteCharacterById: async (id) => {
    try {
      await apiDeleteCharacterById(id)
      await get().fetchCharacters()
    } catch {
      // Silently fail
    }
  },

  loadSaveGame: async (slug) => {
    set({ loading: true, error: null })
    try {
      const response = await loadGame(slug)
      if (!response.ok) {
        set({ error: 'Failed to load save', loading: false })
        return
      }

      // Populate game store with world state
      useGameStore.getState().setWorldState(response.state)

      // Set character if save embeds one
      if (response.character) {
        set({ currentCharacter: response.character as unknown as Character })
      }

      set({ loading: false })
    } catch (err: unknown) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load save',
        loading: false,
      })
    }
  },

  deleteSaveGame: async (slug) => {
    try {
      await deleteSave(slug)
      await get().fetchSaves()
    } catch {
      // Silently fail
    }
  },
}))
