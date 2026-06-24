/**
 * WhisperPanel tests — Grubnik kicks the tires on the DM consultation panel.
 *
 * Covers: render/hide based on consultationOpen, close button, input field,
 * empty state, history display, submit flow with API call, and accessibility.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { useGameStore } from '../../stores/gameStore'
import { WhisperPanel } from './WhisperPanel'

// Mock the API endpoint — the component imports consult from here
vi.mock('../../api/endpoints', () => ({
  consult: vi.fn(),
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Reset consultation state to defaults. */
function resetConsultationState(): void {
  act(() => {
    useGameStore.setState({
      consultationOpen: false,
      consultationHistory: [],
      consultationStreaming: false,
    })
  })
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  resetConsultationState()
})

afterEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WhisperPanel', () => {
  // ---------------------------------------------------------------
  // Open / close
  // ---------------------------------------------------------------

  describe('open / close', () => {
    it('renders the panel when consultationOpen is true', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      expect(
        screen.getByText('Whisper — DM Consultation'),
      ).toBeInTheDocument()
    })

    it('does NOT render when consultationOpen is false', () => {
      // Already false from beforeEach
      const { container } = render(<WhisperPanel />)
      expect(container.innerHTML).toBe('')
    })

    it('close button closes the panel', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      fireEvent.click(screen.getByLabelText('Close consultation'))
      expect(useGameStore.getState().consultationOpen).toBe(false)
    })
  })

  // ---------------------------------------------------------------
  // Empty state
  // ---------------------------------------------------------------

  describe('empty state', () => {
    it('shows empty state text when history is empty', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      expect(
        screen.getByText('No consultations yet. Ask a question!'),
      ).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // History display
  // ---------------------------------------------------------------

  describe('consultation history', () => {
    it('displays consultation history items', () => {
      act(() => {
        useGameStore.setState({
          consultationOpen: true,
          consultationHistory: [
            { role: 'user', content: 'Hello?' },
            { role: 'assistant', content: 'Hi there!' },
          ],
        })
      })
      render(<WhisperPanel />)
      expect(screen.getByText('Hello?')).toBeInTheDocument()
      expect(screen.getByText('Hi there!')).toBeInTheDocument()
    })

    it('shows user and DM labels for messages', () => {
      act(() => {
        useGameStore.setState({
          consultationOpen: true,
          consultationHistory: [
            { role: 'user', content: 'Test question' },
            { role: 'assistant', content: 'Test answer' },
          ],
        })
      })
      render(<WhisperPanel />)
      expect(screen.getByText('You')).toBeInTheDocument()
      expect(screen.getByText('DM')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Input field
  // ---------------------------------------------------------------

  describe('input field', () => {
    it('exists and is focusable', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      const input = screen.getByLabelText('Consultation question')
      expect(input).toBeInTheDocument()
      // Focus the input
      input.focus()
      expect(document.activeElement).toBe(input)
    })

    it('can be typed into', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      const input = screen.getByLabelText('Consultation question')
      fireEvent.change(input, { target: { value: 'Is this thing on?' } })
      expect((input as HTMLInputElement).value).toBe('Is this thing on?')
    })

    it('has the correct placeholder', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      expect(
        screen.getByPlaceholderText('Ask the DM a question...'),
      ).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // Submit flow
  // ---------------------------------------------------------------

  describe('submit flow', () => {
    it('submit button calls the API and updates history', async () => {
      const { consult } = await import('../../api/endpoints')
      ;(consult as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        answer: 'Yes, it works!',
      })

      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)

      const input = screen.getByLabelText('Consultation question')
      fireEvent.change(input, { target: { value: 'Does it work?' } })
      fireEvent.click(screen.getByLabelText('Ask question'))

      // Wait for the async operation to complete
      await waitFor(() => {
        const history = useGameStore.getState().consultationHistory
        expect(history.length).toBe(2)
        expect(history[0].content).toBe('Does it work?')
        expect(history[1].content).toBe('Yes, it works!')
      })
    })

    it('shows error message in history when API returns not ok', async () => {
      const { consult } = await import('../../api/endpoints')
      ;(consult as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: false,
        answer: '',
      })

      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)

      const input = screen.getByLabelText('Consultation question')
      fireEvent.change(input, { target: { value: 'Are you there?' } })
      fireEvent.click(screen.getByLabelText('Ask question'))

      await waitFor(() => {
        const history = useGameStore.getState().consultationHistory
        expect(history.length).toBe(2)
        expect(history[1].content).toBe(
          'The DM is momentarily distracted. Please try again.',
        )
      })
    })

    it('does not submit when input is empty', async () => {
      const { consult } = await import('../../api/endpoints')
      const consultMock = consult as ReturnType<typeof vi.fn>

      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)

      fireEvent.click(screen.getByLabelText('Ask question'))

      // consult should not have been called
      expect(consultMock).not.toHaveBeenCalled()
    })

    it('does not submit when already streaming', async () => {
      const { consult } = await import('../../api/endpoints')
      const consultMock = consult as ReturnType<typeof vi.fn>

      act(() => {
        useGameStore.setState({
          consultationOpen: true,
          consultationStreaming: true,
        })
      })
      render(<WhisperPanel />)

      const input = screen.getByLabelText('Consultation question')
      fireEvent.change(input, { target: { value: 'Hello?' } })
      fireEvent.click(screen.getByLabelText('Ask question'))

      expect(consultMock).not.toHaveBeenCalled()
    })
  })

  // ---------------------------------------------------------------
  // Keyboard interaction
  // ---------------------------------------------------------------

  describe('keyboard interaction', () => {
    it('submits on Enter key press', async () => {
      const { consult } = await import('../../api/endpoints')
      ;(consult as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        answer: 'Enter works!',
      })

      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)

      const input = screen.getByLabelText('Consultation question')
      fireEvent.change(input, { target: { value: 'Enter key test' } })
      fireEvent.keyDown(input, { key: 'Enter' })

      await waitFor(() => {
        const history = useGameStore.getState().consultationHistory
        expect(history.length).toBe(2)
        expect(history[0].content).toBe('Enter key test')
        expect(history[1].content).toBe('Enter works!')
      })
    })
  })

  // ---------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------

  describe('accessibility', () => {
    it('panel has correct ARIA attributes', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      const dialog = screen.getByRole('dialog')
      expect(dialog).toHaveAttribute('aria-modal', 'true')
      expect(dialog).toHaveAttribute('aria-labelledby', 'whisper-title')
    })

    it('close button has accessible label', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      expect(
        screen.getByLabelText('Close consultation'),
      ).toBeInTheDocument()
    })

    it('input has accessible label', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      expect(
        screen.getByLabelText('Consultation question'),
      ).toBeInTheDocument()
    })

    it('submit button has accessible label', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      render(<WhisperPanel />)
      expect(
        screen.getByLabelText('Ask question'),
      ).toBeInTheDocument()
    })

    it('chat log has aria-live="polite"', () => {
      act(() => {
        useGameStore.setState({ consultationOpen: true })
      })
      const { container } = render(<WhisperPanel />)
      const chatLog = container.querySelector('[aria-live="polite"]')
      expect(chatLog).toBeInTheDocument()
    })
  })
})
