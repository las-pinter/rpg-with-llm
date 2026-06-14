/**
 * ConnectionStatus tests — four states: idle, loading, success, error.
 *
 * Checks that the dot colour class, status text, and latency display are
 * all driven correctly from the connection store values.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { act } from 'react'
import { useConnectionStore } from '../../stores/connectionStore'
import ConnectionStatus from './ConnectionStatus'
import styles from './ConnectionStatus.module.css'


/** Reset the connection store before each test. */
function resetStore() {
  useConnectionStore.getState().reset()
}

beforeEach(() => {
  resetStore()
})

/* ------------------------------------------------------------------ */
/*  Idle state                                                         */
/* ------------------------------------------------------------------ */

describe('ConnectionStatus — idle state', () => {
  it('renders "Not tested" text when checking is false and healthOk is null', () => {
    render(<ConnectionStatus />)
    expect(screen.getByText('Not tested')).toBeInTheDocument()
  })

  it('renders the idle dot with the idle class', () => {
    const { container } = render(<ConnectionStatus />)
    const dot = container.querySelector('span:first-child')
    expect(dot).toHaveClass(styles.dotIdle)
  })

  it('does not show latency when idle', () => {
    render(<ConnectionStatus />)
    expect(screen.queryByText(/ms$/)).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Loading state                                                      */
/* ------------------------------------------------------------------ */

describe('ConnectionStatus — loading state', () => {
  it('renders "Testing connection…" when checking is true', () => {
    useConnectionStore.getState().setChecking(true)
    render(<ConnectionStatus />)
    expect(screen.getByText('Testing connection…')).toBeInTheDocument()
  })

  it('renders the loading dot with the loading class', () => {
    useConnectionStore.getState().setChecking(true)
    const { container } = render(<ConnectionStatus />)
    const dot = container.querySelector('span:first-child')
    expect(dot).toHaveClass(styles.dotLoading)
  })

  it('takes priority over healthOk even when healthOk is set', () => {
    // Simulate an in-flight check that previously succeeded
    useConnectionStore.getState().setHealthResult(true, 42, null)
    // Then a new check starts
    useConnectionStore.getState().setChecking(true)
    render(<ConnectionStatus />)
    expect(screen.getByText('Testing connection…')).toBeInTheDocument()
    expect(screen.queryByText('Connected')).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Success state                                                      */
/* ------------------------------------------------------------------ */

describe('ConnectionStatus — success state', () => {
  it('renders "Connected" when healthOk is true', () => {
    useConnectionStore.getState().setHealthResult(true, 45, null)
    render(<ConnectionStatus />)
    expect(screen.getByText('Connected')).toBeInTheDocument()
  })

  it('renders the success dot with the success class', () => {
    useConnectionStore.getState().setHealthResult(true, 45, null)
    const { container } = render(<ConnectionStatus />)
    const dot = container.querySelector('span:first-child')
    expect(dot).toHaveClass(styles.dotSuccess)
  })

  it('shows latency in ms when latencyMs is provided', () => {
    useConnectionStore.getState().setHealthResult(true, 127, null)
    render(<ConnectionStatus />)
    expect(screen.getByText('127ms')).toBeInTheDocument()
  })

  it('shows latency 0ms for zero latency', () => {
    useConnectionStore.getState().setHealthResult(true, 0, null)
    render(<ConnectionStatus />)
    expect(screen.getByText('0ms')).toBeInTheDocument()
  })

  it('does not show latency when latencyMs is null', () => {
    useConnectionStore.getState().setHealthResult(true, null, null)
    render(<ConnectionStatus />)
    expect(screen.queryByText(/ms$/)).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Error state                                                        */
/* ------------------------------------------------------------------ */

describe('ConnectionStatus — error state', () => {
  it('renders the error message when healthOk is false and healthError is set', () => {
    useConnectionStore.getState().setHealthResult(false, null, 'Connection refused')
    render(<ConnectionStatus />)
    expect(screen.getByText('Connection refused')).toBeInTheDocument()
  })

  it('renders the error dot with the error class', () => {
    useConnectionStore.getState().setHealthResult(false, null, 'Timeout')
    const { container } = render(<ConnectionStatus />)
    const dot = container.querySelector('span:first-child')
    expect(dot).toHaveClass(styles.dotError)
  })

  it('renders "Connection failed" fallback when healthError is null', () => {
    useConnectionStore.getState().setHealthResult(false, null, null)
    render(<ConnectionStatus />)
    expect(screen.getByText('Connection failed')).toBeInTheDocument()
  })

  it('does not show latency when in error state', () => {
    useConnectionStore.getState().setHealthResult(false, null, 'Bad gateway')
    render(<ConnectionStatus />)
    expect(screen.queryByText(/ms$/)).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('ConnectionStatus — accessibility', () => {
  it('has role="status" for live region announcements', () => {
    render(<ConnectionStatus />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('marks the dot as aria-hidden', () => {
    const { container } = render(<ConnectionStatus />)
    const dot = container.querySelector('span:first-child')
    expect(dot).toHaveAttribute('aria-hidden', 'true')
  })
})

/* ------------------------------------------------------------------ */
/*  State priority — loading wins over error                            */
/* ------------------------------------------------------------------ */

describe('ConnectionStatus — priority: loading over error', () => {
  it('shows loading when checking is true even if healthOk is false', () => {
    // Set a failed health result first…
    useConnectionStore.getState().setHealthResult(false, null, 'Server down')
    // …then a new check starts (e.g. retry button)
    useConnectionStore.getState().setChecking(true)
    render(<ConnectionStatus />)
    expect(screen.getByText('Testing connection…')).toBeInTheDocument()
    expect(screen.queryByText('Server down')).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases                                                          */
/* ------------------------------------------------------------------ */

describe('ConnectionStatus — edge cases', () => {
  it('renders empty status text when healthError is empty string', () => {
    useConnectionStore.getState().setHealthResult(false, null, '')
    const { container } = render(<ConnectionStatus />)
    const textEl = container.querySelector('[class*="text"]')
    expect(textEl).toBeInTheDocument()
    expect(textEl?.textContent).toBe('')
  })
})

/* ------------------------------------------------------------------ */
/*  State transitions (integration with store)                          */
/* ------------------------------------------------------------------ */

describe('ConnectionStatus — state transitions', () => {
  it('moves through idle → loading → success on rerender', () => {
    // Step 1: idle
    const { rerender } = render(<ConnectionStatus />)
    expect(screen.getByText('Not tested')).toBeInTheDocument()

    // Step 2: loading
    act(() => useConnectionStore.getState().setChecking(true))
    rerender(<ConnectionStatus />)
    expect(screen.getByText('Testing connection…')).toBeInTheDocument()

    // Step 3: success with latency
    act(() => useConnectionStore.getState().setHealthResult(true, 33, null))
    rerender(<ConnectionStatus />)
    expect(screen.getByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('33ms')).toBeInTheDocument()
  })

  it('moves through idle → loading → error on rerender', () => {
    // Step 1: idle
    const { rerender } = render(<ConnectionStatus />)
    expect(screen.getByText('Not tested')).toBeInTheDocument()

    // Step 2: loading
    act(() => useConnectionStore.getState().setChecking(true))
    rerender(<ConnectionStatus />)
    expect(screen.getByText('Testing connection…')).toBeInTheDocument()

    // Step 3: error
    act(() => useConnectionStore.getState().setHealthResult(false, null, 'Timeout'))
    rerender(<ConnectionStatus />)
    expect(screen.getByText('Timeout')).toBeInTheDocument()
    expect(screen.queryByText(/ms$/)).not.toBeInTheDocument()
  })
})
