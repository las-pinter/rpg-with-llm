/**
 * CampfireMode tests — story-driven character creation orchestrator.
 *
 * Covers: initial render, question navigation, answer tracking, generate
 * validation (too few answers, missing connection), generate API call on
 * success, error display, loading state, and the empty-questions fallback.
 * Also covers the hero name input, filled indicator, and accessibility.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { act } from 'react'
import userEvent from '@testing-library/user-event'
import { useCharacterStore } from '../../stores/characterStore'
import { useConnectionStore } from '../../stores/connectionStore'
import { generateCharacter } from '../../api/endpoints'
import type { CharacterRules, Character } from '../../api/types'
import { ItemType } from '../../api/types'
import CampfireMode from './CampfireMode'

// ---------------------------------------------------------------------------
// Mock the generate endpoint
// ---------------------------------------------------------------------------

vi.mock('../../api/endpoints', async () => {
  const actual = await vi.importActual('../../api/endpoints')
  return {
    ...actual,
    generateCharacter: vi.fn(),
  }
})

const mockGenerateCharacter = vi.mocked(generateCharacter)

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
    'Where were you born, and what was your childhood like?',
    'What drove you to become an adventurer?',
    'Describe a pivotal moment that shaped who you are.',
    'What is your greatest fear, and why?',
    'Who or what do you value above all else?',
  ],
}

const sampleCharacter: Character = {
  id: 'char-123',
  name: 'Kaelen Shadowmere',
  character_class: 'Fighter',
  level: 1,
  abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
  skills: ['Athletics', 'Intimidation'],
  backstory: 'Born in the shadow of the Iron Peaks…',
  appearance: 'Tall with a scarred face.',
  personality: 'Determined and brooding.',
  hooks: ['Seeks the lost sword of his father.'],
  inventory: [
    { id: 'item-1', name: 'Longsword', quantity: 1, item_type: ItemType.WEAPON, properties: {}, description: '', weight: 3, value: 15 },
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
    storyAnswers: sampleRules.assisted_creation_questions.map(() => ''),
    currentQuestion: 0,
    creationMode: 'campfire',
  })
  useConnectionStore.getState().reset()
  useConnectionStore.getState().setSettings({
    baseUrl: 'http://localhost:11434',
    model: 'llama3.2',
    providerType: 'ollama',
  })
}

/** Fill in the first N answers in the store (simulates user typing answers). */
function fillAnswers(count: number) {
  const answers = sampleRules.assisted_creation_questions.map((_, i) =>
    i < count ? `Answer number ${i + 1}` : '',
  )
  useCharacterStore.getState().setStoryAnswers(answers)
}

beforeEach(() => {
  setupStore()
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Initial render
// ---------------------------------------------------------------------------

describe('CampfireMode — initial render', () => {
  it('renders StoryProgress with the correct counter', () => {
    render(<CampfireMode />)
    expect(screen.getByText(/Question 1 of 5/)).toBeInTheDocument()
  })

  it('renders the first story question', () => {
    render(<CampfireMode />)
    expect(
      screen.getByText('Where were you born, and what was your childhood like?'),
    ).toBeInTheDocument()
  })

  it('renders a Previous button (disabled on first question)', () => {
    render(<CampfireMode />)
    const prev = screen.getByRole('button', { name: /Previous question/ })
    expect(prev).toBeInTheDocument()
    expect(prev).toBeDisabled()
  })

  it('renders a Next button on the first question', () => {
    render(<CampfireMode />)
    const next = screen.getByRole('button', { name: /Next question/ })
    expect(next).toBeInTheDocument()
    expect(next).not.toBeDisabled()
  })

  it('renders the hero name input', () => {
    render(<CampfireMode />)
    const input = screen.getByRole('textbox', { name: /Hero/i })
    expect(input).toBeInTheDocument()
    expect(input).toHaveValue('')
  })

  it('renders AbilityGrid and ClassSelector', () => {
    render(<CampfireMode />)
    expect(screen.getByText('Ability Scores')).toBeInTheDocument()
    expect(screen.getByText('Class')).toBeInTheDocument()
  })

  it('shows 0 of 5 answered when no answers filled', () => {
    render(<CampfireMode />)
    expect(screen.getByText('0 of 5 questions answered')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Question navigation
// ---------------------------------------------------------------------------

describe('CampfireMode — question navigation', () => {
  it('moves to the next question on Next click', async () => {
    const user = userEvent.setup()
    render(<CampfireMode />)

    await user.click(screen.getByRole('button', { name: /Next question/ }))

    expect(
      screen.getByText('What drove you to become an adventurer?'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Question 2 of 5/)).toBeInTheDocument()
  })

  it('moves to the previous question on Prev click', async () => {
    const user = userEvent.setup()
    render(<CampfireMode />)

    // Go forward first
    await user.click(screen.getByRole('button', { name: /Next question/ }))
    expect(screen.getByText(/Question 2 of 5/)).toBeInTheDocument()

    // Then go back
    await user.click(screen.getByRole('button', { name: /Previous question/ }))
    expect(screen.getByText(/Question 1 of 5/)).toBeInTheDocument()
  })

  it('disables Previous on the first question', () => {
    render(<CampfireMode />)
    expect(
      screen.getByRole('button', { name: /Previous question/ }),
    ).toBeDisabled()
  })

  it('shows Generate button instead of Next on the last question', async () => {
    const user = userEvent.setup()
    render(<CampfireMode />)

    // Navigate to the last question (index 4)
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    expect(screen.getByText(/Question 5 of 5/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Next question/ }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Generate character from story/ }),
    ).toBeInTheDocument()
  })

  it('Previous is enabled after moving away from question 0', async () => {
    const user = userEvent.setup()
    render(<CampfireMode />)

    await user.click(screen.getByRole('button', { name: /Next question/ }))
    expect(
      screen.getByRole('button', { name: /Previous question/ }),
    ).not.toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// Question navigation — extended boundaries
// ---------------------------------------------------------------------------

describe('CampfireMode — question navigation extended', () => {
  it('enables Previous button on the last question', async () => {
    const user = userEvent.setup()
    render(<CampfireMode />)

    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    expect(screen.getByText(/Question 5 of 5/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Previous question/ }),
    ).not.toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// Hero name input
// ---------------------------------------------------------------------------

describe('CampfireMode — hero name input', () => {
  it('updates the name as the user types', async () => {
    const user = userEvent.setup()
    render(<CampfireMode />)

    const input = screen.getByRole('textbox', { name: /Hero/i })
    await user.type(input, 'Kaelen')
    expect(input).toHaveValue('Kaelen')
  })

  it('shows the placeholder text', () => {
    render(<CampfireMode />)
    expect(
      screen.getByPlaceholderText('Leave blank for a surprise…'),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Filled indicator
// ---------------------------------------------------------------------------

describe('CampfireMode — filled indicator', () => {
  it('shows updated filled count when answers are provided', () => {
    fillAnswers(2)
    render(<CampfireMode />)
    expect(screen.getByText('2 of 5 questions answered')).toBeInTheDocument()
  })

  it('shows all answered when all questions are filled', () => {
    fillAnswers(5)
    render(<CampfireMode />)
    expect(screen.getByText('5 of 5 questions answered')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Generate validation
// ---------------------------------------------------------------------------

describe('CampfireMode — generate validation', () => {
  it('shows error when fewer than 3 answers are filled', async () => {
    const user = userEvent.setup()
    fillAnswers(2)
    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(
      screen.getByText(/Answer at least 3 questions/),
    ).toBeInTheDocument()
    expect(mockGenerateCharacter).not.toHaveBeenCalled()
  })

  it('shows error when connection settings are missing', async () => {
    const user = userEvent.setup()
    fillAnswers(4)

    // Clear connection settings
    useConnectionStore.getState().setSettings({
      baseUrl: '',
      model: '',
      providerType: '',
    })

    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(
      screen.getByText(/No LLM provider configured/),
    ).toBeInTheDocument()
    expect(mockGenerateCharacter).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Generate validation — boundary value
// ---------------------------------------------------------------------------

describe('CampfireMode — generate validation boundary', () => {
  it('calls generateCharacter when exactly 3 answers are filled', async () => {
    const user = userEvent.setup()
    fillAnswers(3)
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    render(<CampfireMode />)

    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(mockGenerateCharacter).toHaveBeenCalledTimes(1)
    expect(
      screen.queryByText(/Answer at least 3 questions/),
    ).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Error clearing on navigation and re-generate
// ---------------------------------------------------------------------------

describe('CampfireMode — error clearing', () => {
  it('clears error when navigating to a new question', async () => {
    const user = userEvent.setup()
    fillAnswers(2)
    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    // Trigger validation error
    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )
    expect(screen.getByText(/Answer at least 3 questions/)).toBeInTheDocument()

    // Navigate back — error should be cleared by handlePrev
    await user.click(screen.getByRole('button', { name: /Previous question/ }))
    expect(
      screen.queryByText(/Answer at least 3 questions/),
    ).not.toBeInTheDocument()
  })

  it('clears error when re-generating after a failure', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockRejectedValueOnce(new Error('First failure'))

    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    // First generate — fails with network error
    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )
    expect(await screen.findByText(/First failure/)).toBeInTheDocument()

    // Second generate — succeeds
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })
    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    // Error should be gone (handleGenerate calls setError(null) first)
    expect(screen.queryByText(/First failure/)).not.toBeInTheDocument()
    expect(mockGenerateCharacter).toHaveBeenCalledTimes(2)
  })
})

// ---------------------------------------------------------------------------
// Generate API call (success and failure)
// ---------------------------------------------------------------------------

describe('CampfireMode — generate API call', () => {
  it('calls generateCharacter with correct params on successful generate', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(mockGenerateCharacter).toHaveBeenCalledTimes(1)

    const params = mockGenerateCharacter.mock.calls[0][0]
    expect(params.answers).toBeDefined()
    expect(Object.keys(params.answers).length).toBe(5)
    expect(params.character_class).toBe('Fighter')
    expect(params.abilities).toEqual({
      STR: 15,
      DEX: 13,
      CON: 14,
      INT: 10,
      WIS: 12,
      CHA: 8,
    })
    expect(params.provider).toEqual({
      base_url: 'http://localhost:11434',
      model: 'llama3.2',
      provider_type: 'ollama',
    })
  })

  it('includes name in the request when user entered one', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    render(<CampfireMode />)

    // Enter a name
    const nameInput = screen.getByRole('textbox', { name: /Hero/i })
    await user.type(nameInput, 'Kaelen')

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(mockGenerateCharacter).toHaveBeenCalledTimes(1)
    expect(mockGenerateCharacter.mock.calls[0][0].name).toBe('Kaelen')
  })

  it('sets generatedCharacter and switches to review mode on success', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    // Wait for async state update
    await act(async () => {
      // The click already resolved the mock
    })

    expect(useCharacterStore.getState().generatedCharacter).toEqual(
      sampleCharacter,
    )
    expect(useCharacterStore.getState().creationMode).toBe('review')
  })

  it('shows error banner on API failure', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockRejectedValueOnce(new Error('Server is on fire'))

    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    // Wait for the error to appear
    const errorEl = await screen.findByText(/Server is on fire/)
    expect(errorEl).toBeInTheDocument()
  })

  it('shows error when API returns ok: false', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: false,
      character: undefined as unknown as Character,
    })

    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    const errorEl = await screen.findByText(
      /Failed to generate character/,
    )
    expect(errorEl).toBeInTheDocument()
  })

  it('includes api_key when connection store has it', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    useConnectionStore.getState().setApiKey('sk-test-key')

    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(mockGenerateCharacter).toHaveBeenCalledTimes(1)
    expect(mockGenerateCharacter.mock.calls[0][0].provider?.api_key).toBe(
      'sk-test-key',
    )
  })
})

// ---------------------------------------------------------------------------
// Generate API — edge cases (partial answers, empty abilities)
// ---------------------------------------------------------------------------

describe('CampfireMode — generate API edge cases', () => {
  it('sends only non-empty answers in the request when some are empty', async () => {
    const user = userEvent.setup()
    fillAnswers(3) // Only first 3 filled, last 2 empty
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    render(<CampfireMode />)

    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(mockGenerateCharacter).toHaveBeenCalledTimes(1)
    const params = mockGenerateCharacter.mock.calls[0][0]
    expect(Object.keys(params.answers).length).toBe(3)
    expect(params.answers[0]).toBe('Answer number 1')
    expect(params.answers[1]).toBe('Answer number 2')
    expect(params.answers[2]).toBe('Answer number 3')
    expect(params.answers[3]).toBeUndefined()
    expect(params.answers[4]).toBeUndefined()
  })

  it('omits abilities from request when abilities dict is empty', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    // Clear abilities in store to trigger the empty-check guard
    useCharacterStore.getState().setState({ abilities: {} })

    render(<CampfireMode />)

    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(mockGenerateCharacter).toHaveBeenCalledTimes(1)
    const params = mockGenerateCharacter.mock.calls[0][0]
    expect(params.abilities).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe('CampfireMode — loading state', () => {
  it('shows loading text while generating', async () => {
    const user = userEvent.setup()
    fillAnswers(5)

    // Never resolve — keeps loading
    mockGenerateCharacter.mockReturnValueOnce(
      new Promise(() => {}),
    )

    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(
      screen.getByText(/The Dungeon Master is weaving your story/),
    ).toBeInTheDocument()
  })

  it('disables navigation buttons while generating', async () => {
    const user = userEvent.setup()
    fillAnswers(5)

    mockGenerateCharacter.mockReturnValueOnce(
      new Promise(() => {}),
    )

    render(<CampfireMode />)

    // Navigate to last question
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    const generateBtn = screen.getByRole('button', {
      name: /Generate character from story/,
    })
    await user.click(generateBtn)

    // All nav buttons should be disabled
    expect(
      screen.getByRole('button', { name: /Previous question/ }),
    ).toBeDisabled()
    expect(generateBtn).toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// Loading state — extended (overlay accessibility, button text)
// ---------------------------------------------------------------------------

describe('CampfireMode — loading state extended', () => {
  it('displays a loading overlay with status role while generating', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockReturnValueOnce(new Promise(() => {}))

    render(<CampfireMode />)

    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(
      screen.getByText(/The Dungeon Master is weaving your story/),
    ).toBeInTheDocument()
  })

  it('shows "Weaving…" on the generate button while loading', async () => {
    const user = userEvent.setup()
    fillAnswers(5)
    mockGenerateCharacter.mockReturnValueOnce(new Promise(() => {}))

    render(<CampfireMode />)

    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    const generateBtn = screen.getByRole('button', {
      name: /Generate character from story/,
    })
    await user.click(generateBtn)

    expect(generateBtn).toHaveTextContent(/Weaving/)
  })
})

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe('CampfireMode — empty state', () => {
  it('shows empty state message when no questions are loaded', () => {
    useCharacterStore.getState().setState({
      rules: {
        ...sampleRules,
        assisted_creation_questions: [],
      },
      storyAnswers: [],
    })
    render(<CampfireMode />)
    expect(
      screen.getByText(/No character creation questions loaded/),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe('CampfireMode — accessibility', () => {
  it('has accessible Previous button', () => {
    render(<CampfireMode />)
    expect(
      screen.getByRole('button', { name: /Previous question/ }),
    ).toBeInTheDocument()
  })

  it('has accessible Next button', () => {
    render(<CampfireMode />)
    expect(
      screen.getByRole('button', { name: /Next question/ }),
    ).toBeInTheDocument()
  })

  it('has accessible generate button on last question', async () => {
    const user = userEvent.setup()
    render(<CampfireMode />)

    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    expect(
      screen.getByRole('button', { name: /Generate character from story/ }),
    ).toBeInTheDocument()
  })

  it('error banner has alert role', async () => {
    const user = userEvent.setup()
    fillAnswers(2)
    render(<CampfireMode />)

    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /Next question/ }))
    }

    await user.click(
      screen.getByRole('button', { name: /Generate character from story/ }),
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})
