/**
 * ConnectionPage tests — verify assembly of all child components and
 * navigation behavior.
 *
 * Acceptance criteria:
 * - Renders all child components
 * - Start Adventure is disabled initially (connectionTested === false)
 * - Start Adventure enables after connectionTested === true
 * - Start Adventure navigates to /character
 * - Back button navigates to /
 * - useSettings hook is called
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { useConnectionStore } from '../stores/connectionStore'
import ConnectionPage from './ConnectionPage'

/* ------------------------------------------------------------------ */
/*  Helpers                                                             */
/* ------------------------------------------------------------------ */

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <ConnectionPage />
    </MemoryRouter>,
  )
}

function resetStore() {
  useConnectionStore.getState().reset()
}

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="current-location">{location.pathname}</div>
}

function renderPageForNav() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <ConnectionPage />
      <LocationDisplay />
    </MemoryRouter>,
  )
}

/* ------------------------------------------------------------------ */
/*  Mock useSettings                                                    */
/* ------------------------------------------------------------------ */

const mockUseSettings = vi.fn()

vi.mock('../hooks/useSettings', () => ({
  useSettings: () => mockUseSettings(),
}))

/* ------------------------------------------------------------------ */
/*  Setup / Teardown                                                    */
/* ------------------------------------------------------------------ */

beforeEach(() => {
  resetStore()
  mockUseSettings.mockReturnValue({ loading: false, error: null })
})

/* ------------------------------------------------------------------ */
/*  Page renders                                                        */
/* ------------------------------------------------------------------ */

describe('ConnectionPage — rendering', () => {
  it('renders the page title', () => {
    renderPage()
    expect(
      screen.getByRole('heading', { name: /connection setup/i }),
    ).toBeInTheDocument()
  })

  it('renders the subtitle text', () => {
    renderPage()
    expect(
      screen.getByText(/configure your llm provider to begin the adventure/i),
    ).toBeInTheDocument()
  })

  it('renders ProviderSelect (the provider select input)', () => {
    renderPage()
    expect(screen.getByLabelText('Provider')).toBeInTheDocument()
  })

  it('renders ModelSelector (the fetch models button)', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /fetch models/i }),
    ).toBeInTheDocument()
  })

  it('renders TestConnectionButton (the test connection button)', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /test connection/i }),
    ).toBeInTheDocument()
  })

  it('renders AdvancedSection (the advanced settings header)', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /advanced settings/i }),
    ).toBeInTheDocument()
  })

  it('renders the Back button', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /back/i }),
    ).toBeInTheDocument()
  })

  it('renders the Start Adventure button', () => {
    renderPage()
    expect(
      screen.getByRole('button', { name: /start adventure/i }),
    ).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  useSettings integration                                             */
/* ------------------------------------------------------------------ */

describe('ConnectionPage — useSettings', () => {
  it('calls useSettings hook on render', () => {
    mockUseSettings.mockClear()
    renderPage()
    expect(mockUseSettings).toHaveBeenCalledOnce()
  })
})

/* ------------------------------------------------------------------ */
/*  Start Adventure button state                                       */
/* ------------------------------------------------------------------ */

describe('ConnectionPage — Start Adventure button', () => {
  it('is disabled when connectionTested is false (default)', () => {
    renderPage()
    expect(screen.getByRole('button', { name: /start adventure/i })).toBeDisabled()
  })

  it('is enabled when connectionTested is true', () => {
    useConnectionStore.getState().setConnectionTested(true)
    renderPage()
    expect(
      screen.getByRole('button', { name: /start adventure/i }),
    ).toBeEnabled()
  })

  it('navigates to /character when clicked and enabled', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setConnectionTested(true)
    renderPageForNav()

    await user.click(screen.getByRole('button', { name: /start adventure/i }))

    expect(screen.getByTestId('current-location')).toHaveTextContent('/character')
  })

  it('does not navigate when disabled', async () => {
    const user = userEvent.setup()
    renderPageForNav()

    await user.click(screen.getByRole('button', { name: /start adventure/i }))

    expect(screen.getByTestId('current-location')).toHaveTextContent('/')
  })

  it('is disabled when connectionTested is null (edge case)', () => {
    useConnectionStore.setState({ connectionTested: null as unknown as boolean })
    renderPage()
    expect(screen.getByRole('button', { name: /start adventure/i })).toBeDisabled()
  })

  it('is disabled when error is present and connectionTested is false', () => {
    mockUseSettings.mockReturnValue({ loading: false, error: 'fail' })
    renderPage()
    expect(screen.getByRole('button', { name: /start adventure/i })).toBeDisabled()
  })
})

/* ------------------------------------------------------------------ */
/*  Back button                                                        */
/* ------------------------------------------------------------------ */

describe('ConnectionPage — Back button', () => {
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

    expect(screen.getByTestId('current-location')).toHaveTextContent('/')
  })
})

/* ------------------------------------------------------------------ */
/*  Loading state                                                      */
/* ------------------------------------------------------------------ */

describe('ConnectionPage — loading state', () => {
  it('shows a loading indicator when useSettings is loading', () => {
    mockUseSettings.mockReturnValue({ loading: true, error: null })
    renderPage()
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('does not show an error banner when loading', () => {
    mockUseSettings.mockReturnValue({ loading: true, error: 'fail' })
    renderPage()
    expect(screen.getByText('Loading…')).toBeInTheDocument()
    expect(screen.queryByText(/could not load/i)).not.toBeInTheDocument()
  })

  it('renders all form controls while loading is true', () => {
    mockUseSettings.mockReturnValue({ loading: true, error: null })
    renderPage()
    expect(screen.getByLabelText('Provider')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /fetch models/i }),
    ).toBeInTheDocument()
  })

  it('does not show loading banner when not loading', () => {
    mockUseSettings.mockReturnValue({ loading: false, error: null })
    renderPage()
    expect(screen.queryByText('Loading…')).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Error state                                                        */
/* ------------------------------------------------------------------ */

describe('ConnectionPage — error state', () => {
  it('shows an error banner when useSettings has an error', () => {
    mockUseSettings.mockReturnValue({ loading: false, error: 'Something broke' })
    renderPage()
    expect(
      screen.getByText(/could not load saved settings/i),
    ).toBeInTheDocument()
  })

  it('still renders all form controls when there is an error', () => {
    mockUseSettings.mockReturnValue({ loading: false, error: 'Something broke' })
    renderPage()
    expect(screen.getByLabelText('Provider')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /fetch models/i }),
    ).toBeInTheDocument()
  })

  it('does not show error banner when there is no error', () => {
    mockUseSettings.mockReturnValue({ loading: false, error: null })
    renderPage()
    expect(
      screen.queryByText(/could not load saved settings/i),
    ).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('ConnectionPage — accessibility', () => {
  it('has status role on loading banner', () => {
    mockUseSettings.mockReturnValue({ loading: true, error: null })
    renderPage()
    const statuses = screen.getAllByRole('status')
    const loadingStatus = statuses.find((s) =>
      s.textContent?.includes('Loading…'),
    )
    expect(loadingStatus).toBeInTheDocument()
  })

  it('has alert role on error banner', () => {
    mockUseSettings.mockReturnValue({ loading: false, error: 'fail' })
    renderPage()
    expect(screen.getByRole('alert')).toHaveTextContent(
      /could not load saved settings/i,
    )
  })
})
