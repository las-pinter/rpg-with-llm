import { vi, describe, it, expect, beforeEach } from 'vitest'

// Mock API module before any imports that use it
vi.mock('../api/endpoints', () => ({
  listCharacters: vi.fn(),
  listSaves: vi.fn(),
  loadCharacterById: vi.fn(),
  deleteCharacterById: vi.fn(),
  loadGame: vi.fn(),
  deleteSave: vi.fn(),
}))

import { listCharacters, loadCharacterById } from '../api/endpoints'
import { useConnectionStore } from '../stores/connectionStore'
import { useCharacterStore } from '../stores/characterStore'
import { useGameStore } from '../stores/gameStore'
import type { CharacterListItem } from '../api/types'

describe('connectionStore', () => {
  beforeEach(() => {
    useConnectionStore.getState().reset()
  })

  it('has default values', () => {
    const state = useConnectionStore.getState()
    expect(state.baseUrl).toBe('http://localhost:11434')
    expect(state.model).toBe('llama3.2')
    expect(state.providerType).toBe('ollama')
    expect(state.checking).toBe(false)
    expect(state.healthOk).toBeNull()
  })

  it('updates baseUrl', () => {
    useConnectionStore.getState().setBaseUrl('http://example.com')
    expect(useConnectionStore.getState().baseUrl).toBe('http://example.com')
  })

  it('updates model', () => {
    useConnectionStore.getState().setModel('gpt-4')
    expect(useConnectionStore.getState().model).toBe('gpt-4')
  })

  it('sets health result', () => {
    useConnectionStore.getState().setHealthResult(true, 42, null)
    const state = useConnectionStore.getState()
    expect(state.healthOk).toBe(true)
    expect(state.latencyMs).toBe(42)
    expect(state.healthError).toBeNull()
    expect(state.checking).toBe(false)
  })

  it('resets to initial state', () => {
    useConnectionStore.getState().setBaseUrl('http://other.com')
    useConnectionStore.getState().setModel('other-model')
    useConnectionStore.getState().reset()
    const state = useConnectionStore.getState()
    expect(state.baseUrl).toBe('http://localhost:11434')
    expect(state.model).toBe('llama3.2')
  })

  it('has new default values for agent settings', () => {
    const state = useConnectionStore.getState()
    expect(state.dm_max_tokens).toBe(16000)
    expect(state.dm_temperature).toBe(0.8)
    expect(state.dm_timeout).toBe(120)
    expect(state.npc_max_tokens).toBe(1024)
    expect(state.npc_temperature).toBe(0.7)
    expect(state.npc_timeout).toBe(60)
    expect(state.summarizer_max_tokens).toBe(16000)
    expect(state.summarizer_temperature).toBe(0.7)
    expect(state.summarizer_timeout).toBe(120)
  })

  it('has new default values for provider-level and status fields', () => {
    const state = useConnectionStore.getState()
    expect(state.timeout).toBe(300)
    expect(state.max_tokens).toBeNull()
    expect(state.temperature).toBeNull()
    expect(state.npcEnabled).toBe(true)
    expect(state.summarizerEnabled).toBe(true)
    expect(state.connectionTested).toBe(false)
    expect(state.models).toEqual([])
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('updates dm settings', () => {
    useConnectionStore.getState().setSettings({
      dm_max_tokens: 32000,
      dm_temperature: 0.9,
      dm_timeout: 240,
    })
    const state = useConnectionStore.getState()
    expect(state.dm_max_tokens).toBe(32000)
    expect(state.dm_temperature).toBe(0.9)
    expect(state.dm_timeout).toBe(240)
  })

  it('updates npc settings via individual setters', () => {
    useConnectionStore.getState().setSettings({
      npc_max_tokens: 2048,
      npc_temperature: 0.5,
      npc_timeout: 120,
    })
    const state = useConnectionStore.getState()
    expect(state.npc_max_tokens).toBe(2048)
    expect(state.npc_temperature).toBe(0.5)
    expect(state.npc_timeout).toBe(120)
  })

  it('updates summarizer settings via setSettings', () => {
    useConnectionStore.getState().setSettings({
      summarizer_max_tokens: 8000,
      summarizer_temperature: 0.6,
      summarizer_timeout: 60,
    })
    const state = useConnectionStore.getState()
    expect(state.summarizer_max_tokens).toBe(8000)
    expect(state.summarizer_temperature).toBe(0.6)
    expect(state.summarizer_timeout).toBe(60)
  })

  it('updates provider-level settings', () => {
    const store = useConnectionStore.getState()
    store.setTimeout(600)
    store.setMaxTokens(4096)
    store.setTemperature(0.5)
    const state = useConnectionStore.getState()
    expect(state.timeout).toBe(600)
    expect(state.max_tokens).toBe(4096)
    expect(state.temperature).toBe(0.5)
  })

  it('sets max_tokens to null', () => {
    useConnectionStore.getState().setMaxTokens(4096)
    expect(useConnectionStore.getState().max_tokens).toBe(4096)
    useConnectionStore.getState().setMaxTokens(null)
    expect(useConnectionStore.getState().max_tokens).toBeNull()
  })

  it('toggles npcEnabled and summarizerEnabled', () => {
    useConnectionStore.getState().setNpcEnabled(false)
    expect(useConnectionStore.getState().npcEnabled).toBe(false)
    useConnectionStore.getState().setSummarizerEnabled(false)
    expect(useConnectionStore.getState().summarizerEnabled).toBe(false)
  })

  it('updates connectionTested', () => {
    useConnectionStore.getState().setConnectionTested(true)
    expect(useConnectionStore.getState().connectionTested).toBe(true)
  })

  it('updates models list', () => {
    const models = ['llama3.2', 'mistral', 'codellama']
    useConnectionStore.getState().setModels(models)
    expect(useConnectionStore.getState().models).toEqual(models)
  })

  it('updates loading and error', () => {
    useConnectionStore.getState().setLoading(true)
    expect(useConnectionStore.getState().loading).toBe(true)
    useConnectionStore.getState().setError('Something went wrong')
    expect(useConnectionStore.getState().error).toBe('Something went wrong')
  })

  it('setSettings bulk update merges partial state', () => {
    useConnectionStore.getState().setSettings({
      timeout: 500,
      npcEnabled: false,
      summarizerEnabled: false,
    })
    const state = useConnectionStore.getState()
    expect(state.timeout).toBe(500)
    expect(state.npcEnabled).toBe(false)
    expect(state.summarizerEnabled).toBe(false)
    // Unchanged fields keep defaults
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('setSettings with empty object does nothing', () => {
    useConnectionStore.getState().setSettings({})
    const state = useConnectionStore.getState()
    expect(state.timeout).toBe(300)
    expect(state.loading).toBe(false)
  })

  it('setSettings with a single field merges partial', () => {
    useConnectionStore.getState().setSettings({ dm_max_tokens: 999 })
    const state = useConnectionStore.getState()
    expect(state.dm_max_tokens).toBe(999)
    // Other agent fields unchanged
    expect(state.dm_temperature).toBe(0.8)
    expect(state.dm_timeout).toBe(120)
    // Other unrelated fields unchanged
    expect(state.timeout).toBe(300)
  })

  it('setSettings with null values merges correctly', () => {
    useConnectionStore.getState().setSettings({
      apiKey: 'some-key',
      max_tokens: 4096,
      temperature: 0.5,
    })
    useConnectionStore.getState().setSettings({
      apiKey: null,
      max_tokens: null,
      temperature: null,
    })
    const state = useConnectionStore.getState()
    expect(state.apiKey).toBeNull()
    expect(state.max_tokens).toBeNull()
    expect(state.temperature).toBeNull()
  })

  it('setSettings multiple sequential calls merge correctly', () => {
    const store = useConnectionStore.getState()
    store.setSettings({ timeout: 100 })
    store.setSettings({ timeout: 200, npcEnabled: false })
    store.setSettings({ summarizerEnabled: false })
    const state = useConnectionStore.getState()
    expect(state.timeout).toBe(200) // overwritten by second call
    expect(state.npcEnabled).toBe(false)
    expect(state.summarizerEnabled).toBe(false)
  })

  it('updates providerType', () => {
    useConnectionStore.getState().setProviderType('groq')
    expect(useConnectionStore.getState().providerType).toBe('groq')
  })

  it('updates apiKey to string and back to null', () => {
    useConnectionStore.getState().setApiKey('sk-test-key')
    expect(useConnectionStore.getState().apiKey).toBe('sk-test-key')
    useConnectionStore.getState().setApiKey(null)
    expect(useConnectionStore.getState().apiKey).toBeNull()
  })

  it('updates checking', () => {
    useConnectionStore.getState().setChecking(true)
    expect(useConnectionStore.getState().checking).toBe(true)
    useConnectionStore.getState().setChecking(false)
    expect(useConnectionStore.getState().checking).toBe(false)
  })

  it('sets temperature to null', () => {
    useConnectionStore.getState().setTemperature(0.5)
    expect(useConnectionStore.getState().temperature).toBe(0.5)
    useConnectionStore.getState().setTemperature(null)
    expect(useConnectionStore.getState().temperature).toBeNull()
  })

  it('sets error to null', () => {
    useConnectionStore.getState().setError('Something went wrong')
    expect(useConnectionStore.getState().error).toBe('Something went wrong')
    useConnectionStore.getState().setError(null)
    expect(useConnectionStore.getState().error).toBeNull()
  })

  it('setting models to empty list', () => {
    useConnectionStore.getState().setModels(['llama3', 'mistral'])
    useConnectionStore.getState().setModels([])
    expect(useConnectionStore.getState().models).toEqual([])
  })

  it('reset restores ALL fields to initial values', () => {
    const store = useConnectionStore.getState()

    // Mutate every mutable field
    store.setBaseUrl('http://other.com')
    store.setModel('other-model')
    store.setProviderType('groq')
    store.setApiKey('sk-key')
    store.setChecking(true)
    store.setHealthResult(true, 42, null)
    store.setSettings({
      timeout: 999,
      max_tokens: 2048,
      temperature: 0.5,
      dm_max_tokens: 1,
      dm_temperature: 0.1,
      dm_timeout: 1,
      npc_max_tokens: 1,
      npc_temperature: 0.1,
      npc_timeout: 1,
      summarizer_max_tokens: 1,
      summarizer_temperature: 0.1,
      summarizer_timeout: 1,
      npcEnabled: false,
      summarizerEnabled: false,
      connectionTested: true,
      models: ['codellama'],
      loading: true,
      error: 'oh no',
    })

    store.reset()

    const state = useConnectionStore.getState()

    // Connection config
    expect(state.baseUrl).toBe('http://localhost:11434')
    expect(state.model).toBe('llama3.2')
    expect(state.providerType).toBe('ollama')
    expect(state.apiKey).toBeNull()

    // Health / status
    expect(state.checking).toBe(false)
    expect(state.healthOk).toBeNull()
    expect(state.healthError).toBeNull()
    expect(state.latencyMs).toBeNull()

    // Agent-specific settings
    expect(state.dm_max_tokens).toBe(16000)
    expect(state.dm_temperature).toBe(0.8)
    expect(state.dm_timeout).toBe(120)
    expect(state.npc_max_tokens).toBe(1024)
    expect(state.npc_temperature).toBe(0.7)
    expect(state.npc_timeout).toBe(60)
    expect(state.summarizer_max_tokens).toBe(16000)
    expect(state.summarizer_temperature).toBe(0.7)
    expect(state.summarizer_timeout).toBe(120)

    // Provider-level settings
    expect(state.timeout).toBe(300)
    expect(state.max_tokens).toBeNull()
    expect(state.temperature).toBeNull()

    // Toggles
    expect(state.npcEnabled).toBe(true)
    expect(state.summarizerEnabled).toBe(true)

    // Status
    expect(state.connectionTested).toBe(false)
    expect(state.models).toEqual([])
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })
})

describe('characterStore', () => {
  beforeEach(() => {
    useCharacterStore.getState().reset()
  })

  it('has default values', () => {
    const state = useCharacterStore.getState()
    expect(state.currentCharacter).toBeNull()
    expect(state.savedCharacters).toEqual([])
    expect(state.savedGames).toEqual([])
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.rules).toBeNull()
    expect(state.rulesLoading).toBe(false)
    expect(state.rulesError).toBeNull()
    expect(state.abilities).toEqual({})
    expect(state.selectedClass).toBe('')
    expect(state.remainingPoints).toBe(27)
    expect(state.creationMode).toBe('campfire')
    expect(state.storyAnswers).toEqual([])
    expect(state.currentQuestion).toBe(0)
    expect(state.generatedCharacter).toBeNull()
    expect(state.isEditing).toBe(false)
    expect(state.manualName).toBe('')
    expect(state.manualAppearance).toBe('')
    expect(state.manualBackstory).toBe('')
  })

  it('sets current character', () => {
    const char = {
      name: 'Test Hero',
      character_class: 'Fighter',
      level: 1,
      abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
      hp: 12,
      max_hp: 12,
      ac: 18,
      skills: ['Athletics'],
      backstory: '',
      appearance: '',
      personality: '',
      hooks: [],
      inventory: ['Sword'],
      gold: 10,
      xp: 0,
      created_at: '2024-01-01',
    }
    useCharacterStore.getState().setCurrentCharacter(char)
    expect(useCharacterStore.getState().currentCharacter?.name).toBe('Test Hero')
  })

  it('manages saved characters list', () => {
    const items: CharacterListItem[] = [
      { id: '1', name: 'Hero 1', class: 'Rogue', level: 1, timestamp: '2024-01-01' },
      { id: '2', name: 'Hero 2', class: 'Fighter', level: 2, timestamp: '2024-01-02' },
    ]
    useCharacterStore.getState().setSavedCharacters(items)
    expect(useCharacterStore.getState().savedCharacters).toHaveLength(2)
    useCharacterStore.getState().setSavedCharacters([items[0]])
    expect(useCharacterStore.getState().savedCharacters).toHaveLength(1)
  })

  it('manages saved games list', () => {
    const saves = [
      { id: 'save-1', name: 'Adventure 1', timestamp: '2024-01-01', turn_count: 5 },
      { id: 'save-2', name: 'Adventure 2', timestamp: '2024-01-02', turn_count: 12 },
    ]
    useCharacterStore.getState().setSavedGames(saves)
    expect(useCharacterStore.getState().savedGames).toHaveLength(2)
    useCharacterStore.getState().setSavedGames([])
    expect(useCharacterStore.getState().savedGames).toHaveLength(0)
  })

  it('sets creation mode', () => {
    useCharacterStore.getState().setCreationMode('manual')
    expect(useCharacterStore.getState().creationMode).toBe('manual')
    useCharacterStore.getState().setCreationMode('review')
    expect(useCharacterStore.getState().creationMode).toBe('review')
    useCharacterStore.getState().setCreationMode('campfire')
    expect(useCharacterStore.getState().creationMode).toBe('campfire')
  })

  it('updates campaign story state', () => {
    useCharacterStore.getState().setStoryAnswers(['a', 'b', 'c', 'd', 'e', 'f', 'g'])
    expect(useCharacterStore.getState().storyAnswers).toHaveLength(7)
    useCharacterStore.getState().setCurrentQuestion(3)
    expect(useCharacterStore.getState().currentQuestion).toBe(3)
  })

  it('saves current answer and navigates questions', () => {
    useCharacterStore.getState().setStoryAnswers(['', '', ''])
    useCharacterStore.getState().saveCurrentAnswer('my answer')
    expect(useCharacterStore.getState().storyAnswers[0]).toBe('my answer')

    useCharacterStore.getState().nextQuestion()
    expect(useCharacterStore.getState().currentQuestion).toBe(1)

    useCharacterStore.getState().prevQuestion()
    expect(useCharacterStore.getState().currentQuestion).toBe(0)
  })

  it('does not go below 0 or above max questions', () => {
    useCharacterStore.getState().setStoryAnswers(['a', 'b'])
    useCharacterStore.getState().setCurrentQuestion(0)
    useCharacterStore.getState().prevQuestion()
    expect(useCharacterStore.getState().currentQuestion).toBe(0)

    useCharacterStore.getState().setCurrentQuestion(1)
    useCharacterStore.getState().nextQuestion()
    expect(useCharacterStore.getState().currentQuestion).toBe(1)
  })

  it('jumps to specific question via goToQuestion', () => {
    useCharacterStore.getState().setStoryAnswers(['a', 'b', 'c'])
    useCharacterStore.getState().goToQuestion(2)
    expect(useCharacterStore.getState().currentQuestion).toBe(2)
  })

  it('sets generated character and edit mode', () => {
    expect(useCharacterStore.getState().isEditing).toBe(false)
    useCharacterStore.getState().setIsEditing(true)
    expect(useCharacterStore.getState().isEditing).toBe(true)
    useCharacterStore.getState().setIsEditing(false)
    expect(useCharacterStore.getState().isEditing).toBe(false)
  })

  it('sets manual form fields', () => {
    useCharacterStore.getState().setManualName('Hero')
    useCharacterStore.getState().setManualAppearance('Tall')
    useCharacterStore.getState().setManualBackstory('A tale')
    expect(useCharacterStore.getState().manualName).toBe('Hero')
    expect(useCharacterStore.getState().manualAppearance).toBe('Tall')
    expect(useCharacterStore.getState().manualBackstory).toBe('A tale')
  })

  it('sets rules state fields', () => {
    useCharacterStore.getState().setRulesLoading(true)
    expect(useCharacterStore.getState().rulesLoading).toBe(true)
    useCharacterStore.getState().setRulesError('Network error')
    expect(useCharacterStore.getState().rulesError).toBe('Network error')
    useCharacterStore.getState().setRulesLoading(false)
    useCharacterStore.getState().setRulesError(null)
    expect(useCharacterStore.getState().rulesLoading).toBe(false)
    expect(useCharacterStore.getState().rulesError).toBeNull()
  })

  it('setState bulk update merges partial state', () => {
    useCharacterStore.getState().setState({
      loading: true,
      creationMode: 'manual',
      manualName: 'Bulk Hero',
    })
    const state = useCharacterStore.getState()
    expect(state.loading).toBe(true)
    expect(state.creationMode).toBe('manual')
    expect(state.manualName).toBe('Bulk Hero')
    // Unchanged fields keep defaults
    expect(state.error).toBeNull()
    expect(state.remainingPoints).toBe(27)
  })

  it('resets to initial state', () => {
    useCharacterStore.getState().setLoading(true)
    useCharacterStore.getState().setError('Something went wrong')
    useCharacterStore.getState().setCreationMode('review')
    useCharacterStore.getState().setManualName('Temp')
    useCharacterStore.getState().reset()
    const state = useCharacterStore.getState()
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.creationMode).toBe('campfire')
    expect(state.manualName).toBe('')
  })

  it('point-buy canIncrease/canDecrease guards missing abilities', () => {
    const state = useCharacterStore.getState()
    // Without rules and empty abilities, guards return false
    expect(state.canIncrease('STR')).toBe(false)
    expect(state.canDecrease('STR')).toBe(false)
  })

  it('point-buy increase and decrease work with default cost table', () => {
    useCharacterStore.getState().setAbilities({ STR: 10 })
    useCharacterStore.getState().increaseAbility('STR')
    // Without rules but score=10 is under maxScore default (15) and
    // pointCost is 0 (costs table empty), so increase works
    expect(useCharacterStore.getState().abilities['STR']).toBe(11)
    expect(useCharacterStore.getState().remainingPoints).toBe(27)

    useCharacterStore.getState().decreaseAbility('STR')
    // Decrease works because score=11 > minScore default (8)
    expect(useCharacterStore.getState().abilities['STR']).toBe(10)
    expect(useCharacterStore.getState().remainingPoints).toBe(27)
  })

  it('point-buy cannot increase at max score', () => {
    useCharacterStore.getState().setRemainingPoints(99)
    useCharacterStore.getState().setAbilities({ STR: 15 })
    // With default maxScore=15, STR=15 cannot increase further
    expect(useCharacterStore.getState().canIncrease('STR')).toBe(false)
  })

  it('point-buy cannot decrease at min score', () => {
    useCharacterStore.getState().setAbilities({ STR: 8 })
    // With default minScore=8, STR=8 cannot decrease further
    expect(useCharacterStore.getState().canDecrease('STR')).toBe(false)
  })

  // ------------------------------------------------------------------
  // Point-buy with real cost table
  // ------------------------------------------------------------------

  describe('point-buy with real costs', () => {
    const mockRules = {
      valid_classes: ['Fighter', 'Rogue', 'Mage', 'Cleric'],
      standard_abilities: ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
      class_templates: {},
      point_buy: {
        costs: {
          '8': 0,
          '9': 1,
          '10': 2,
          '11': 3,
          '12': 4,
          '13': 5,
          '14': 7,
          '15': 9,
        },
        max_points: 27,
        min_score: 8,
        max_score: 15,
      },
      assisted_creation_questions: ['Q1?', 'Q2?', 'Q3?'],
    }

    beforeEach(() => {
      useCharacterStore.getState().reset()
      useCharacterStore.getState().setRules(mockRules as any)
      useCharacterStore.getState().setAbilities({ STR: 8 })
      useCharacterStore.getState().setRemainingPoints(27)
    })

    it('getCost returns correct cost from real cost table', () => {
      expect(useCharacterStore.getState().getCost(8)).toBe(0)
      expect(useCharacterStore.getState().getCost(13)).toBe(5)
      expect(useCharacterStore.getState().getCost(15)).toBe(9)
    })

    it('getCost returns 0 for score not in cost table', () => {
      expect(useCharacterStore.getState().getCost(3)).toBe(0)
      expect(useCharacterStore.getState().getCost(20)).toBe(0)
    })

    it('increaseAbility deducts correct point cost', () => {
      // 8 -> 9 costs 1 point
      useCharacterStore.getState().increaseAbility('STR')
      expect(useCharacterStore.getState().abilities['STR']).toBe(9)
      expect(useCharacterStore.getState().remainingPoints).toBe(26)

      // 9 -> 10 costs 1 point (cost goes from 1 to 2)
      useCharacterStore.getState().increaseAbility('STR')
      expect(useCharacterStore.getState().abilities['STR']).toBe(10)
      expect(useCharacterStore.getState().remainingPoints).toBe(25)
    })

    it('decreaseAbility refunds correct point cost', () => {
      useCharacterStore.getState().setAbilities({ STR: 15 })
      useCharacterStore.getState().setRemainingPoints(9)

      // 15 -> 14 refunds 2 points (cost drops from 9 to 7)
      useCharacterStore.getState().decreaseAbility('STR')
      expect(useCharacterStore.getState().abilities['STR']).toBe(14)
      expect(useCharacterStore.getState().remainingPoints).toBe(11)

      // 14 -> 13 refunds 2 points (cost drops from 7 to 5)
      useCharacterStore.getState().decreaseAbility('STR')
      expect(useCharacterStore.getState().abilities['STR']).toBe(13)
      expect(useCharacterStore.getState().remainingPoints).toBe(13)
    })

    it('canIncrease returns false when insufficient remaining points', () => {
      useCharacterStore.getState().setAbilities({ STR: 14 })
      // 14 -> 15 costs 2 points (9 - 7 = 2)
      useCharacterStore.getState().setRemainingPoints(1)
      expect(useCharacterStore.getState().canIncrease('STR')).toBe(false)

      // Exactly enough points should work
      useCharacterStore.getState().setRemainingPoints(2)
      expect(useCharacterStore.getState().canIncrease('STR')).toBe(true)
    })

    it('increaseAbility does nothing when canIncrease is false', () => {
      // Already at max score (15), cannot increase
      useCharacterStore.getState().setAbilities({ STR: 15 })
      useCharacterStore.getState().setRemainingPoints(99)

      useCharacterStore.getState().increaseAbility('STR')
      expect(useCharacterStore.getState().abilities['STR']).toBe(15)
      expect(useCharacterStore.getState().remainingPoints).toBe(99)
    })

    it('decreaseAbility does nothing when canDecrease is false', () => {
      // Already at min score (8), cannot decrease
      useCharacterStore.getState().setAbilities({ STR: 8 })
      useCharacterStore.getState().increaseAbility('STR') // go to 9, cost 1
      expect(useCharacterStore.getState().abilities['STR']).toBe(9)

      // Decrease back to 8
      useCharacterStore.getState().decreaseAbility('STR')
      expect(useCharacterStore.getState().abilities['STR']).toBe(8)
      // 8 is min, so cannot decrease further
      useCharacterStore.getState().decreaseAbility('STR')
      expect(useCharacterStore.getState().abilities['STR']).toBe(8)
    })
  })

  // ------------------------------------------------------------------
  // initDefaults
  // ------------------------------------------------------------------

  describe('initDefaults', () => {
    it('sets base scores to 8, picks first class, and calculates remaining points', () => {
      const mockRules = {
        valid_classes: ['Cleric', 'Fighter', 'Mage', 'Rogue'],
        standard_abilities: ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
        class_templates: {
          Cleric: {
            abilities: { STR: 13, DEX: 8, CON: 14, INT: 10, WIS: 15, CHA: 12 },
          },
        },
        point_buy: {
          costs: {
            '8': 0,
            '9': 1,
            '10': 2,
            '11': 3,
            '12': 4,
            '13': 5,
            '14': 7,
            '15': 9,
          },
          max_points: 27,
          min_score: 8,
          max_score: 15,
        },
        assisted_creation_questions: ['Q1?', 'Q2?', 'Q3?'],
      }

      useCharacterStore.getState().setRules(mockRules as any)
      useCharacterStore.getState().initDefaults()

      const state = useCharacterStore.getState()
      // Cleric template: STR=13(5), DEX=8(0), CON=14(7), INT=10(2), WIS=15(9), CHA=12(4)
      // Total cost: 5+0+7+2+9+4 = 27, remaining = 0
      expect(state.abilities).toEqual({
        STR: 13,
        DEX: 8,
        CON: 14,
        INT: 10,
        WIS: 15,
        CHA: 12,
      })
      expect(state.selectedClass).toBe('Cleric')
      expect(state.remainingPoints).toBe(0)
      expect(state.storyAnswers).toEqual(['', '', ''])
      expect(state.currentQuestion).toBe(0)
      expect(state.creationMode).toBe('campfire')
      expect(state.generatedCharacter).toBeNull()
      expect(state.isEditing).toBe(false)
      expect(state.manualName).toBe('')
      expect(state.manualAppearance).toBe('')
      expect(state.manualBackstory).toBe('')
    })

    it('picks first valid class even without class_templates entry', () => {
      const mockRules = {
        valid_classes: ['Fighter'],
        standard_abilities: ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
        class_templates: {
          Cleric: {
            abilities: { STR: 13, DEX: 8, CON: 14, INT: 10, WIS: 15, CHA: 12 },
          },
        },
        point_buy: {
          costs: { '8': 0 },
          max_points: 27,
          min_score: 8,
          max_score: 15,
        },
        assisted_creation_questions: ['Q1?'],
      }

      useCharacterStore.getState().setRules(mockRules as any)
      useCharacterStore.getState().initDefaults()

      const state = useCharacterStore.getState()
      // Fighter class has no template, so all base scores are 8
      expect(state.selectedClass).toBe('Fighter')
      expect(state.abilities).toEqual({
        STR: 8,
        DEX: 8,
        CON: 8,
        INT: 8,
        WIS: 8,
        CHA: 8,
      })
      expect(state.remainingPoints).toBe(27)
      expect(state.storyAnswers).toEqual([''])
    })

    it('does nothing when rules are null', () => {
      // rules should already be null from reset
      useCharacterStore.getState().initDefaults()
      const state = useCharacterStore.getState()
      expect(state.abilities).toEqual({})
      expect(state.selectedClass).toBe('')
      expect(state.remainingPoints).toBe(27)
      expect(state.storyAnswers).toEqual([])
    })
  })

  // ------------------------------------------------------------------
  // applyClassDefaults
  // ------------------------------------------------------------------

  describe('applyClassDefaults', () => {
    const mockRules = {
      valid_classes: ['Fighter', 'Rogue', 'Mage', 'Cleric'],
      standard_abilities: ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
      class_templates: {
        Rogue: {
          abilities: { STR: 8, DEX: 15, CON: 13, INT: 14, WIS: 12, CHA: 10 },
        },
      },
      point_buy: {
        costs: {
          '8': 0,
          '9': 1,
          '10': 2,
          '11': 3,
          '12': 4,
          '13': 5,
          '14': 7,
          '15': 9,
        },
        max_points: 27,
        min_score: 8,
        max_score: 15,
      },
      assisted_creation_questions: [],
    }

    beforeEach(() => {
      useCharacterStore.getState().reset()
      useCharacterStore.getState().setRules(mockRules as any)
    })

    it('applies selected class template and recalculates remaining points', () => {
      useCharacterStore.getState().setSelectedClass('Rogue')
      useCharacterStore.getState().applyClassDefaults()

      const state = useCharacterStore.getState()
      // Rogue: STR=8(0), DEX=15(9), CON=13(5), INT=14(7), WIS=12(4), CHA=10(2)
      // Total: 0+9+5+7+4+2 = 27, remaining = 0
      expect(state.abilities).toEqual({
        STR: 8,
        DEX: 15,
        CON: 13,
        INT: 14,
        WIS: 12,
        CHA: 10,
      })
      expect(state.remainingPoints).toBe(0)
    })

    it('does nothing when rules are null', () => {
      useCharacterStore.getState().setRules(null as any)
      useCharacterStore.getState().setSelectedClass('Rogue')
      useCharacterStore.getState().applyClassDefaults()

      const state = useCharacterStore.getState()
      expect(state.abilities).toEqual({})
      expect(state.remainingPoints).toBe(27)
    })

    it('does nothing when selectedClass is empty string', () => {
      useCharacterStore.getState().setSelectedClass('')
      useCharacterStore.getState().applyClassDefaults()

      const state = useCharacterStore.getState()
      expect(state.abilities).toEqual({})
      expect(state.remainingPoints).toBe(27)
    })

    it('does nothing when selectedClass has no template', () => {
      useCharacterStore.getState().setSelectedClass('Mage')
      useCharacterStore.getState().applyClassDefaults()

      const state = useCharacterStore.getState()
      expect(state.abilities).toEqual({})
      expect(state.remainingPoints).toBe(27)
    })
  })

  // ------------------------------------------------------------------
  // Campfire navigation edge cases
  // ------------------------------------------------------------------

  describe('campfire navigation edge cases', () => {
    beforeEach(() => {
      useCharacterStore.getState().reset()
    })

    it('saveCurrentAnswer overwrites existing answer at current index', () => {
      useCharacterStore.getState().setStoryAnswers(['first', '', 'third'])
      useCharacterStore.getState().setCurrentQuestion(0)
      useCharacterStore.getState().saveCurrentAnswer('overwritten')
      expect(useCharacterStore.getState().storyAnswers[0]).toBe('overwritten')
      expect(useCharacterStore.getState().storyAnswers[1]).toBe('')
      expect(useCharacterStore.getState().storyAnswers[2]).toBe('third')
    })

    it('saveCurrentAnswer saves to different index positions', () => {
      useCharacterStore.getState().setStoryAnswers(['', '', ''])
      useCharacterStore.getState().setCurrentQuestion(1)
      useCharacterStore.getState().saveCurrentAnswer('middle answer')
      expect(useCharacterStore.getState().storyAnswers[0]).toBe('')
      expect(useCharacterStore.getState().storyAnswers[1]).toBe('middle answer')
      expect(useCharacterStore.getState().storyAnswers[2]).toBe('')
    })

    it('nextQuestion does not advance past the last question', () => {
      useCharacterStore.getState().setStoryAnswers(['a', 'b'])
      useCharacterStore.getState().setCurrentQuestion(1)
      useCharacterStore.getState().nextQuestion()
      expect(useCharacterStore.getState().currentQuestion).toBe(1)
    })

    it('prevQuestion does not go below question 0', () => {
      useCharacterStore.getState().setStoryAnswers(['a', 'b'])
      useCharacterStore.getState().setCurrentQuestion(0)
      useCharacterStore.getState().prevQuestion()
      expect(useCharacterStore.getState().currentQuestion).toBe(0)
    })

    it('goToQuestion sets currentQuestion to any index', () => {
      useCharacterStore.getState().setStoryAnswers(['a', 'b', 'c', 'd'])
      useCharacterStore.getState().goToQuestion(3)
      expect(useCharacterStore.getState().currentQuestion).toBe(3)
    })

    it('goToQuestion can set question beyond bounds', () => {
      useCharacterStore.getState().setStoryAnswers(['a', 'b'])
      // goToQuestion doesn't bound-check — it sets whatever index you pass
      useCharacterStore.getState().goToQuestion(999)
      expect(useCharacterStore.getState().currentQuestion).toBe(999)
    })
  })

  // ------------------------------------------------------------------
  // Additional setter coverage
  // ------------------------------------------------------------------

  it('sets selected class', () => {
    useCharacterStore.getState().setSelectedClass('Mage')
    expect(useCharacterStore.getState().selectedClass).toBe('Mage')
  })

  it('sets remaining points explicitly', () => {
    useCharacterStore.getState().setRemainingPoints(15)
    expect(useCharacterStore.getState().remainingPoints).toBe(15)
  })

  it('sets generated character to null and back', () => {
    expect(useCharacterStore.getState().generatedCharacter).toBeNull()
    const char = {
      name: 'Generated Hero',
      character_class: 'Mage',
      level: 1,
      abilities: { STR: 8, DEX: 14, CON: 13, INT: 15, WIS: 12, CHA: 10 },
      hp: 8,
      max_hp: 8,
      ac: 12,
      skills: ['Arcana'],
      backstory: '',
      appearance: '',
      personality: '',
      hooks: [],
      inventory: ['Spellbook'],
      gold: 20,
      xp: 0,
      created_at: '2024-01-01',
    }
    useCharacterStore.getState().setGeneratedCharacter(char)
    expect(useCharacterStore.getState().generatedCharacter?.name).toBe('Generated Hero')
    useCharacterStore.getState().setGeneratedCharacter(null)
    expect(useCharacterStore.getState().generatedCharacter).toBeNull()
  })

  it('setStoryAnswers replaces entire array', () => {
    useCharacterStore.getState().setStoryAnswers(['x', 'y', 'z'])
    expect(useCharacterStore.getState().storyAnswers).toEqual(['x', 'y', 'z'])
    useCharacterStore.getState().setStoryAnswers([])
    expect(useCharacterStore.getState().storyAnswers).toEqual([])
  })

  // ------------------------------------------------------------------
  // Comprehensive reset
  // ------------------------------------------------------------------

  it('reset restores ALL fields to initial values', () => {
    const state = useCharacterStore.getState()

    // Mutate every mutable field
    state.setCurrentCharacter({
      name: 'Mutated',
      character_class: 'Rogue',
      level: 5,
      abilities: { STR: 14, DEX: 16, CON: 15, INT: 10, WIS: 8, CHA: 12 },
      hp: 30,
      max_hp: 30,
      ac: 15,
      skills: ['Stealth'],
      backstory: 'test',
      appearance: 'test',
      personality: '',
      hooks: [],
      inventory: ['Dagger'],
      gold: 50,
      xp: 100,
      created_at: '2024-06-01',
    })
    state.setSavedCharacters([
      { id: 'c1', name: 'C1', class: 'Fighter', level: 1, timestamp: 't1' },
    ])
    state.setSavedGames([{ id: 's1', name: 'S1', timestamp: 't1' }])
    state.setLoading(true)
    state.setError('some error')
    state.setRules({
      valid_classes: [],
      standard_abilities: [],
      class_templates: {},
      point_buy: { costs: {}, max_points: 27, min_score: 8, max_score: 15 },
      assisted_creation_questions: [],
    })
    state.setRulesLoading(true)
    state.setRulesError('rules error')
    state.setAbilities({ STR: 15 })
    state.setSelectedClass('Mage')
    state.setRemainingPoints(10)
    state.setCreationMode('manual')
    state.setStoryAnswers(['answer'])
    state.setCurrentQuestion(2)
    state.setGeneratedCharacter({
      name: 'Gen',
      character_class: 'Fighter',
      level: 1,
      abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
      hp: 12,
      max_hp: 12,
      ac: 18,
      skills: [],
      backstory: '',
      appearance: '',
      personality: '',
      hooks: [],
      inventory: [],
      gold: 0,
      xp: 0,
      created_at: '2024-01-01',
    })
    state.setIsEditing(true)
    state.setManualName('Manual')
    state.setManualAppearance('Tall')
    state.setManualBackstory('Story')

    state.reset()

    const s = useCharacterStore.getState()
    expect(s.currentCharacter).toBeNull()
    expect(s.savedCharacters).toEqual([])
    expect(s.savedGames).toEqual([])
    expect(s.loading).toBe(false)
    expect(s.error).toBeNull()
    expect(s.rules).toBeNull()
    expect(s.rulesLoading).toBe(false)
    expect(s.rulesError).toBeNull()
    expect(s.abilities).toEqual({})
    expect(s.selectedClass).toBe('')
    expect(s.remainingPoints).toBe(27)
    expect(s.creationMode).toBe('campfire')
    expect(s.storyAnswers).toEqual([])
    expect(s.currentQuestion).toBe(0)
    expect(s.generatedCharacter).toBeNull()
    expect(s.isEditing).toBe(false)
    expect(s.manualName).toBe('')
    expect(s.manualAppearance).toBe('')
    expect(s.manualBackstory).toBe('')
  })

  // ------------------------------------------------------------------
  // Async API methods
  // ------------------------------------------------------------------

  describe('fetchCharacters', () => {
    beforeEach(() => {
      vi.clearAllMocks()
      useCharacterStore.getState().reset()
    })

    it('fetches and sets saved characters list', async () => {
      const mockList: CharacterListItem[] = [
        {
          id: 'c1',
          name: 'Alice',
          class: 'Fighter',
          level: 3,
          timestamp: '2024-01-01',
        },
        { id: 'c2', name: 'Bob', class: 'Mage', level: 2, timestamp: '2024-01-02' },
      ]
      vi.mocked(listCharacters).mockResolvedValue({
        ok: true,
        characters: mockList,
      } as any)

      await useCharacterStore.getState().fetchCharacters()

      expect(useCharacterStore.getState().savedCharacters).toEqual(mockList)
    })

    it('does not update savedCharacters when API returns ok:false', async () => {
      vi.mocked(listCharacters).mockResolvedValue({
        ok: false,
        characters: [],
      } as any)

      await useCharacterStore.getState().fetchCharacters()

      expect(useCharacterStore.getState().savedCharacters).toEqual([])
    })

    it('does not update savedCharacters on network error', async () => {
      vi.mocked(listCharacters).mockRejectedValue(new Error('Network error'))

      await useCharacterStore.getState().fetchCharacters()

      // Background fetch fails silently — savedCharacters stays empty
      expect(useCharacterStore.getState().savedCharacters).toEqual([])
    })
  })

  describe('loadCharacterById', () => {
    beforeEach(() => {
      vi.clearAllMocks()
      useCharacterStore.getState().reset()
    })

    it('loads and sets currentCharacter on success', async () => {
      const mockCharacter = {
        name: 'Loaded Hero',
        character_class: 'Fighter',
        level: 1,
        abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
        hp: 12,
        max_hp: 12,
        ac: 18,
        skills: ['Athletics'],
        backstory: '',
        appearance: '',
        personality: '',
        hooks: [],
        inventory: ['Sword'],
        gold: 10,
        xp: 0,
        created_at: '2024-01-01',
      }
      vi.mocked(loadCharacterById).mockResolvedValue({
        ok: true,
        character: mockCharacter,
      } as any)

      await useCharacterStore.getState().loadCharacterById('test-id')

      expect(useCharacterStore.getState().currentCharacter).toEqual(mockCharacter)
      expect(useCharacterStore.getState().loading).toBe(false)
      expect(useCharacterStore.getState().error).toBeNull()
    })

    it('sets error when API returns ok:false', async () => {
      vi.mocked(loadCharacterById).mockResolvedValue({
        ok: false,
      } as any)

      await useCharacterStore.getState().loadCharacterById('bad-id')

      expect(useCharacterStore.getState().currentCharacter).toBeNull()
      expect(useCharacterStore.getState().error).toBe('Failed to load character')
      expect(useCharacterStore.getState().loading).toBe(false)
    })

    it('sets error message on network failure', async () => {
      vi.mocked(loadCharacterById).mockRejectedValue(new Error('Network failure'))

      await useCharacterStore.getState().loadCharacterById('fail-id')

      expect(useCharacterStore.getState().currentCharacter).toBeNull()
      expect(useCharacterStore.getState().error).toBe('Network failure')
      expect(useCharacterStore.getState().loading).toBe(false)
    })

    it('handles non-Error thrown values gracefully', async () => {
      vi.mocked(loadCharacterById).mockRejectedValue('raw string')

      await useCharacterStore.getState().loadCharacterById('fail-id')

      expect(useCharacterStore.getState().error).toBe('Failed to load character')
      expect(useCharacterStore.getState().loading).toBe(false)
    })
  })
})

describe('gameStore', () => {
  beforeEach(() => {
    useGameStore.getState().reset()
  })

  it('has default values', () => {
    const state = useGameStore.getState()
    expect(state.narrative).toBe('')
    expect(state.worldState).toBeNull()
    expect(state.processing).toBe(false)
    expect(state.isActive).toBe(false)
    expect(state.error).toBeNull()
  })

  it('appends narrative text', () => {
    useGameStore.getState().appendNarrative('Hello, ')
    useGameStore.getState().appendNarrative('world!')
    expect(useGameStore.getState().narrative).toBe('Hello, world!')
  })

  it('sets processing state', () => {
    useGameStore.getState().setProcessing(true)
    expect(useGameStore.getState().processing).toBe(true)
  })

  it('sets world state', () => {
    const ws = { location: 'Tavern', hp: 20 }
    useGameStore.getState().setWorldState(ws)
    expect(useGameStore.getState().worldState).toEqual(ws)
  })

  it('resets to initial state', () => {
    useGameStore.getState().setNarrative('Some story')
    useGameStore.getState().setIsActive(true)
    useGameStore.getState().reset()
    const state = useGameStore.getState()
    expect(state.narrative).toBe('')
    expect(state.isActive).toBe(false)
  })
})
