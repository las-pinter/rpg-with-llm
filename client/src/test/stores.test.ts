import { describe, it, expect, beforeEach } from 'vitest'
import { useConnectionStore } from '../stores/connectionStore'
import { useCharacterStore } from '../stores/characterStore'
import { useGameStore } from '../stores/gameStore'

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
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('sets current character', () => {
    const char = {
      name: 'Test Hero',
      character_class: 'Fighter',
      level: 1,
      race: 'Human',
      abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
      hp: 12,
      max_hp: 12,
      ac: 18,
      skills: ['Athletics'],
      backstory: '',
      appearance: '',
      personality: '',
      ideals: '',
      bonds: '',
      flaws: '',
      inventory: ['Sword'],
      gold: 10,
      xp: 0,
      created_at: '2024-01-01',
    }
    useCharacterStore.getState().setCurrentCharacter(char)
    expect(useCharacterStore.getState().currentCharacter?.name).toBe('Test Hero')
  })

  it('manages saved characters list', () => {
    const char1 = {
      name: 'Hero 1',
      character_class: 'Rogue',
      level: 1,
      race: 'Elf',
      abilities: { STR: 8, DEX: 15, CON: 13, INT: 14, WIS: 12, CHA: 10 },
      hp: 9,
      max_hp: 9,
      ac: 14,
      skills: ['Stealth'],
      backstory: '',
      appearance: '',
      personality: '',
      ideals: '',
      bonds: '',
      flaws: '',
      inventory: ['Dagger'],
      gold: 15,
      xp: 0,
      created_at: '2024-01-01',
    }
    useCharacterStore.getState().addSavedCharacter(char1)
    expect(useCharacterStore.getState().savedCharacters).toHaveLength(1)
    useCharacterStore.getState().removeSavedCharacter('Hero 1')
    expect(useCharacterStore.getState().savedCharacters).toHaveLength(0)
  })

  it('resets to initial state', () => {
    useCharacterStore.getState().setLoading(true)
    useCharacterStore.getState().setError('Something went wrong')
    useCharacterStore.getState().reset()
    const state = useCharacterStore.getState()
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
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
