/**
 * GameInputArea tests — making sure the input forge works!
 *
 * Covers: rendering, input handling, submit behaviour (with and without
 * onSubmit prop), quick action chips, action buttons, disabled states,
 * and keyboard interactions.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useGameStore } from '../../stores/gameStore'
import GameInputArea from './GameInputArea'

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function setProcessing(value: boolean): void {
  act(() => {
    useGameStore.setState({ processing: value })
  })
}

function setIsActive(value: boolean): void {
  act(() => {
    useGameStore.setState({ isActive: value })
  })
}

/** Reset store to game-relevant defaults. */
function resetGameStore(): void {
  act(() => {
    useGameStore.setState({
      playerInput: '',
      processing: false,
      isActive: true,
    })
  })
}

beforeEach(() => {
  resetGameStore()
})

afterEach(() => {
  resetGameStore()
})

/* ------------------------------------------------------------------ */
/*  Rendering                                                         */
/* ------------------------------------------------------------------ */

describe('GameInputArea — rendering', () => {
  it('renders the input field with placeholder', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')
    expect(input).toBeInTheDocument()
    expect(input).toHaveAttribute('aria-label', 'Player action input')
  })

  it('renders the Act submit button', () => {
    render(<GameInputArea />)
    const btn = screen.getByRole('button', { name: /submit action/i })
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveTextContent('Act')
  })

  it('renders all 6 quick action chips', () => {
    render(<GameInputArea />)
    expect(screen.getByText('Look around')).toBeInTheDocument()
    expect(screen.getByText('Check inventory')).toBeInTheDocument()
    expect(screen.getByText('Talk to NPCs')).toBeInTheDocument()
    expect(screen.getByText('Rest')).toBeInTheDocument()
    expect(screen.getByText('Attack')).toBeInTheDocument()
    expect(screen.getByText('Use magic')).toBeInTheDocument()
  })

  it('renders Save Game, Load Game, and New Game buttons', () => {
    render(<GameInputArea />)
    expect(screen.getByText('Save Game')).toBeInTheDocument()
    expect(screen.getByText('Load Game')).toBeInTheDocument()
    expect(screen.getByText('New Game')).toBeInTheDocument()
  })

  it('renders the region with correct aria-label', () => {
    render(<GameInputArea />)
    expect(
      screen.getByRole('region', { name: /game input area/i }),
    ).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Input behaviour                                                    */
/* ------------------------------------------------------------------ */

describe('GameInputArea — input behaviour', () => {
  it('allows typing into the input field', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')
    fireEvent.change(input, { target: { value: 'Attack the dragon' } })
    expect(input).toHaveValue('Attack the dragon')
  })

  it('Act button is enabled even when input is empty (validation on submit)', () => {
    render(<GameInputArea />)
    const btn = screen.getByRole('button', { name: /submit action/i })
    expect(btn).not.toBeDisabled()
  })

  it('Act button is enabled when input has text', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')
    fireEvent.change(input, { target: { value: 'Hello' } })
    const btn = screen.getByRole('button', { name: /submit action/i })
    expect(btn).not.toBeDisabled()
  })
})

/* ------------------------------------------------------------------ */
/*  Submit behaviour (store fallback)                                  */
/* ------------------------------------------------------------------ */

describe('GameInputArea — submit via store', () => {
  it('sets playerInput and processing in store on submit', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.change(input, { target: { value: 'Look around' } })
    fireEvent.click(screen.getByRole('button', { name: /submit action/i }))

    expect(useGameStore.getState().playerInput).toBe('Look around')
    expect(useGameStore.getState().processing).toBe(true)
  })

  it('clears the input field after submit', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.change(input, { target: { value: 'Attack' } })
    fireEvent.click(screen.getByRole('button', { name: /submit action/i }))

    expect(input).toHaveValue('')
  })

  it('submits on Enter key press', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.change(input, { target: { value: 'Check door' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(useGameStore.getState().playerInput).toBe('Check door')
    expect(useGameStore.getState().processing).toBe(true)
  })

  it('does not submit empty input on Enter', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.keyDown(input, { key: 'Enter' })

    expect(useGameStore.getState().playerInput).toBe('')
    expect(useGameStore.getState().processing).toBe(false)
  })

  it('does not submit when processing is already true', () => {
    setProcessing(true)
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.change(input, { target: { value: 'Run away' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(useGameStore.getState().playerInput).toBe('')
  })
})

/* ------------------------------------------------------------------ */
/*  Submit behaviour (onSubmit prop)                                   */
/* ------------------------------------------------------------------ */

describe('GameInputArea — submit via onSubmit prop', () => {
  it('calls onSubmit with the trimmed input when provided', () => {
    const onSubmit = vi.fn()
    render(<GameInputArea onSubmit={onSubmit} />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.change(input, { target: { value: '  Open chest  ' } })
    fireEvent.click(screen.getByRole('button', { name: /submit action/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith('Open chest')
  })

  it('does not set store values when onSubmit is provided', () => {
    const onSubmit = vi.fn()
    render(<GameInputArea onSubmit={onSubmit} />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.change(input, { target: { value: 'Hello' } })
    fireEvent.click(screen.getByRole('button', { name: /submit action/i }))

    expect(useGameStore.getState().playerInput).toBe('')
    expect(useGameStore.getState().processing).toBe(false)
  })

  it('clears input after onSubmit call', () => {
    const onSubmit = vi.fn()
    render(<GameInputArea onSubmit={onSubmit} />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.change(input, { target: { value: 'Test' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(onSubmit).toHaveBeenCalledWith('Test')
    expect(input).toHaveValue('')
  })
})

/* ------------------------------------------------------------------ */
/*  Quick actions                                                      */
/* ------------------------------------------------------------------ */

describe('GameInputArea — quick actions', () => {
  it('fills input field when a quick action chip is clicked', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.click(screen.getByText('Look around'))

    expect(input).toHaveValue('Look around')
  })

  it('does not submit when clicking a quick action', () => {
    render(<GameInputArea />)

    fireEvent.click(screen.getByText('Attack'))

    expect(useGameStore.getState().playerInput).toBe('')
    expect(useGameStore.getState().processing).toBe(false)
  })

  it('replaces existing input text when quick action is clicked', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.change(input, { target: { value: 'Old text' } })
    fireEvent.click(screen.getByText('Use magic'))

    expect(input).toHaveValue('Use magic')
  })

  it('quick actions are disabled when processing is true', () => {
    setProcessing(true)
    render(<GameInputArea />)

    const chips = screen.getAllByRole('button', { name: /quick action/i })
    chips.forEach((chip) => {
      expect(chip).toBeDisabled()
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Action buttons                                                     */
/* ------------------------------------------------------------------ */

describe('GameInputArea — action buttons', () => {
  it('calls onSave when Save Game is clicked', () => {
    const onSave = vi.fn()
    render(<GameInputArea onSave={onSave} />)

    fireEvent.click(screen.getByText('Save Game'))

    expect(onSave).toHaveBeenCalledTimes(1)
  })

  it('calls onLoad when Load Game is clicked', () => {
    const onLoad = vi.fn()
    render(<GameInputArea onLoad={onLoad} />)

    fireEvent.click(screen.getByText('Load Game'))

    expect(onLoad).toHaveBeenCalledTimes(1)
  })

  it('calls onNewGame when New Game is clicked', () => {
    const onNewGame = vi.fn()
    render(<GameInputArea onNewGame={onNewGame} />)

    fireEvent.click(screen.getByText('New Game'))

    expect(onNewGame).toHaveBeenCalledTimes(1)
  })

  it('Save Game is disabled when isActive is false', () => {
    setIsActive(false)
    render(<GameInputArea />)

    const saveBtn = screen.getByText('Save Game').closest('button')
    expect(saveBtn).toBeDisabled()
  })

  it('Load Game and New Game are not disabled even when inactive', () => {
    setIsActive(false)
    render(<GameInputArea />)

    expect(screen.getByText('Load Game').closest('button')).not.toBeDisabled()
    expect(screen.getByText('New Game').closest('button')).not.toBeDisabled()
  })
})

/* ------------------------------------------------------------------ */
/*  Disabled states                                                    */
/* ------------------------------------------------------------------ */

describe('GameInputArea — disabled states', () => {
  it('disables input when isActive is false', () => {
    setIsActive(false)
    render(<GameInputArea />)

    expect(
      screen.getByPlaceholderText('What do you do?'),
    ).toBeDisabled()
  })

  it('disables input when processing is true', () => {
    setProcessing(true)
    render(<GameInputArea />)

    expect(
      screen.getByPlaceholderText('What do you do?'),
    ).toBeDisabled()
  })

  it('disables Act button when processing is true', () => {
    setProcessing(true)
    render(<GameInputArea />)

    expect(
      screen.getByRole('button', { name: /submit action/i }),
    ).toBeDisabled()
  })

  it('disables Act button when isActive is false', () => {
    setIsActive(false)
    render(<GameInputArea />)

    expect(
      screen.getByRole('button', { name: /submit action/i }),
    ).toBeDisabled()
  })

  it('Act button is enabled when input has text and game is active', () => {
    render(<GameInputArea />)
    const input = screen.getByPlaceholderText('What do you do?')

    fireEvent.change(input, { target: { value: 'Go' } })

    expect(
      screen.getByRole('button', { name: /submit action/i }),
    ).not.toBeDisabled()
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('GameInputArea — accessibility', () => {
  it('input has aria-label for screen readers', () => {
    render(<GameInputArea />)
    expect(
      screen.getByLabelText('Player action input'),
    ).toBeInTheDocument()
  })

  it('Act button has aria-label for screen readers', () => {
    render(<GameInputArea />)
    expect(
      screen.getByLabelText('Submit action'),
    ).toBeInTheDocument()
  })

  it('quick action chips have role button and aria-labels', () => {
    render(<GameInputArea />)
    const lookAround = screen.getByLabelText('Quick action: Look around')
    expect(lookAround).toHaveAttribute('role', 'button')
    expect(lookAround).toHaveAttribute('tabindex', '0')
  })

  it('action buttons have aria-labels', () => {
    render(<GameInputArea />)
    expect(screen.getByLabelText('Save game')).toBeInTheDocument()
    expect(screen.getByLabelText('Load game')).toBeInTheDocument()
    expect(screen.getByLabelText('New game')).toBeInTheDocument()
  })

  it('quick actions group has aria-label', () => {
    render(<GameInputArea />)
    expect(
      screen.getByRole('group', { name: /quick actions/i }),
    ).toBeInTheDocument()
  })
})
