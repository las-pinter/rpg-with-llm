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
