/** Character state — creation flow, point-buy logic, campfire story, review, and load tab. */

import { create } from 'zustand'
import type {
  Character,
  CharacterRules,
  SaveMeta,
  CharacterListItem,
  CharactersListResponse,
  SavesListResponse,
  DerivedSheet,
} from '../api/types'
import {
  listCharacters,
  listSaves,
  loadCharacterById as apiLoadCharacterById,
  deleteCharacterById as apiDeleteCharacterById,
  getCharacterSheet as apiGetCharacterSheet,
  loadGame,
  deleteSave,
} from '../api/endpoints'
import { useGameStore, type NarrativeEntry } from './gameStore'

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

export interface CharacterState {
  /** Currently loaded/selected character for gameplay, or null. */
  currentCharacter: Character | null
  /** Derived sheet for the current character (computed stats). */
  derivedSheet: DerivedSheet | null
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
  setDerivedSheet: (sheet: DerivedSheet | null) => void
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
  /** Fetch the derived sheet for a character and store it. */
  fetchCharacterSheet: (id: string) => Promise<void>
  /** Delete a character by ID and refresh the list. */
  deleteCharacterById: (id: string) => Promise<void>
  /** Load a saved game by slug. */
  loadSaveGame: (slug: string) => Promise<void>
  /** Delete a saved game and refresh the list. */
  deleteSaveGame: (slug: string) => Promise<void>
  /** Load a character into the manual creation form for review/editing. */
  loadCharacterIntoForm: (character: Character) => void
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
  derivedSheet: null,
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

  setCurrentCharacter: (currentCharacter) => set({ currentCharacter, derivedSheet: null }),
  setDerivedSheet: (derivedSheet) => set({ derivedSheet }),
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
        set({ currentCharacter: response.character, derivedSheet: null, loading: false })
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

  fetchCharacterSheet: async (id) => {
    try {
      const response = await apiGetCharacterSheet(id)
      if (response.ok) {
        set({ derivedSheet: response.sheet })
      }
    } catch {
      // Silently fail — derived sheet is non-critical
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

      // Clean slate and populate game store with world state
      useGameStore.getState().resetGame()
      useGameStore.getState().setWorldState(response.state)

      // Populate narrative entries from save data
      // Priority: rich _narrative_entries > story_summary > story_log + user_input_history
      const gameState = useGameStore.getState()
      const richEntries = response.state._narrative_entries as
        | Array<{ type: string; content: string }>
        | undefined

      if (richEntries && Array.isArray(richEntries) && richEntries.length > 0) {
        // Primary: rich narrative entries (full conversation)
        for (const e of richEntries) {
          gameState.addNarrativeEntry({
            type: (e.type || 'narrative') as NarrativeEntry['type'],
            content: e.content,
          })
        }
      } else {
        // Fallback paths for legacy saves
        const storySummary = response.state.story_summary as string[] | undefined
        if (storySummary && Array.isArray(storySummary) && storySummary.length > 0) {
          for (const entry of storySummary) {
            gameState.addNarrativeEntry({ type: 'narrative', content: entry })
          }
        } else {
          // Last resort — merge story_log and user_input_history
          const storyLog = response.state.story_log as string[] | undefined
          if (storyLog && Array.isArray(storyLog)) {
            for (const entry of storyLog) {
              gameState.addNarrativeEntry({ type: 'narrative', content: entry })
            }
          }

          const userInputHistory = response.state.user_input_history as string[] | undefined
          if (userInputHistory && Array.isArray(userInputHistory)) {
            for (const input of userInputHistory) {
              gameState.addNarrativeEntry({ type: 'player', content: input })
            }
          }
        }
      }

      // Set character if save embeds one
      if (response.character) {
        set({ currentCharacter: response.character as unknown as Character })
      }

      // Activate the game — resetGame above sets isActive=false, so
      // re-activate here to prevent the "Entering the Realm…" overlay
      // from showing when the user submits their first prompt.
      useGameStore.getState().setIsActive(true)

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

  loadCharacterIntoForm: (character) => set({
    manualName: character.name || '',
    manualAppearance: character.appearance || '',
    manualBackstory: character.backstory || '',
    abilities: { ...character.abilities },
    selectedClass: character.character_class,
    remainingPoints: 0,
    creationMode: 'manual',
    generatedCharacter: null,
    isEditing: false,
  }),
}))
