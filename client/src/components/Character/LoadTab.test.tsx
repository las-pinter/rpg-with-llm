/**
 * LoadTab tests — saved characters and saved games browsing.
 *
 * Acceptance criteria:
 * - Fetches characters and saves on mount
 * - Shows loading states while fetching
 * - Shows empty states when no characters/saves
 * - Shows character cards with Load and Delete buttons
 * - Shows save cards with Continue and Delete buttons
 * - Load button triggers loadCharacterById and navigates to /game
 * - Delete button shows confirmation, then deletes and refreshes
 * - Continue button triggers loadSaveGame and navigates to /game
 * - Error states display error banners
 * - Uses fetchCharacters and fetchSaves from the store
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { useCharacterStore } from '../../stores/characterStore'
import type { CharacterListItem, SaveMeta } from '../../api/types'
import LoadTab from './LoadTab'

// ---------------------------------------------------------------------------
// Mock react-router-dom's useNavigate
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const sampleCharacters: CharacterListItem[] = [
  {
    id: 'char-1',
    name: 'Kaelen Shadowmere',
    class: 'Fighter',
    level: 1,
    timestamp: '2026-05-15T10:30:00Z',
  },
  {
    id: 'char-2',
    name: 'Lyra Moonshadow',
    class: 'Wizard',
    level: 3,
    timestamp: '2026-05-20T14:00:00Z',
  },
]

const sampleSaves: SaveMeta[] = [
  {
    id: 'save-1',
    name: 'Session 1 – The Forest',
    timestamp: '2026-05-20T18:00:00Z',
    character_name: 'Kaelen Shadowmere',
    turn_count: 12,
  },
  {
    id: 'save-2',
    name: 'Session 2 – The Cave',
    timestamp: '2026-05-21T09:00:00Z',
    character_name: 'Lyra Moonshadow',
    turn_count: 8,
  },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderLoadTab() {
  return render(
    <MemoryRouter>
      <LoadTab />
    </MemoryRouter>,
  )
}

/** Init store with data so fetch resolves immediately to pre-loaded data. */
function setStoreCharacters(chars: CharacterListItem[]) {
  useCharacterStore.getState().setSavedCharacters(chars)
}

function setStoreSaves(saves: SaveMeta[]) {
  useCharacterStore.getState().setSavedGames(saves)
}

function resetStore() {
  useCharacterStore.getState().reset()
}

beforeEach(() => {
  resetStore()
  mockNavigate.mockClear()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LoadTab — data fetching', () => {
  it('shows loading state for characters section on mount', () => {
    // Keep default empty store — fetchCharacters/fetchSaves will be called async
    renderLoadTab()
    expect(screen.getByText(/loading characters/i)).toBeInTheDocument()
  })

  it('shows loading state for saved games section on mount', () => {
    renderLoadTab()
    expect(screen.getByText(/loading saved games/i)).toBeInTheDocument()
  })

  it('fetches characters via store fetchCharacters on mount', async () => {
    const fetchCharacters = vi.spyOn(
      useCharacterStore.getState(),
      'fetchCharacters',
    )
    renderLoadTab()
    await waitFor(() => {
      expect(fetchCharacters).toHaveBeenCalledOnce()
    })
    fetchCharacters.mockRestore()
  })

  it('fetches saves via store fetchSaves on mount', async () => {
    const fetchSaves = vi.spyOn(
      useCharacterStore.getState(),
      'fetchSaves',
    )
    renderLoadTab()
    await waitFor(() => {
      expect(fetchSaves).toHaveBeenCalledOnce()
    })
    fetchSaves.mockRestore()
  })
})

describe('LoadTab — empty states', () => {
  it('shows empty message when no saved characters exist', async () => {
    // Set empty data so loading resolves to empty
    setStoreCharacters([])
    renderLoadTab()
    await waitFor(() => {
      expect(
        screen.getByText(/no saved characters yet/i),
      ).toBeInTheDocument()
    })
  })

  it('shows empty message when no saved games exist', async () => {
    setStoreSaves([])
    renderLoadTab()
    await waitFor(() => {
      expect(screen.getByText(/no saved games yet/i)).toBeInTheDocument()
    })
  })
})

describe('LoadTab — character cards', () => {
  it('renders character names in cards', async () => {
    setStoreCharacters(sampleCharacters)
    renderLoadTab()
    await waitFor(() => {
      expect(screen.getByText('Kaelen Shadowmere')).toBeInTheDocument()
      expect(screen.getByText('Lyra Moonshadow')).toBeInTheDocument()
    })
  })

  it('renders character class and level in card meta', async () => {
    setStoreCharacters(sampleCharacters)
    renderLoadTab()
    await waitFor(() => {
      expect(screen.getByText(/Fighter/i)).toBeInTheDocument()
      expect(screen.getByText(/Level 1/i)).toBeInTheDocument()
      expect(screen.getByText(/Wizard/i)).toBeInTheDocument()
      expect(screen.getByText(/Level 3/i)).toBeInTheDocument()
    })
  })

  it('renders Load and Delete buttons for each character', async () => {
    setStoreCharacters(sampleCharacters)
    renderLoadTab()
    await waitFor(() => {
      const loadButtons = screen.getAllByRole('button', { name: /load/i })
      expect(loadButtons).toHaveLength(2)
      const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
      expect(deleteButtons).toHaveLength(2)
    })
  })
})

describe('LoadTab — character load action', () => {
  it('calls loadCharacterById and navigates to /game on Load click', async () => {
    const user = userEvent.setup()
    setStoreCharacters(sampleCharacters)

    const loadCharacterById = vi.spyOn(
      useCharacterStore.getState(),
      'loadCharacterById',
    )

    renderLoadTab()

    await waitFor(() => {
      expect(screen.getByText('Kaelen Shadowmere')).toBeInTheDocument()
    })

    const loadBtn = screen.getByRole('button', { name: /load kaelen/i })
    await user.click(loadBtn)

    expect(loadCharacterById).toHaveBeenCalledWith('char-1')
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/game')
    })

    loadCharacterById.mockRestore()
  })
})

describe('LoadTab — character delete action', () => {
  it('shows confirm and cancel buttons when Delete is clicked', async () => {
    const user = userEvent.setup()
    setStoreCharacters([sampleCharacters[0]])
    renderLoadTab()

    await waitFor(() => {
      expect(screen.getByText('Kaelen Shadowmere')).toBeInTheDocument()
    })

    const deleteBtn = screen.getByRole('button', { name: /delete kaelen/i })
    await user.click(deleteBtn)

    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /cancel/i }),
    ).toBeInTheDocument()
  })

  it('hides confirm/cancel and shows Load/Delete again on Cancel', async () => {
    const user = userEvent.setup()
    setStoreCharacters([sampleCharacters[0]])
    renderLoadTab()

    await waitFor(() => {
      expect(screen.getByText('Kaelen Shadowmere')).toBeInTheDocument()
    })

    const deleteBtn = screen.getByRole('button', { name: /delete kaelen/i })
    await user.click(deleteBtn)

    // Click Cancel
    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(
      screen.getByRole('button', { name: /load kaelen/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /delete kaelen/i }),
    ).toBeInTheDocument()
  })

  it('calls deleteCharacterById on Confirm', async () => {
    const user = userEvent.setup()
    setStoreCharacters([sampleCharacters[0]])

    const deleteCharacterById = vi
      .spyOn(useCharacterStore.getState(), 'deleteCharacterById')
      .mockImplementation(async () => {})

    const fetchCharacters = vi
      .spyOn(useCharacterStore.getState(), 'fetchCharacters')
      .mockResolvedValue({ ok: false, characters: [] })

    renderLoadTab()

    await waitFor(() => {
      expect(screen.getByText('Kaelen Shadowmere')).toBeInTheDocument()
    })

    const deleteBtn = screen.getByRole('button', { name: /delete kaelen/i })
    await user.click(deleteBtn)

    const confirmBtn = screen.getByRole('button', { name: /confirm/i })
    await user.click(confirmBtn)

    expect(deleteCharacterById).toHaveBeenCalledWith('char-1')

    deleteCharacterById.mockRestore()
    fetchCharacters.mockRestore()
  })
})

describe('LoadTab — save cards', () => {
  it('renders save names in cards', async () => {
    setStoreSaves(sampleSaves)
    renderLoadTab()
    await waitFor(() => {
      expect(
        screen.getByText('Session 1 – The Forest'),
      ).toBeInTheDocument()
      expect(
        screen.getByText('Session 2 – The Cave'),
      ).toBeInTheDocument()
    })
  })

  it('renders save meta (turn count, character name)', async () => {
    setStoreSaves(sampleSaves)
    renderLoadTab()
    await waitFor(() => {
      expect(screen.getByText(/Turn 12/i)).toBeInTheDocument()
      expect(screen.getByText(/Turn 8/i)).toBeInTheDocument()
      expect(screen.getByText(/Kaelen Shadowmere/)).toBeInTheDocument()
      expect(screen.getByText(/Lyra Moonshadow/)).toBeInTheDocument()
    })
  })

  it('renders Continue and Delete buttons for each save', async () => {
    setStoreSaves(sampleSaves)
    renderLoadTab()
    await waitFor(() => {
      const continueButtons = screen.getAllByRole('button', { name: /continue/i })
      expect(continueButtons).toHaveLength(2)
      const deleteButtons = screen.getAllByRole('button', { name: /delete save/i })
      expect(deleteButtons).toHaveLength(2)
    })
  })
})

describe('LoadTab — save continue action', () => {
  it('calls loadSaveGame and navigates to /game on Continue click', async () => {
    const user = userEvent.setup()
    setStoreSaves([sampleSaves[0]])

    const loadSaveGame = vi.spyOn(
      useCharacterStore.getState(),
      'loadSaveGame',
    )

    renderLoadTab()

    await waitFor(() => {
      expect(
        screen.getByText('Session 1 – The Forest'),
      ).toBeInTheDocument()
    })

    const continueBtn = screen.getByRole('button', {
      name: /continue session 1/i,
    })
    await user.click(continueBtn)

    expect(loadSaveGame).toHaveBeenCalledWith('save-1')
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/game')
    })

    loadSaveGame.mockRestore()
  })
})

describe('LoadTab — save delete action', () => {
  it('shows confirm/cancel when Delete is clicked on a save', async () => {
    const user = userEvent.setup()
    setStoreSaves([sampleSaves[0]])
    renderLoadTab()

    await waitFor(() => {
      expect(
        screen.getByText('Session 1 – The Forest'),
      ).toBeInTheDocument()
    })

    const deleteBtn = screen.getByRole('button', {
      name: /delete save session 1/i,
    })
    await user.click(deleteBtn)

    expect(
      screen.getByRole('button', { name: /confirm delete save/i }),
    ).toBeInTheDocument()
  })

  it('hides confirm/cancel and shows Continue/Delete again on Cancel for saves', async () => {
    const user = userEvent.setup()
    setStoreSaves([sampleSaves[0]])
    renderLoadTab()

    await waitFor(() => {
      expect(
        screen.getByText('Session 1 – The Forest'),
      ).toBeInTheDocument()
    })

    const deleteBtn = screen.getByRole('button', {
      name: /delete save session 1/i,
    })
    await user.click(deleteBtn)

    // Click Cancel
    await user.click(
      screen.getByRole('button', { name: /cancel delete save/i }),
    )

    expect(
      screen.getByRole('button', { name: /continue session 1/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /delete save session 1/i }),
    ).toBeInTheDocument()
  })
})

describe('LoadTab — error states', () => {
  it('shows error banner when charError is set', async () => {
    // Manually trigger error state by causing fetchCharacters to throw
    // by making the store's fetchCharacters throw
    const fetchCharacters = vi
      .spyOn(useCharacterStore.getState(), 'fetchCharacters')
      .mockRejectedValue(new Error('Network error'))

    renderLoadTab()
    await waitFor(() => {
      expect(
        screen.getByText(/failed to load saved characters/i),
      ).toBeInTheDocument()
    })

    fetchCharacters.mockRestore()
  })

  it('shows error banner when saves error is set', async () => {
    const fetchSaves = vi
      .spyOn(useCharacterStore.getState(), 'fetchSaves')
      .mockRejectedValue(new Error('Network error'))

    renderLoadTab()
    await waitFor(() => {
      expect(
        screen.getByText(/failed to load saved games/i),
      ).toBeInTheDocument()
    })

    fetchSaves.mockRestore()
  })

  it('shows error banner when character delete fails', async () => {
    const user = userEvent.setup()
    setStoreCharacters([sampleCharacters[0]])

    const deleteCharacterById = vi
      .spyOn(useCharacterStore.getState(), 'deleteCharacterById')
      .mockRejectedValue(new Error('Delete failed'))

    renderLoadTab()

    await waitFor(() => {
      expect(screen.getByText('Kaelen Shadowmere')).toBeInTheDocument()
    })

    const deleteBtn = screen.getByRole('button', { name: /delete kaelen/i })
    await user.click(deleteBtn)

    const confirmBtn = screen.getByRole('button', { name: /confirm/i })
    await user.click(confirmBtn)

    await waitFor(() => {
      expect(
        screen.getByText(/failed to delete character/i),
      ).toBeInTheDocument()
    })

    deleteCharacterById.mockRestore()
  })

  it('shows error banner when save delete fails', async () => {
    const user = userEvent.setup()
    setStoreSaves([sampleSaves[0]])

    const deleteSaveGame = vi
      .spyOn(useCharacterStore.getState(), 'deleteSaveGame')
      .mockRejectedValue(new Error('Delete failed'))

    renderLoadTab()

    await waitFor(() => {
      expect(
        screen.getByText('Session 1 – The Forest'),
      ).toBeInTheDocument()
    })

    const deleteBtn = screen.getByRole('button', {
      name: /delete save session 1/i,
    })
    await user.click(deleteBtn)

    const confirmBtn = screen.getByRole('button', {
      name: /confirm delete save/i,
    })
    await user.click(confirmBtn)

    await waitFor(() => {
      expect(
        screen.getByText(/failed to delete save/i),
      ).toBeInTheDocument()
    })

    deleteSaveGame.mockRestore()
  })
})

describe('LoadTab — accessibility', () => {
  it('has status role on loading indicators', async () => {
    renderLoadTab()
    const statuses = screen.getAllByRole('status')
    expect(statuses.length).toBeGreaterThanOrEqual(1)
  })

  it('has alert role on error banners', async () => {
    const fetchCharacters = vi
      .spyOn(useCharacterStore.getState(), 'fetchCharacters')
      .mockRejectedValue(new Error('fail'))

    renderLoadTab()
    await waitFor(() => {
      const alerts = screen.getAllByRole('alert')
      expect(alerts.length).toBeGreaterThanOrEqual(1)
    })

    fetchCharacters.mockRestore()
  })
})
