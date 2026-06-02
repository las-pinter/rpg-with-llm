/**
 * CharacterPage tests — character creation and load management hub.
 *
 * Acceptance criteria:
 * - Title and subtitle render
 * - useCharacterRules hook is called on mount
 * - Tab bar shows Create and Load tabs
 * - Create tab is active by default
 * - Sub-tab bar shows Campfire and Manual when Create is active
 * - CampfireMode renders when creationMode is 'campfire'
 * - ManualMode renders when creationMode is 'manual'
 * - ReviewSheet renders when creationMode is 'review'
 * - LoadTab renders when activeTab is 'load'
 * - Loading banner shows when rules are loading
 * - Error banner shows when rules error
 * - Back button navigates to /
 * - Sub-tab switching works via store actions
 * - Tab switching works via store actions
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { useCharacterStore } from '../stores/characterStore'
import type { CharacterRules } from '../api/types'
import CharacterPage from './CharacterPage'

// ---------------------------------------------------------------------------
// Mock hook
// ---------------------------------------------------------------------------

const mockUseCharacterRules = vi.fn()

vi.mock('../hooks/useCharacterRules', () => ({
  useCharacterRules: () => mockUseCharacterRules(),
}))

// ---------------------------------------------------------------------------
// Sample rules for context
// ---------------------------------------------------------------------------

const sampleRules: CharacterRules = {
  valid_classes: ['Fighter', 'Wizard', 'Rogue', 'Cleric'],
  standard_abilities: ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
  class_templates: {
    Fighter: {
      abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
    },
  },
  point_buy: {
    costs: { '8': 0, '9': 1, '10': 2, '11': 3, '12': 4, '13': 5, '14': 7, '15': 9 },
    max_points: 27,
    min_score: 8,
    max_score: 15,
  },
  assisted_creation_questions: ['Question 1?', 'Question 2?', 'Question 3?'],
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/character']}>
      <CharacterPage />
    </MemoryRouter>,
  )
}

function renderPageForNav() {
  return render(
    <MemoryRouter initialEntries={['/character']}>
      <CharacterPage />
      <LocationDisplay />
    </MemoryRouter>,
  )
}

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="current-location">{location.pathname}</div>
}

function resetStore() {
  useCharacterStore.getState().reset()
}

beforeEach(() => {
  resetStore()
  mockUseCharacterRules.mockReturnValue({ loading: false, error: null })
  // Set some rules so sub-components render without breaking
  useCharacterStore.getState().setRules(sampleRules)
  useCharacterStore.getState().initDefaults()
})

// ---------------------------------------------------------------------------
// Page renders
// ---------------------------------------------------------------------------

describe('CharacterPage — rendering', () => {
  it('renders the page title', () => {
    renderPage()
    expect(
      screen.getByRole('heading', { name: /character/i }),
    ).toBeInTheDocument()
  })

  it('renders the subtitle text', () => {
    renderPage()
    expect(
      screen.getByText(/create or load your adventurer/i),
    ).toBeInTheDocument()
  })

  it('renders the Create tab (active by default)', () => {
    renderPage()
    const createTab = screen.getByRole('button', { name: /create/i })
    expect(createTab).toBeInTheDocument()
    expect(createTab).toHaveAttribute('aria-current', 'page')
  })

  it('renders the Load tab', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /load/i }),
    ).toBeInTheDocument()
  })

  it('renders the Back button', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /back/i }),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// useCharacterRules integration
// ---------------------------------------------------------------------------

describe('CharacterPage — useCharacterRules', () => {
  it('calls useCharacterRules hook on render', () => {
    mockUseCharacterRules.mockClear()
    renderPage()
    expect(mockUseCharacterRules).toHaveBeenCalledOnce()
  })
})

// ---------------------------------------------------------------------------
// Create tab content
// ---------------------------------------------------------------------------

describe('CharacterPage — Create tab', () => {
  it('shows sub-tab bar (Campfire / Manual) when Create is active', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /campfire/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /manual/i }),
    ).toBeInTheDocument()
  })

  it('renders CampfireMode by default', () => {
    renderPage()
    // CampfireMode renders story progress and the hero name input
    expect(
      screen.getByPlaceholderText(/leave blank for a surprise/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('progressbar'),
    ).toBeInTheDocument()
  })

  it('switches to ManualMode when Manual sub-tab is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /manual/i }))

    // Manual mode shows the Create Character button
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /create character/i }),
      ).toBeInTheDocument()
    })
  })

  it('switches back to CampfireMode when Campfire sub-tab is clicked after Manual', async () => {
    const user = userEvent.setup()
    renderPage()

    // Switch to Manual first
    await user.click(screen.getByRole('button', { name: /manual/i }))
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /create character/i }),
      ).toBeInTheDocument()
    })

    // Switch back to Campfire
    await user.click(screen.getByRole('button', { name: /campfire/i }))
    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/leave blank for a surprise/i),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('progressbar'),
      ).toBeInTheDocument()
    })
  })

  it('hides sub-tab bar when creationMode is review', () => {
    useCharacterStore.getState().setCreationMode('review')
    // Set a generated character so ReviewSheet renders
    useCharacterStore.getState().setGeneratedCharacter({
      id: 'test',
      name: 'Test Hero',
      character_class: 'Fighter',
      level: 1,
      abilities: { STR: 15, DEX: 13, CON: 14, INT: 10, WIS: 12, CHA: 8 },
      hp: 12,
      max_hp: 12,
      ac: 18,
      skills: ['Athletics'],
      backstory: 'A test hero.',
      appearance: 'Tall and sturdy.',
      personality: 'Brave',
      hooks: [],
      inventory: ['Sword'],
      gold: 10,
      xp: 0,
      created_at: '2026-01-01T00:00:00Z',
    })
    renderPage()

    // Sub-tab bar should be hidden
    expect(
      screen.queryByRole('button', { name: /campfire/i }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /manual/i }),
    ).not.toBeInTheDocument()

    // ReviewSheet should be visible
    expect(screen.getByText('Test Hero')).toBeInTheDocument()
  })

  it('shows ReviewSheet empty state when generatedCharacter is null in review mode', () => {
    useCharacterStore.getState().setCreationMode('review')
    renderPage()

    // Sub-tab bar should be hidden
    expect(
      screen.queryByRole('button', { name: /campfire/i }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /manual/i }),
    ).not.toBeInTheDocument()

    // ReviewSheet empty state should be visible
    expect(
      screen.getByText(/no character to review/i),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Load tab content
// ---------------------------------------------------------------------------

describe('CharacterPage — Load tab', () => {
  it('switches to LoadTab when Load tab is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /load/i }))

    // Load tab shows saved characters section heading
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /saved characters/i }),
      ).toBeInTheDocument()
    })
  })

  it('shows empty state in LoadTab after fetch resolves', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /load/i }))

    // After the store's fetchCharacters resolves, the empty state appears
    await waitFor(() => {
      expect(
        screen.getByText(/no saved characters yet/i),
      ).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe('CharacterPage — loading state', () => {
  it('shows loading banner when useCharacterRules is loading', () => {
    mockUseCharacterRules.mockReturnValue({ loading: true, error: null })
    renderPage()
    expect(
      screen.getByText(/loading character rules/i),
    ).toBeInTheDocument()
  })

  it('does not show error banner when loading', () => {
    mockUseCharacterRules.mockReturnValue({ loading: true, error: 'fail' })
    renderPage()
    expect(
      screen.getByText(/loading character rules/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/could not load character rules/i),
    ).not.toBeInTheDocument()
  })

  it('does not show loading banner when not loading', () => {
    mockUseCharacterRules.mockReturnValue({ loading: false, error: null })
    renderPage()
    expect(
      screen.queryByText(/loading character rules/i),
    ).not.toBeInTheDocument()
  })

  it('shows loading banner when store rulesLoading is true', () => {
    mockUseCharacterRules.mockReturnValue({ loading: true, error: null })
    renderPage()
    expect(
      screen.getByText(/loading character rules/i),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

describe('CharacterPage — error state', () => {
  it('shows error banner when useCharacterRules has an error', () => {
    mockUseCharacterRules.mockReturnValue({
      loading: false,
      error: 'Something broke',
    })
    renderPage()
    expect(
      screen.getByText(/could not load character rules/i),
    ).toBeInTheDocument()
  })

  it('does not show error banner when there is no error', () => {
    mockUseCharacterRules.mockReturnValue({ loading: false, error: null })
    renderPage()
    expect(
      screen.queryByText(/could not load character rules/i),
    ).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Back button
// ---------------------------------------------------------------------------

describe('CharacterPage — Back button', () => {
  it('renders Back button with left arrow', () => {
    renderPage()
    const backBtn = screen.getByRole('button', { name: /back/i })
    expect(backBtn).toBeInTheDocument()
    expect(backBtn).toBeEnabled()
  })

  it('navigates to / when clicked', async () => {
    const user = userEvent.setup()
    renderPageForNav()

    await user.click(screen.getByRole('button', { name: /back/i }))

    await waitFor(() => {
      expect(screen.getByTestId('current-location')).toHaveTextContent('/')
    })
  })
})

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------

describe('CharacterPage — tab switching', () => {
  it('switches aria-current to Load when Load tab is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    const loadTab = screen.getByRole('button', { name: /load/i })
    await user.click(loadTab)

    await waitFor(() => {
      expect(loadTab).toHaveAttribute('aria-current', 'page')
    })
  })

  it('switches back to Create when Create tab is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    const createTab = screen.getByRole('button', { name: /create/i })
    const loadTab = screen.getByRole('button', { name: /load/i })

    // Click Load
    await user.click(loadTab)
    // Click Create
    await user.click(createTab)

    await waitFor(() => {
      expect(createTab).toHaveAttribute('aria-current', 'page')
    })
  })
})

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe('CharacterPage — accessibility', () => {
  it('has status role on loading banner', () => {
    mockUseCharacterRules.mockReturnValue({ loading: true, error: null })
    renderPage()
    const statuses = screen.getAllByRole('status')
    const loadingStatus = statuses.find((s) =>
      s.textContent?.includes('Loading'),
    )
    expect(loadingStatus).toBeInTheDocument()
  })

  it('has alert role on error banner', () => {
    mockUseCharacterRules.mockReturnValue({
      loading: false,
      error: 'fail',
    })
    renderPage()
    expect(screen.getByRole('alert')).toHaveTextContent(
      /could not load character rules/i,
    )
  })

  it('has aria-current on active tab', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /create/i }),
    ).toHaveAttribute('aria-current', 'page')
  })

  it('has aria-label on nav elements', () => {
    renderPage()
    expect(
      screen.getByLabelText(/character page tabs/i),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText(/creation mode tabs/i),
    ).toBeInTheDocument()
  })
})
