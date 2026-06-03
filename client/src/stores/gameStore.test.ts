import { describe, it, expect, beforeEach } from 'vitest'
import { useGameStore } from './gameStore'
import type { NarrativeEntry } from './gameStore'

/** Reset store to pristine defaults before each test. */
function resetStore(): void {
  useGameStore.setState({
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
  })
}

// ---------------------------------------------------------------------------
// Default values
// ---------------------------------------------------------------------------

describe('gameStore', () => {
  beforeEach(resetStore)

  describe('initial defaults', () => {
    it('has all fields at initial default values', () => {
      const s = useGameStore.getState()
      expect(s.narrative).toBe('')
      expect(s.worldState).toBeNull()
      expect(s.playerInput).toBe('')
      expect(s.processing).toBe(false)
      expect(s.isActive).toBe(false)
      expect(s.error).toBeNull()
      expect(s.narrativeEntries).toEqual([])
      expect(s.streamingText).toBe('')
      expect(s.isThinking).toBe(false)
      expect(s.npcThinking).toBeNull()
      expect(s.turnCount).toBe(0)
      expect(s.tokenUsage).toEqual({ accumulated: 0, latest: 0 })
      expect(s.autoScroll).toBe(true)
      expect(s.showTokens).toBe(false)
    })
  })

  // -----------------------------------------------------------------------
  // Legacy actions
  // -----------------------------------------------------------------------

  describe('appendNarrative', () => {
    it('appends text to an empty narrative', () => {
      useGameStore.getState().appendNarrative('Hello, world!')
      expect(useGameStore.getState().narrative).toBe('Hello, world!')
    })

    it('appends text to existing narrative', () => {
      useGameStore.setState({ narrative: 'Start. ' })
      useGameStore.getState().appendNarrative('Middle. ')
      useGameStore.getState().appendNarrative('End.')
      expect(useGameStore.getState().narrative).toBe('Start. Middle. End.')
    })

    it('appending an empty string does not change narrative', () => {
      useGameStore.setState({ narrative: 'Some text' })
      useGameStore.getState().appendNarrative('')
      expect(useGameStore.getState().narrative).toBe('Some text')
    })
  })

  describe('setNarrative', () => {
    it('sets narrative to a given string', () => {
      useGameStore.getState().setNarrative('The adventure begins...')
      expect(useGameStore.getState().narrative).toBe('The adventure begins...')
    })

    it('sets narrative to an empty string', () => {
      useGameStore.setState({ narrative: 'Old story' })
      useGameStore.getState().setNarrative('')
      expect(useGameStore.getState().narrative).toBe('')
    })
  })

  describe('setWorldState', () => {
    it('sets worldState to an object', () => {
      const ws = { location: 'Dungeon', hp: 30, gold: 100 }
      useGameStore.getState().setWorldState(ws)
      expect(useGameStore.getState().worldState).toEqual(ws)
    })

    it('sets worldState to null', () => {
      useGameStore.setState({ worldState: { location: 'Tavern' } })
      useGameStore.getState().setWorldState(null)
      expect(useGameStore.getState().worldState).toBeNull()
    })

    it('sets worldState to an empty object', () => {
      useGameStore.getState().setWorldState({})
      expect(useGameStore.getState().worldState).toEqual({})
    })
  })

  describe('setPlayerInput', () => {
    it('sets playerInput to a given string', () => {
      useGameStore.getState().setPlayerInput('I attack the goblin!')
      expect(useGameStore.getState().playerInput).toBe('I attack the goblin!')
    })

    it('sets playerInput to an empty string', () => {
      useGameStore.setState({ playerInput: 'Old input' })
      useGameStore.getState().setPlayerInput('')
      expect(useGameStore.getState().playerInput).toBe('')
    })

    it('overwrites previous playerInput', () => {
      useGameStore.getState().setPlayerInput('first')
      useGameStore.getState().setPlayerInput('second')
      expect(useGameStore.getState().playerInput).toBe('second')
    })
  })

  describe('setProcessing', () => {
    it('sets processing to true', () => {
      useGameStore.getState().setProcessing(true)
      expect(useGameStore.getState().processing).toBe(true)
    })

    it('sets processing to false', () => {
      useGameStore.setState({ processing: true })
      useGameStore.getState().setProcessing(false)
      expect(useGameStore.getState().processing).toBe(false)
    })

    it('toggles processing back and forth', () => {
      useGameStore.getState().setProcessing(true)
      expect(useGameStore.getState().processing).toBe(true)
      useGameStore.getState().setProcessing(false)
      expect(useGameStore.getState().processing).toBe(false)
    })
  })

  describe('setIsActive', () => {
    it('sets isActive to true', () => {
      useGameStore.getState().setIsActive(true)
      expect(useGameStore.getState().isActive).toBe(true)
    })

    it('sets isActive to false', () => {
      useGameStore.setState({ isActive: true })
      useGameStore.getState().setIsActive(false)
      expect(useGameStore.getState().isActive).toBe(false)
    })
  })

  describe('setError', () => {
    it('sets an error message', () => {
      useGameStore.getState().setError('Something went wrong')
      expect(useGameStore.getState().error).toBe('Something went wrong')
    })

    it('clears error with null', () => {
      useGameStore.setState({ error: 'Old error' })
      useGameStore.getState().setError(null)
      expect(useGameStore.getState().error).toBeNull()
    })

    it('set then clear then set again', () => {
      useGameStore.getState().setError('First error')
      expect(useGameStore.getState().error).toBe('First error')
      useGameStore.getState().setError(null)
      expect(useGameStore.getState().error).toBeNull()
      useGameStore.getState().setError('Second error')
      expect(useGameStore.getState().error).toBe('Second error')
    })
  })

  describe('reset', () => {
    it('restores all initialState fields to their defaults', () => {
      const store = useGameStore.getState()

      // Mutate every field covered by initialState
      store.setNarrative('Story')
      store.setWorldState({ turn: 5 })
      store.setPlayerInput('hello')
      store.setProcessing(true)
      store.setIsActive(true)
      store.setError('boom')
      store.setStreamingText('stream')
      store.setIsThinking(true)
      store.setNpcThinking('goblin', 'sneak')
      store.incrementTurnCount()
      store.toggleAutoScroll()
      store.setShowTokens(true)

      store.reset()

      const s = useGameStore.getState()
      expect(s.narrative).toBe('')
      expect(s.worldState).toBeNull()
      expect(s.playerInput).toBe('')
      expect(s.processing).toBe(false)
      expect(s.isActive).toBe(false)
      expect(s.error).toBeNull()
      expect(s.streamingText).toBe('')
      expect(s.isThinking).toBe(false)
      expect(s.npcThinking).toBeNull()
      expect(s.turnCount).toBe(0)
      expect(s.autoScroll).toBe(true)
      expect(s.showTokens).toBe(false)
    })

    it('resets ALL fields including narrativeEntries and tokenUsage', () => {
      const store = useGameStore.getState()
      store.addNarrativeEntry({ type: 'narrative', content: 'Persistent entry' })
      store.setTokenUsage({ accumulated: 50, latest: 10 })

      store.reset()

      const s = useGameStore.getState()
      // initialState now includes ALL fields, so reset clears everything
      expect(s.narrativeEntries).toEqual([])
      expect(s.tokenUsage).toEqual({ accumulated: 0, latest: 0 })
    })
  })

  // -----------------------------------------------------------------------
  // New structured actions
  // -----------------------------------------------------------------------

  describe('addNarrativeEntry', () => {
    it('creates an entry with a non-empty string id', () => {
      useGameStore.getState().addNarrativeEntry({ type: 'narrative', content: 'Hello' })
      const entries = useGameStore.getState().narrativeEntries
      expect(entries).toHaveLength(1)
      expect(entries[0].id).toBeTypeOf('string')
      expect(entries[0].id.length).toBeGreaterThan(0)
    })

    it('creates an entry with the correct type', () => {
      useGameStore.getState().addNarrativeEntry({ type: 'player', content: 'I attack!' })
      const entry = useGameStore.getState().narrativeEntries[0]
      expect(entry.type).toBe('player')
    })

    it('creates an entry with the correct content', () => {
      useGameStore.getState().addNarrativeEntry({ type: 'narrative', content: 'The dragon roars.' })
      const entry = useGameStore.getState().narrativeEntries[0]
      expect(entry.content).toBe('The dragon roars.')
    })

    it('creates an entry with a numeric timestamp', () => {
      useGameStore.getState().addNarrativeEntry({ type: 'separator', content: '---' })
      const entry = useGameStore.getState().narrativeEntries[0]
      expect(entry.timestamp).toBeTypeOf('number')
      expect(Number.isFinite(entry.timestamp)).toBe(true)
    })

    it('appends multiple entries in order', () => {
      useGameStore.getState().addNarrativeEntry({ type: 'player', content: 'Entry 1' })
      useGameStore.getState().addNarrativeEntry({ type: 'narrative', content: 'Entry 2' })
      useGameStore.getState().addNarrativeEntry({ type: 'tool_result', content: 'Entry 3' })

      const entries = useGameStore.getState().narrativeEntries
      expect(entries).toHaveLength(3)
      expect(entries[0].content).toBe('Entry 1')
      expect(entries[1].content).toBe('Entry 2')
      expect(entries[2].content).toBe('Entry 3')
    })

    it('handles all entry types', () => {
      const types: NarrativeEntry['type'][] = ['player', 'narrative', 'tool_result', 'separator', 'error']
      for (const t of types) {
        useGameStore.getState().addNarrativeEntry({ type: t, content: `type: ${t}` })
      }

      const entries = useGameStore.getState().narrativeEntries
      expect(entries).toHaveLength(5)
      for (let i = 0; i < types.length; i += 1) {
        expect(entries[i].type).toBe(types[i])
      }
    })

    it('each entry gets a unique id', () => {
      useGameStore.getState().addNarrativeEntry({ type: 'narrative', content: 'A' })
      useGameStore.getState().addNarrativeEntry({ type: 'narrative', content: 'B' })
      useGameStore.getState().addNarrativeEntry({ type: 'narrative', content: 'C' })

      const entries = useGameStore.getState().narrativeEntries
      const ids = entries.map((e) => e.id)
      const uniqueIds = new Set(ids)
      expect(uniqueIds.size).toBe(3)
    })
  })

  describe('setStreamingText', () => {
    it('sets streamingText to a given string', () => {
      useGameStore.getState().setStreamingText('The DM says...')
      expect(useGameStore.getState().streamingText).toBe('The DM says...')
    })

    it('sets streamingText to empty string', () => {
      useGameStore.setState({ streamingText: 'old stream' })
      useGameStore.getState().setStreamingText('')
      expect(useGameStore.getState().streamingText).toBe('')
    })

    it('overwrites previous streamingText', () => {
      useGameStore.getState().setStreamingText('first')
      useGameStore.getState().setStreamingText('second')
      expect(useGameStore.getState().streamingText).toBe('second')
    })
  })

  describe('setIsThinking', () => {
    it('sets isThinking to true', () => {
      useGameStore.getState().setIsThinking(true)
      expect(useGameStore.getState().isThinking).toBe(true)
    })

    it('sets isThinking to false', () => {
      useGameStore.setState({ isThinking: true })
      useGameStore.getState().setIsThinking(false)
      expect(useGameStore.getState().isThinking).toBe(false)
    })
  })

  describe('setNpcThinking', () => {
    it('sets npcThinking with npcId and hint', () => {
      useGameStore.getState().setNpcThinking('goblin_1', 'about to flee')
      expect(useGameStore.getState().npcThinking).toEqual({
        npcId: 'goblin_1',
        hint: 'about to flee',
      })
    })

    it('defaults hint to empty string when omitted', () => {
      useGameStore.getState().setNpcThinking('dragon')
      expect(useGameStore.getState().npcThinking).toEqual({
        npcId: 'dragon',
        hint: '',
      })
    })

    it('clears npcThinking when npcId is null', () => {
      useGameStore.setState({ npcThinking: { npcId: 'goblin', hint: 'sneak' } })
      useGameStore.getState().setNpcThinking(null)
      expect(useGameStore.getState().npcThinking).toBeNull()
    })

    it('clearing with null ignores hint parameter', () => {
      useGameStore.setState({ npcThinking: { npcId: 'goblin', hint: 'sneak' } })
      useGameStore.getState().setNpcThinking(null, 'should be ignored')
      expect(useGameStore.getState().npcThinking).toBeNull()
    })

    it('replaces existing npcThinking with new values', () => {
      useGameStore.setState({ npcThinking: { npcId: 'goblin', hint: 'sneak' } })
      useGameStore.getState().setNpcThinking('dragon', 'breathes fire')
      expect(useGameStore.getState().npcThinking).toEqual({
        npcId: 'dragon',
        hint: 'breathes fire',
      })
    })
  })

  describe('incrementTurnCount', () => {
    it('increments from 0 to 1', () => {
      useGameStore.getState().incrementTurnCount()
      expect(useGameStore.getState().turnCount).toBe(1)
    })

    it('increments from 1 to 2', () => {
      useGameStore.setState({ turnCount: 1 })
      useGameStore.getState().incrementTurnCount()
      expect(useGameStore.getState().turnCount).toBe(2)
    })

    it('increments from any starting count', () => {
      useGameStore.setState({ turnCount: 42 })
      useGameStore.getState().incrementTurnCount()
      expect(useGameStore.getState().turnCount).toBe(43)
    })

    it('multiple increments accumulate', () => {
      useGameStore.getState().incrementTurnCount()
      useGameStore.getState().incrementTurnCount()
      useGameStore.getState().incrementTurnCount()
      expect(useGameStore.getState().turnCount).toBe(3)
    })
  })

  describe('setTokenUsage', () => {
    it('sets both accumulated and latest', () => {
      useGameStore.getState().setTokenUsage({ accumulated: 100, latest: 25 })
      expect(useGameStore.getState().tokenUsage).toEqual({ accumulated: 100, latest: 25 })
    })

    it('partial update with only accumulated preserves latest', () => {
      useGameStore.setState({ tokenUsage: { accumulated: 50, latest: 10 } })
      useGameStore.getState().setTokenUsage({ accumulated: 75 })
      expect(useGameStore.getState().tokenUsage).toEqual({ accumulated: 75, latest: 10 })
    })

    it('partial update with only latest preserves accumulated', () => {
      useGameStore.setState({ tokenUsage: { accumulated: 50, latest: 10 } })
      useGameStore.getState().setTokenUsage({ latest: 20 })
      expect(useGameStore.getState().tokenUsage).toEqual({ accumulated: 50, latest: 20 })
    })

    it('empty partial update preserves both fields', () => {
      useGameStore.setState({ tokenUsage: { accumulated: 99, latest: 33 } })
      useGameStore.getState().setTokenUsage({})
      expect(useGameStore.getState().tokenUsage).toEqual({ accumulated: 99, latest: 33 })
    })

    it('setting accumulated to 0 works', () => {
      useGameStore.setState({ tokenUsage: { accumulated: 100, latest: 50 } })
      useGameStore.getState().setTokenUsage({ accumulated: 0 })
      expect(useGameStore.getState().tokenUsage).toEqual({ accumulated: 0, latest: 50 })
    })
  })

  describe('toggleAutoScroll', () => {
    it('toggles from true to false', () => {
      useGameStore.setState({ autoScroll: true })
      useGameStore.getState().toggleAutoScroll()
      expect(useGameStore.getState().autoScroll).toBe(false)
    })

    it('toggles from false to true', () => {
      useGameStore.setState({ autoScroll: false })
      useGameStore.getState().toggleAutoScroll()
      expect(useGameStore.getState().autoScroll).toBe(true)
    })

    it('toggles multiple times returns to original', () => {
      useGameStore.setState({ autoScroll: true })
      useGameStore.getState().toggleAutoScroll()
      useGameStore.getState().toggleAutoScroll()
      expect(useGameStore.getState().autoScroll).toBe(true)
    })
  })

  describe('setShowTokens', () => {
    it('sets showTokens to true', () => {
      useGameStore.getState().setShowTokens(true)
      expect(useGameStore.getState().showTokens).toBe(true)
    })

    it('sets showTokens to false', () => {
      useGameStore.setState({ showTokens: true })
      useGameStore.getState().setShowTokens(false)
      expect(useGameStore.getState().showTokens).toBe(false)
    })

    it('sets showTokens to true after being false', () => {
      useGameStore.setState({ showTokens: false })
      useGameStore.getState().setShowTokens(true)
      expect(useGameStore.getState().showTokens).toBe(true)
    })
  })

  // -----------------------------------------------------------------------
  // applyStateUpdate — operates on worldState
  // -----------------------------------------------------------------------

  describe('applyStateUpdate', () => {
    it('set action on a top-level worldState field', () => {
      useGameStore.getState().setWorldState({ hp: 50 })
      useGameStore.getState().applyStateUpdate({
        hp: { action: 'set', value: 30 },
      })
      expect(useGameStore.getState().worldState).toEqual({ hp: 30 })
    })

    it('set action with null value', () => {
      useGameStore.getState().setWorldState({ hp: 50, name: 'Hero' })
      useGameStore.getState().applyStateUpdate({
        hp: { action: 'set', value: null },
      })
      const ws = useGameStore.getState().worldState
      expect(ws).toHaveProperty('name', 'Hero')
      expect(ws).toHaveProperty('hp', null)
    })

    it('set action creates nested path via dot notation', () => {
      useGameStore.getState().setWorldState({})
      useGameStore.getState().applyStateUpdate({
        'stats.hp': { action: 'set', value: 100 },
      })
      expect(useGameStore.getState().worldState).toEqual({
        stats: { hp: 100 },
      })
    })

    it('set action on deeply nested path', () => {
      useGameStore.getState().setWorldState({ a: { b: { c: 1 } } })
      useGameStore.getState().applyStateUpdate({
        'a.b.c': { action: 'set', value: 99 },
      })
      expect(useGameStore.getState().worldState).toEqual({ a: { b: { c: 99 } } })
    })

    it('set action creates intermediate objects for nested path', () => {
      useGameStore.getState().setWorldState({})
      useGameStore.getState().applyStateUpdate({
        'inventory.weapon.damage': { action: 'set', value: 12 },
      })
      expect(useGameStore.getState().worldState).toEqual({
        inventory: { weapon: { damage: 12 } },
      })
    })

    it('add action increments a numeric field', () => {
      useGameStore.getState().setWorldState({ gold: 100 })
      useGameStore.getState().applyStateUpdate({
        gold: { action: 'add', value: 50 },
      })
      expect(useGameStore.getState().worldState).toEqual({ gold: 150 })
    })

    it('add action works with nested numeric field', () => {
      useGameStore.getState().setWorldState({ stats: { xp: 200 } })
      useGameStore.getState().applyStateUpdate({
        'stats.xp': { action: 'add', value: 50 },
      })
      expect(useGameStore.getState().worldState).toEqual({ stats: { xp: 250 } })
    })

    it('add action sets value when field does not exist', () => {
      useGameStore.getState().setWorldState({})
      useGameStore.getState().applyStateUpdate({
        score: { action: 'add', value: 10 },
      })
      expect(useGameStore.getState().worldState).toEqual({ score: 10 })
    })

    it('add action does not crash with non-numeric value', () => {
      useGameStore.getState().setWorldState({})
      expect(() => {
        useGameStore.getState().applyStateUpdate({
          tag: { action: 'add', value: 'hello' },
        })
      }).not.toThrow()
    })

    it('add action with negative value decrements', () => {
      useGameStore.getState().setWorldState({ hp: 50 })
      useGameStore.getState().applyStateUpdate({
        hp: { action: 'add', value: -10 },
      })
      expect(useGameStore.getState().worldState).toEqual({ hp: 40 })
    })

    it('append action appends to a string', () => {
      useGameStore.getState().setWorldState({ name: 'He' })
      useGameStore.getState().applyStateUpdate({
        name: { action: 'append', value: 'ro' },
      })
      expect(useGameStore.getState().worldState).toEqual({ name: 'Hero' })
    })

    it('append action pushes to an array', () => {
      useGameStore.getState().setWorldState({ items: ['sword'] })
      useGameStore.getState().applyStateUpdate({
        items: { action: 'append', value: 'shield' },
      })
      expect(useGameStore.getState().worldState).toEqual({ items: ['sword', 'shield'] })
    })

    it('append action sets value when field does not exist and is not array/string', () => {
      useGameStore.getState().setWorldState({})
      useGameStore.getState().applyStateUpdate({
        newField: { action: 'append', value: 'hello' },
      })
      expect(useGameStore.getState().worldState).toEqual({ newField: 'hello' })
    })

    it('remove action deletes a field', () => {
      useGameStore.getState().setWorldState({ hp: 50, name: 'Hero' })
      useGameStore.getState().applyStateUpdate({
        hp: { action: 'remove' },
      })
      expect(useGameStore.getState().worldState).toEqual({ name: 'Hero' })
      expect(useGameStore.getState().worldState).not.toHaveProperty('hp')
    })

    it('remove action on non-existent path does not crash', () => {
      useGameStore.getState().setWorldState({ hp: 50 })
      expect(() => {
        useGameStore.getState().applyStateUpdate({
          nonexistent: { action: 'remove' },
        })
      }).not.toThrow()
      expect(useGameStore.getState().worldState).toEqual({ hp: 50 })
    })

    it('remove action on nested non-existent path does not crash', () => {
      useGameStore.getState().setWorldState({})
      expect(() => {
        useGameStore.getState().applyStateUpdate({
          'a.b.c': { action: 'remove' },
        })
      }).not.toThrow()
    })

    it('empty updates dict does nothing', () => {
      useGameStore.getState().setWorldState({ hp: 50 })
      useGameStore.getState().applyStateUpdate({})
      expect(useGameStore.getState().worldState).toEqual({ hp: 50 })
    })

    it('multiple updates in a single call are all applied', () => {
      useGameStore.getState().setWorldState({ hp: 50, gold: 100, name: 'He' })
      useGameStore.getState().applyStateUpdate({
        hp: { action: 'set', value: 30 },
        gold: { action: 'add', value: 25 },
        name: { action: 'append', value: 'ro' },
      })
      expect(useGameStore.getState().worldState).toEqual({
        hp: 30,
        gold: 125,
        name: 'Hero',
      })
    })

    it('works when worldState is null (creates fresh object)', () => {
      useGameStore.getState().setWorldState(null)
      useGameStore.getState().applyStateUpdate({
        hp: { action: 'set', value: 10 },
      })
      expect(useGameStore.getState().worldState).toEqual({ hp: 10 })
    })

    it('multiple calls accumulate changes', () => {
      useGameStore.getState().setWorldState({ x: 0 })
      useGameStore.getState().applyStateUpdate({ x: { action: 'add', value: 1 } })
      useGameStore.getState().applyStateUpdate({ x: { action: 'add', value: 2 } })
      useGameStore.getState().applyStateUpdate({ x: { action: 'add', value: 3 } })
      expect(useGameStore.getState().worldState).toEqual({ x: 6 })
    })

    // --- Prototype-pollution related paths ---

    it('rejects __proto__ paths to prevent prototype pollution', () => {
      useGameStore.getState().setWorldState({})
      useGameStore.getState().applyStateUpdate({
        '__proto__.polluted': { action: 'set', value: true },
      })
      // Verify the prototype was NOT polluted
      expect(({} as Record<string, unknown>).polluted).toBeUndefined()
      expect(useGameStore.getState().worldState).toEqual({})
    })

    it('rejects constructor paths to prevent prototype pollution', () => {
      useGameStore.getState().setWorldState({})
      useGameStore.getState().applyStateUpdate({
        constructor: { action: 'set' as const, value: 'test' },
      })
      // Verify worldState is unchanged
      expect(useGameStore.getState().worldState).toEqual({})
    })

    it('rejects prototype paths to prevent prototype pollution', () => {
      useGameStore.getState().setWorldState({})
      useGameStore.getState().applyStateUpdate({
        'prototype.polluted': { action: 'set', value: true },
      })
      expect(({} as Record<string, unknown>).polluted).toBeUndefined()
      expect(useGameStore.getState().worldState).toEqual({})
    })
  })

  // -----------------------------------------------------------------------
  // resetGame
  // -----------------------------------------------------------------------

  describe('resetGame', () => {
    it('resets game-specific fields but preserves autoScroll and showTokens', () => {
      // Set all fields to non-default values
      const store = useGameStore.getState()
      store.setNarrative('Story')
      store.setWorldState({ turn: 5 })
      store.setPlayerInput('hello')
      store.setProcessing(true)
      store.setIsActive(true)
      store.setError('boom')
      store.addNarrativeEntry({ type: 'narrative', content: 'Entry' })
      store.addNarrativeEntry({ type: 'player', content: 'More' })
      store.setStreamingText('stream')
      store.setIsThinking(true)
      store.setNpcThinking('goblin', 'sneak')
      store.incrementTurnCount()
      store.setTokenUsage({ accumulated: 100, latest: 20 })
      store.setShowTokens(true)
      store.toggleAutoScroll() // becomes false

      store.resetGame()

      const s = useGameStore.getState()
      // Fields that should be reset
      expect(s.narrative).toBe('')
      expect(s.worldState).toBeNull()
      expect(s.playerInput).toBe('')
      expect(s.processing).toBe(false)
      expect(s.isActive).toBe(false)
      expect(s.error).toBeNull()
      expect(s.narrativeEntries).toEqual([])
      expect(s.streamingText).toBe('')
      expect(s.isThinking).toBe(false)
      expect(s.npcThinking).toBeNull()
      expect(s.turnCount).toBe(0)
      expect(s.tokenUsage).toEqual({ accumulated: 0, latest: 0 })

      // Fields that should be preserved
      expect(s.autoScroll).toBe(false) // preserved after toggle
      expect(s.showTokens).toBe(true) // preserved
    })

    it('preserves autoScroll when it was true and showTokens when false', () => {
      // With defaults, resetGame keeps them
      useGameStore.getState().setNarrative('Some story')
      useGameStore.getState().resetGame()

      const s = useGameStore.getState()
      expect(s.autoScroll).toBe(true)
      expect(s.showTokens).toBe(false)
    })

    it('preserves autoScroll=false and showTokens=true after resetGame', () => {
      useGameStore.getState().toggleAutoScroll() // -> false
      useGameStore.getState().setShowTokens(true)
      useGameStore.getState().setNarrative('Temporary story')

      useGameStore.getState().resetGame()

      const s = useGameStore.getState()
      expect(s.autoScroll).toBe(false)
      expect(s.showTokens).toBe(true)
      expect(s.narrative).toBe('')
    })
  })
})
