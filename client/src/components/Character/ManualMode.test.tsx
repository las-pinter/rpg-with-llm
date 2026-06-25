/**
 * ManualMode tests — grubnik-scrutiny of the point-buy character creation form.
 *
 * Covers: initial render, input updates, validation (empty name), create API
 * call on success, API failure, error display, loading state, rules guard,
 * and accessibility.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useCharacterStore } from '../../stores/characterStore'
import { createCharacter } from '../../api/endpoints'
import type { CharacterRules, Character } from '../../api/types'
import { ItemType } from '../../api/types'
import ManualMode from './ManualMode'

// ---------------------------------------------------------------------------
// Mock the create endpoint
// ---------------------------------------------------------------------------

vi.mock('../../api/endpoints', async () => {
  const actual = await vi.importActual('../../api/endpoints')
  return {
    ...actual,
    createCharacter: vi.fn(),
    getStartingGear: vi.fn().mockResolvedValue({ ok: true, gear_options: {} }),
  }
})

const mockCreateCharacter = vi.mocked(createCharacter)

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const sampleRules: CharacterRules = {
  valid_classes: ['Fighter', 'Wizard', 'Rogue', 'Cleric'],
  standard_abilities: ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
  class_templates: {
    Fighter: {
      abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
      hp: 12,
      ac: 18,
      skills: ['Athletics', 'Intimidation'],
    },
    Wizard: {
      abilities: { STR: 8, DEX: 12, CON: 13, INT: 15, WIS: 14, CHA: 10 },
      hp: 8,
      ac: 12,
      skills: ['Arcana', 'Investigation'],
    },
  },
  point_buy: {
    costs: { '8': 0, '9': 1, '10': 2, '11': 3, '12': 4, '13': 5, '14': 7, '15': 9 },
    max_points: 27,
    min_score: 8,
    max_score: 15,
  },
  assisted_creation_questions: [
    'Where were you born?',
    'What drives you?',
  ],
}

const sampleCharacter: Character = {
  id: 'char-456',
  name: 'Thorn Ironvein',
  character_class: 'Fighter',
  level: 1,
  abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
  skills: ['Athletics', 'Intimidation'],
  backstory: 'A dwarf from the Iron Peaks…',
  appearance: 'Stocky with a braided beard.',
  personality: 'Stubborn and loyal.',
  hooks: ['Seeks lost dwarven halls.'],
  inventory: [
    { id: 'item-1', name: 'Battleaxe', quantity: 1, item_type: ItemType.WEAPON, properties: {}, description: '', weight: 4, value: 10 },
    { id: 'item-2', name: 'Shield', quantity: 1, item_type: ItemType.ARMOR, properties: {}, description: '', weight: 6, value: 10 },
    { id: 'item-3', name: 'Chainmail', quantity: 1, item_type: ItemType.ARMOR, properties: {}, description: '', weight: 55, value: 75 },
  ],
  equipped_items: [],
  resources: { hp: { value: 12, max: 12, short_rest_recovery: '1d10', long_rest_recovery: 'full' } },
  gold: 15,
  xp: 0,
  created_at: '2026-01-01T00:00:00Z',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setupStore() {
  useCharacterStore.getState().reset()
  useCharacterStore.getState().setState({
    rules: sampleRules,
    abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
    selectedClass: 'Fighter',
    remainingPoints: 0,
    creationMode: 'manual',
    manualName: '',
    manualAppearance: '',
    manualBackstory: '',
  })
}

beforeEach(() => {
  setupStore()
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Initial render
// ---------------------------------------------------------------------------

describe('ManualMode — initial render', () => {
  it('renders the name input', () => {
    render(<ManualMode />)
    expect(screen.getByLabelText('Character Name')).toBeInTheDocument()
  })

  it('renders ClassSelector', () => {
    render(<ManualMode />)
    expect(screen.getByLabelText('Class')).toBeInTheDocument()
  })

  it('renders AbilityGrid', () => {
    render(<ManualMode />)
    expect(screen.getByText('Ability Scores')).toBeInTheDocument()
  })

  it('renders the appearance textarea', () => {
    render(<ManualMode />)
    expect(screen.getByLabelText('Appearance')).toBeInTheDocument()
  })

  it('renders the backstory textarea', () => {
    render(<ManualMode />)
    expect(screen.getByLabelText('Backstory')).toBeInTheDocument()
  })

  it('renders the create button', () => {
    render(<ManualMode />)
    expect(
      screen.getByRole('button', { name: /Create character/i }),
    ).toBeInTheDocument()
  })

  it('name input starts empty', () => {
    render(<ManualMode />)
    const input = screen.getByLabelText('Character Name') as HTMLInputElement
    expect(input.value).toBe('')
  })

  it('appearance textarea starts empty', () => {
    render(<ManualMode />)
    const textarea = screen.getByLabelText('Appearance') as HTMLTextAreaElement
    expect(textarea.value).toBe('')
  })

  it('backstory textarea starts empty', () => {
    render(<ManualMode />)
    const textarea = screen.getByLabelText('Backstory') as HTMLTextAreaElement
    expect(textarea.value).toBe('')
  })

  it('shows placeholder text on name input', () => {
    render(<ManualMode />)
    expect(
      screen.getByPlaceholderText(/hero/),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Input updates
// ---------------------------------------------------------------------------

describe('ManualMode — input updates', () => {
  it('updates name as the user types', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    const input = screen.getByLabelText('Character Name')
    await user.type(input, 'Thorn Ironvein')
    expect(input).toHaveValue('Thorn Ironvein')
  })

  it('updates appearance as the user types', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    const textarea = screen.getByLabelText('Appearance')
    await user.type(textarea, 'Stocky dwarf with braided beard')
    expect(textarea).toHaveValue('Stocky dwarf with braided beard')
  })

  it('updates backstory as the user types', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    const textarea = screen.getByLabelText('Backstory')
    await user.type(textarea, 'Born in the Iron Peaks…')
    expect(textarea).toHaveValue('Born in the Iron Peaks…')
  })

  it('typing name updates the store value', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    const input = screen.getByLabelText('Character Name')
    await user.type(input, 'Grumble')

    expect(useCharacterStore.getState().manualName).toBe('Grumble')
  })

  it('typing appearance updates the store value', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    const textarea = screen.getByLabelText('Appearance')
    await user.type(textarea, 'Tall and rugged')

    expect(useCharacterStore.getState().manualAppearance).toBe('Tall and rugged')
  })

  it('typing backstory updates the store value', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    const textarea = screen.getByLabelText('Backstory')
    await user.type(textarea, 'Born under a bad sign')

    expect(useCharacterStore.getState().manualBackstory).toBe('Born under a bad sign')
  })
})

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

describe('ManualMode — validation', () => {
  it('shows error when name is empty on create', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(screen.getByText(/Please enter a character name/)).toBeInTheDocument()
    expect(mockCreateCharacter).not.toHaveBeenCalled()
  })

  it('shows error when name is only whitespace', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    const input = screen.getByLabelText('Character Name')
    await user.type(input, '   ')
    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(screen.getByText(/Please enter a character name/)).toBeInTheDocument()
    expect(mockCreateCharacter).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

describe('ManualMode — error behavior', () => {
  it('does not show error banner on initial render', () => {
    render(<ManualMode />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('clears error when create is retried after validation failure', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    // Trigger empty-name error
    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )
    expect(screen.getByRole('alert')).toBeInTheDocument()

    // Now fill in a name and try again
    const input = screen.getByLabelText('Character Name')
    await user.type(input, 'Thorn')

    // Re-click create — this time it'll try the API (no mock set, so it'll reject)
    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    // The old error banner should be gone (replaced by API error)
    await vi.waitFor(() => {
      // Should not show the validation error anymore
      expect(
        screen.queryByText(/Please enter a character name/),
      ).not.toBeInTheDocument()
    })
  })

  it('displays generic message when catch receives non-Error value', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockRejectedValueOnce('string error' as unknown as Error)

    useCharacterStore.getState().setManualName('Thorn')

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(
      await screen.findByText(/Unknown error creating character/),
    ).toBeInTheDocument()
  })
})

describe('ManualMode — API call', () => {
  it('calls createCharacter with correct params on success', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    // Pre-fill store with manual form data
    useCharacterStore.getState().setManualName('Thorn Ironvein')
    useCharacterStore.getState().setManualAppearance('Stocky with a braided beard.')
    useCharacterStore.getState().setManualBackstory('A dwarf from the Iron Peaks…')

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(mockCreateCharacter).toHaveBeenCalledTimes(1)

    const params = mockCreateCharacter.mock.calls[0][0]
    expect(params.name).toBe('Thorn Ironvein')
    expect(params.character_class).toBe('Fighter')
    expect(params.abilities).toEqual({
      STR: 15,
      DEX: 13,
      CON: 14,
      INT: 10,
      WIS: 12,
      CHA: 8,
    })
    expect(params.appearance).toBe('Stocky with a braided beard.')
    expect(params.backstory).toBe('A dwarf from the Iron Peaks…')
  })

  it('omits appearance and backstory when empty', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    // Only set name, leave appearance and backstory empty
    useCharacterStore.getState().setManualName('Thorn')

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(mockCreateCharacter).toHaveBeenCalledTimes(1)
    const params = mockCreateCharacter.mock.calls[0][0]
    expect(params.appearance).toBeUndefined()
    expect(params.backstory).toBeUndefined()
  })

  it('omits appearance when it is only whitespace', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    useCharacterStore.getState().setManualName('Thorn')
    useCharacterStore.getState().setManualAppearance('   ')
    useCharacterStore.getState().setManualBackstory('A real backstory.')

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    const params = mockCreateCharacter.mock.calls[0][0]
    expect(params.appearance).toBeUndefined()
    expect(params.backstory).toBe('A real backstory.')
  })

  it('omits backstory when it is only whitespace', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    useCharacterStore.getState().setManualName('Thorn')
    useCharacterStore.getState().setManualAppearance('Has a scar.')
    useCharacterStore.getState().setManualBackstory('   ')

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    const params = mockCreateCharacter.mock.calls[0][0]
    expect(params.appearance).toBe('Has a scar.')
    expect(params.backstory).toBeUndefined()
  })

  it('sets generatedCharacter and switches to review on success', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    useCharacterStore.getState().setManualName('Thorn Ironvein')

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    // Wait for microtasks
    await vi.waitFor(() => {
      expect(useCharacterStore.getState().generatedCharacter).toEqual(
        sampleCharacter,
      )
    })
    expect(useCharacterStore.getState().creationMode).toBe('review')
  })
})

// ---------------------------------------------------------------------------
// Ability adjustments
// ---------------------------------------------------------------------------

describe('ManualMode — ability adjustments', () => {
  it('passes adjusted ability scores to createCharacter', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    // Adjust abilities in the store before creating
    useCharacterStore.getState().setManualName('Thorn')
    useCharacterStore.getState().setState({
      abilities: { STR: 14, DEX: 14, CON: 14, INT: 10, WIS: 10, CHA: 10 },
      remainingPoints: 5,
      selectedClass: 'Fighter',
    })

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(mockCreateCharacter).toHaveBeenCalledTimes(1)
    const params = mockCreateCharacter.mock.calls[0][0]
    expect(params.abilities).toEqual({
      STR: 14,
      DEX: 14,
      CON: 14,
      INT: 10,
      WIS: 10,
      CHA: 10,
    })
  })
})

// ---------------------------------------------------------------------------
// API error handling
// ---------------------------------------------------------------------------

describe('ManualMode — API error handling', () => {
  it('shows error banner on API failure', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockRejectedValueOnce(new Error('Server exploded'))

    useCharacterStore.getState().setManualName('Thorn')

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(await screen.findByText(/Server exploded/)).toBeInTheDocument()
  })

  it('shows error when API returns ok: false', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockResolvedValueOnce({
      ok: false,
      character: undefined as unknown as Character,
    })

    useCharacterStore.getState().setManualName('Thorn')

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(
      await screen.findByText(/Failed to create character/),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe('ManualMode — loading state', () => {
  it('shows "Creating…" on the button while creating', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockReturnValueOnce(new Promise(() => {}))

    useCharacterStore.getState().setManualName('Thorn')

    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(screen.getByRole('button', { name: /Create character/i })).toHaveTextContent(
      /Creating/,
    )
  })

  it('disables the create button while creating', async () => {
    const user = userEvent.setup()
    mockCreateCharacter.mockReturnValueOnce(new Promise(() => {}))

    useCharacterStore.getState().setManualName('Thorn')

    render(<ManualMode />)

    const btn = screen.getByRole('button', { name: /Create character/i })
    await user.click(btn)

    expect(btn).toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// Rules guard (empty state)
// ---------------------------------------------------------------------------

describe('ManualMode — rules guard', () => {
  it('shows empty state when rules is null', () => {
    useCharacterStore.getState().reset() // rules is null by default
    render(<ManualMode />)
    expect(
      screen.getByText(/No character creation rules loaded/),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe('ManualMode — accessibility', () => {
  it('name input has label association with htmlFor', () => {
    render(<ManualMode />)
    const input = screen.getByLabelText('Character Name')
    expect(input).toHaveAttribute('id', 'manual-name')
  })

  it('appearance textarea has label association', () => {
    render(<ManualMode />)
    const textarea = screen.getByLabelText('Appearance')
    expect(textarea).toHaveAttribute('id', 'manual-appearance')
  })

  it('backstory textarea has label association', () => {
    render(<ManualMode />)
    const textarea = screen.getByLabelText('Backstory')
    expect(textarea).toHaveAttribute('id', 'manual-backstory')
  })

  it('name input has aria-required attribute', () => {
    render(<ManualMode />)
    expect(screen.getByLabelText('Character Name')).toHaveAttribute(
      'aria-required',
      'true',
    )
  })

  it('error banner has alert role', async () => {
    const user = userEvent.setup()
    render(<ManualMode />)

    await user.click(
      screen.getByRole('button', { name: /Create character/i }),
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})
