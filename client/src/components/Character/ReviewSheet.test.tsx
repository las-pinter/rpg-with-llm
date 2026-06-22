/**
 * ReviewSheet tests — meticulous goblin inspection of the character sheet.
 *
 * Covers: rendering all character details, empty state, edit/save toggle,
 * regenerate API call and error handling, start adventure navigation,
 * cancel edit mode, and accessibility.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { useCharacterStore } from '../../stores/characterStore'
import { useConnectionStore } from '../../stores/connectionStore'
import { generateCharacter } from '../../api/endpoints'
import type { Character } from '../../api/types'
import { ItemType } from '../../api/types'
import ReviewSheet from './ReviewSheet'

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

const sampleCharacter: Character = {
  id: 'char-789',
  name: 'Elara Moonshadow',
  character_class: 'Rogue',
  level: 1,
  abilities: { STR: 10, DEX: 15, CON: 12, INT: 13, WIS: 8, CHA: 14 },
  skills: ['Stealth', 'Sleight of Hand', 'Deception'],
  backstory: 'Raised in the shadowy streets of Waterdeep…',
  appearance: 'Slender with sharp green eyes.',
  personality: 'Cunning and quick-witted.',
  hooks: ['Seeks a lost artifact.'],
  inventory: [
    { id: 'item-1', name: 'Rapier', quantity: 1, item_type: ItemType.WEAPON, properties: {}, description: '', weight: 2, value: 25 },
    { id: 'item-2', name: 'Shortbow', quantity: 1, item_type: ItemType.WEAPON, properties: {}, description: '', weight: 2, value: 25 },
    { id: 'item-3', name: "Thieves' Tools", quantity: 1, item_type: ItemType.TOOL, properties: {}, description: '', weight: 1, value: 25 },
    { id: 'item-4', name: 'Dark Cloak', quantity: 1, item_type: ItemType.ARMOR, properties: {}, description: '', weight: 3, value: 10 },
  ],
  equipped_items: [],
  resources: { hp: { value: 10, max: 10, short_rest_recovery: '1d8', long_rest_recovery: 'full' } },
  gold: 50,
  xp: 0,
  created_at: '2026-01-01T00:00:00Z',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setupStore(overrides?: Record<string, unknown>) {
  useCharacterStore.getState().reset()
  useCharacterStore.getState().setState({
    generatedCharacter: sampleCharacter,
    isEditing: false,
    ...overrides,
  })
  useConnectionStore.getState().reset()
  useConnectionStore.getState().setSettings({
    baseUrl: 'http://localhost:11434',
    model: 'llama3.2',
    providerType: 'ollama',
  })
}

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="current-location">{location.pathname}</div>
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/character']}>
      <ReviewSheet />
      <LocationDisplay />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setupStore()
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Initial render
// ---------------------------------------------------------------------------

describe('ReviewSheet — initial render', () => {
  it('renders the character name', () => {
    renderPage()
    expect(screen.getByText('Elara Moonshadow')).toBeInTheDocument()
  })

  it('renders character class and level', () => {
    renderPage()
    expect(screen.getByText(/Lvl 1 Rogue/)).toBeInTheDocument()
  })

  it('renders ability scores', () => {
    renderPage()
    // Labels and values should appear
    expect(screen.getByText('STR')).toBeInTheDocument()
    expect(screen.getByText('DEX')).toBeInTheDocument()
    expect(screen.getByText('CON')).toBeInTheDocument()
    expect(screen.getByText('INT')).toBeInTheDocument()
    expect(screen.getByText('WIS')).toBeInTheDocument()
    expect(screen.getByText('CHA')).toBeInTheDocument()
    // Ability values — some may overlap with stat values (e.g. 15 = DEX + AC)
    expect(screen.getAllByText('15').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('10').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('8')).toBeInTheDocument()
  })

  it('renders HP stat', () => {
    renderPage()
    expect(screen.getByText('HP')).toBeInTheDocument()
    // HP value may also appear as STR ability score — use getAllByText
    expect(screen.getAllByText('10').length).toBeGreaterThanOrEqual(1)
  })

  it('renders AC stat', () => {
    renderPage()
    expect(screen.getByText('AC')).toBeInTheDocument()
    const acElements = screen.getAllByText('15')
    // AC value is 15 (shared with DEX score)
    expect(acElements.length).toBeGreaterThanOrEqual(1)
  })

  it('renders Gold stat', () => {
    renderPage()
    expect(screen.getByText('Gold')).toBeInTheDocument()
    expect(screen.getByText('50')).toBeInTheDocument()
  })

  it('renders skills as badges', () => {
    renderPage()
    expect(screen.getByText('Stealth')).toBeInTheDocument()
    expect(screen.getByText('Sleight of Hand')).toBeInTheDocument()
    expect(screen.getByText('Deception')).toBeInTheDocument()
  })

  it('renders appearance text', () => {
    renderPage()
    expect(screen.getByText(/Slender with sharp green eyes/)).toBeInTheDocument()
  })

  it('renders backstory text', () => {
    renderPage()
    expect(screen.getByText(/Raised in the shadowy streets/)).toBeInTheDocument()
  })

  it('renders inventory items', () => {
    renderPage()
    expect(screen.getByText('Rapier')).toBeInTheDocument()
    expect(screen.getByText('Shortbow')).toBeInTheDocument()
    expect(screen.getByText(/Thieves' Tools/)).toBeInTheDocument()
    expect(screen.getByText('Dark Cloak')).toBeInTheDocument()
  })

  it('renders action buttons', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /Edit character/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Regenerate character/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Start adventure/i }),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Structured inventory display
// ---------------------------------------------------------------------------

describe('ReviewSheet — structured inventory', () => {
  it('shows group titles for each item type present', () => {
    renderPage()
    expect(screen.getByText('Weapons')).toBeInTheDocument()
    expect(screen.getByText('Armor')).toBeInTheDocument()
    expect(screen.getByText('Tools')).toBeInTheDocument()
  })

  it('does not show group titles for absent item types', () => {
    renderPage()
    expect(screen.queryByText('Consumables')).not.toBeInTheDocument()
    expect(screen.queryByText('Containers')).not.toBeInTheDocument()
    expect(screen.queryByText('Quest Items')).not.toBeInTheDocument()
    expect(screen.queryByText('Miscellaneous')).not.toBeInTheDocument()
  })

  it('shows type icons for each item', () => {
    renderPage()
    // Two WEAPON icons (Rapier + Shortbow)
    expect(screen.getAllByText('⚔️')).toHaveLength(2)
    // One ARMOR icon
    expect(screen.getByText('🛡️')).toBeInTheDocument()
    // One TOOL icon
    expect(screen.getByText('🔧')).toBeInTheDocument()
  })

  it('shows item weight', () => {
    renderPage()
    // Two items weigh 2 lb (Rapier + Shortbow)
    expect(screen.getAllByText('2 lb')).toHaveLength(2)
    // One item weighs 3 lb (Dark Cloak)
    expect(screen.getByText('3 lb')).toBeInTheDocument()
    // One item weighs 1 lb (Thieves' Tools)
    expect(screen.getByText('1 lb')).toBeInTheDocument()
  })

  it('shows quantity when greater than 1', () => {
    const charMultiQty: Character = {
      ...sampleCharacter,
      inventory: [
        { ...sampleCharacter.inventory[0], quantity: 3 },
        ...sampleCharacter.inventory.slice(1),
      ],
    }
    useCharacterStore.getState().setGeneratedCharacter(charMultiQty)
    renderPage()
    // Rapier now has quantity 3 — check for ×3
    expect(screen.getByText('×3')).toBeInTheDocument()
  })

  it('does not show quantity when quantity is 1', () => {
    renderPage()
    // All sample items have quantity 1 — × should not appear
    expect(screen.queryByText('×')).not.toBeInTheDocument()
  })

  it('shows equipped badge [E] for items in equipped_items', () => {
    const charEquipped: Character = {
      ...sampleCharacter,
      equipped_items: ['item-1'], // Rapier
    }
    useCharacterStore.getState().setGeneratedCharacter(charEquipped)
    renderPage()
    expect(screen.getByText('[E]')).toBeInTheDocument()
  })

  it('does not show [E] badge when no items are equipped', () => {
    renderPage()
    expect(screen.queryByText('[E]')).not.toBeInTheDocument()
  })

  it('renders item names in structured inventory', () => {
    renderPage()
    expect(screen.getByText('Rapier')).toBeInTheDocument()
    expect(screen.getByText('Shortbow')).toBeInTheDocument()
    expect(screen.getByText(/Thieves' Tools/)).toBeInTheDocument()
    expect(screen.getByText('Dark Cloak')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe('ReviewSheet — empty state', () => {
  it('shows empty message when no character is set', () => {
    useCharacterStore.getState().setGeneratedCharacter(null)
    renderPage()
    expect(
      screen.getByText(/No character to review/),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Edit / Save toggle
// ---------------------------------------------------------------------------

describe('ReviewSheet — edit mode', () => {
  it('enters edit mode on Edit click', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Edit character/i }),
    )

    expect(useCharacterStore.getState().isEditing).toBe(true)
    // Edit textareas should now appear
    expect(
      screen.getByLabelText('Edit appearance'),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Edit backstory'),
    ).toBeInTheDocument()
  })

  it('shows Save and Cancel buttons in edit mode', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Edit character/i }),
    )

    expect(
      screen.getByRole('button', { name: /Save character changes/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Cancel editing/i }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Edit character/i }),
    ).not.toBeInTheDocument()
  })

  it('pre-fills edit textareas with current values', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Edit character/i }),
    )

    const appearanceTextarea = screen.getByLabelText(
      'Edit appearance',
    ) as HTMLTextAreaElement
    const backstoryTextarea = screen.getByLabelText(
      'Edit backstory',
    ) as HTMLTextAreaElement

    expect(appearanceTextarea.value).toBe('Slender with sharp green eyes.')
    expect(backstoryTextarea.value).toBe(
      'Raised in the shadowy streets of Waterdeep…',
    )
  })

  it('saves edits and exits edit mode on Save', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Edit character/i }),
    )

    const appearanceTextarea = screen.getByLabelText('Edit appearance')
    const backstoryTextarea = screen.getByLabelText('Edit backstory')

    // Clear and type new values
    await user.clear(appearanceTextarea)
    await user.type(appearanceTextarea, 'Mysterious hooded figure.')
    await user.clear(backstoryTextarea)
    await user.type(backstoryTextarea, 'A former urchin from the docks.')

    await user.click(
      screen.getByRole('button', { name: /Save character changes/i }),
    )

    expect(useCharacterStore.getState().isEditing).toBe(false)
    const updated = useCharacterStore.getState().generatedCharacter
    expect(updated?.appearance).toBe('Mysterious hooded figure.')
    expect(updated?.backstory).toBe('A former urchin from the docks.')
  })

  it('cancels edit mode and reverts changes', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Edit character/i }),
    )

    const backstoryTextarea = screen.getByLabelText('Edit backstory')
    await user.clear(backstoryTextarea)
    await user.type(backstoryTextarea, 'This change should be discarded.')

    await user.click(
      screen.getByRole('button', { name: /Cancel editing/i }),
    )

    expect(useCharacterStore.getState().isEditing).toBe(false)
    // Original backstory should be preserved
    expect(
      screen.getByText(/Raised in the shadowy streets/),
    ).toBeInTheDocument()
  })

  it('typing in edit textarea updates local value before save', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Edit character/i }),
    )

    const backstoryTextarea = screen.getByLabelText(
      'Edit backstory',
    ) as HTMLTextAreaElement
    const appearanceTextarea = screen.getByLabelText(
      'Edit appearance',
    ) as HTMLTextAreaElement

    await user.clear(backstoryTextarea)
    await user.type(backstoryTextarea, 'Partially typed…')

    await user.clear(appearanceTextarea)
    await user.type(appearanceTextarea, 'Still editing…')

    // Before save, the textareas should reflect what was typed
    expect(backstoryTextarea.value).toBe('Partially typed…')
    expect(appearanceTextarea.value).toBe('Still editing…')
  })

  it('saves empty appearance and backstory on Save', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Edit character/i }),
    )

    const appearanceTextarea = screen.getByLabelText('Edit appearance')
    const backstoryTextarea = screen.getByLabelText('Edit backstory')

    await user.clear(appearanceTextarea)
    await user.clear(backstoryTextarea)

    await user.click(
      screen.getByRole('button', { name: /Save character changes/i }),
    )

    const updated = useCharacterStore.getState().generatedCharacter
    expect(updated?.appearance).toBe('')
    expect(updated?.backstory).toBe('')
  })
})

// ---------------------------------------------------------------------------
// Regenerate
// ---------------------------------------------------------------------------

describe('ReviewSheet — regenerate', () => {
  it('calls generateCharacter on regenerate click', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    // Set up some story answers so they're included
    useCharacterStore.getState().setStoryAnswers([
      'Born in Waterdeep',
      'Wanted to escape poverty',
    ])

    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    expect(mockGenerateCharacter).toHaveBeenCalledTimes(1)
  })

  it('passes correct class and abilities to generateCharacter', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    // Override selected class and abilities in the store
    useCharacterStore.getState().setState({
      selectedClass: 'Wizard',
      abilities: { STR: 8, DEX: 14, CON: 12, INT: 15, WIS: 13, CHA: 10 },
    })

    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    expect(mockGenerateCharacter).toHaveBeenCalledTimes(1)
    const params = mockGenerateCharacter.mock.calls[0][0]
    expect(params.character_class).toBe('Wizard')
    expect(params.abilities).toEqual({
      STR: 8,
      DEX: 14,
      CON: 12,
      INT: 15,
      WIS: 13,
      CHA: 10,
    })
  })

  it('passes provider config from connection store', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    const params = mockGenerateCharacter.mock.calls[0][0] as {
      provider?: { base_url: string; model: string; provider_type: string }
    }
    expect(params.provider).toBeDefined()
    expect(params.provider!.base_url).toBe('http://localhost:11434')
    expect(params.provider!.model).toBe('llama3.2')
    expect(params.provider!.provider_type).toBe('ollama')
  })

  it('omits abilities when store abilities are empty', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    // Clear abilities in store
    useCharacterStore.getState().setState({ abilities: {} })

    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    const params = mockGenerateCharacter.mock.calls[0][0]
    expect(params.abilities).toBeUndefined()
  })

  it('updates character on successful regenerate', async () => {
    const user = userEvent.setup()
    const updatedCharacter: Character = {
      ...sampleCharacter,
      name: 'Elara Shadowmoon', // Changed name
      backstory: 'A rewritten past…',
    }
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: updatedCharacter,
    })

    useCharacterStore.getState().setStoryAnswers([
      'Born in Waterdeep',
      'Wanted to escape poverty',
    ])

    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    await vi.waitFor(() => {
      expect(
        useCharacterStore.getState().generatedCharacter?.name,
      ).toBe('Elara Shadowmoon')
    })
  })

  it('shows error on regenerate failure', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockRejectedValueOnce(
      new Error('LLM provider error'),
    )

    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    expect(await screen.findByText(/LLM provider error/)).toBeInTheDocument()
  })

  it('displays generic message when regenerate catches non-Error value', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockRejectedValueOnce(
      'string error' as unknown as Error,
    )

    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    expect(
      await screen.findByText(/Unknown error regenerating character/),
    ).toBeInTheDocument()
  })

  it('disables regenerate button while regenerating', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockReturnValueOnce(new Promise(() => {}))

    renderPage()

    const btn = screen.getByRole('button', { name: /Regenerate character/i })
    await user.click(btn)

    expect(btn).toBeDisabled()
  })

  it('shows "Regenerating…" on button while in progress', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockReturnValueOnce(new Promise(() => {}))

    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    expect(
      screen.getByRole('button', { name: /Regenerate character/i }),
    ).toHaveTextContent(/Regenerating/)
  })
})

// ---------------------------------------------------------------------------
// Start Adventure navigation
// ---------------------------------------------------------------------------

describe('ReviewSheet — start adventure', () => {
  it('navigates to /game on Start Adventure click', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Start adventure/i }),
    )

    expect(screen.getByTestId('current-location')).toHaveTextContent('/game')
  })
})

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('ReviewSheet — edge cases', () => {
  it('shows empty hint when appearance is empty string', () => {
    const charNoAppearance: Character = {
      ...sampleCharacter,
      appearance: '',
    }
    useCharacterStore.getState().setGeneratedCharacter(charNoAppearance)
    renderPage()
    expect(
      screen.getByText(/No appearance described/),
    ).toBeInTheDocument()
  })

  it('shows empty hint when backstory is empty string', () => {
    const charNoBackstory: Character = {
      ...sampleCharacter,
      backstory: '',
    }
    useCharacterStore.getState().setGeneratedCharacter(charNoBackstory)
    renderPage()
    expect(
      screen.getByText(/No backstory written/),
    ).toBeInTheDocument()
  })

  it('renders HP/max_hp split when different', () => {
    const charDamaged: Character = {
      ...sampleCharacter,
      resources: {
        ...sampleCharacter.resources,
        hp: { ...sampleCharacter.resources.hp, value: 5, max: 10 },
      },
    }
    useCharacterStore.getState().setGeneratedCharacter(charDamaged)
    renderPage()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText(/\/ 10/)).toBeInTheDocument()
  })

  it('hides skills section when skills array is empty', () => {
    const charNoSkills: Character = {
      ...sampleCharacter,
      skills: [],
    }
    useCharacterStore.getState().setGeneratedCharacter(charNoSkills)
    renderPage()
    expect(screen.queryByText('Skills')).not.toBeInTheDocument()
  })

  it('hides inventory section when inventory array is empty', () => {
    const charNoInventory: Character = {
      ...sampleCharacter,
      inventory: [],
    }
    useCharacterStore.getState().setGeneratedCharacter(charNoInventory)
    renderPage()
    expect(screen.queryByText('Inventory')).not.toBeInTheDocument()
  })

  it('does not show HP/max_hp split when hp equals max_hp', () => {
    // Character already has hp === max_hp (both 10)
    renderPage()
    // The split "/ 10" should not appear because hp === max_hp
    expect(screen.queryByText(/\/ 10/)).not.toBeInTheDocument()
    // HP value is still displayed (just without the split)
    expect(screen.getAllByText('10').length).toBeGreaterThanOrEqual(1)
  })
})

// ---------------------------------------------------------------------------
// Error behavior
// ---------------------------------------------------------------------------

describe('ReviewSheet — error behavior', () => {
  it('does not show error banner on initial render', () => {
    renderPage()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('clears error on subsequent regenerate attempt', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockRejectedValueOnce(
      new Error('First failure'),
    )

    renderPage()

    // Trigger regenerate failure
    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )
    expect(await screen.findByText(/First failure/)).toBeInTheDocument()

    // Reset the mock for a successful retry
    mockGenerateCharacter.mockResolvedValueOnce({
      ok: true,
      character: sampleCharacter,
    })

    // Click regenerate again
    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    // The error banner should disappear
    await vi.waitFor(() => {
      expect(
        screen.queryByText(/First failure/),
      ).not.toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe('ReviewSheet — accessibility', () => {
  it('edit button has accessible name', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /Edit character/i }),
    ).toBeInTheDocument()
  })

  it('regenerate button has accessible name', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /Regenerate character/i }),
    ).toBeInTheDocument()
  })

  it('start adventure button has accessible name', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /Start adventure/i }),
    ).toBeInTheDocument()
  })

  it('error banner has alert role', async () => {
    const user = userEvent.setup()
    mockGenerateCharacter.mockRejectedValueOnce(new Error('Fail'))

    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Regenerate character/i }),
    )

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('edit textareas have aria-labels', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      screen.getByRole('button', { name: /Edit character/i }),
    )

    expect(
      screen.getByLabelText('Edit appearance'),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Edit backstory'),
    ).toBeInTheDocument()
  })
})
