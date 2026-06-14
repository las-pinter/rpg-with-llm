/**
 * ModelSelector tests — no model left unturned.
 *
 * Covers: initial render, fetch button validation/loading/success/error,
 * select population, manual input sync, empty results, network failure,
 * and all store interaction paths.
 */

import { vi, describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock the API module before any imports that use it
vi.mock('../../api/endpoints', () => ({
  listModels: vi.fn(),
}))

import { listModels } from '../../api/endpoints'
import { useConnectionStore } from '../../stores/connectionStore'
import ModelSelector from './ModelSelector'

/** Reset the connection store to defaults before each test. */
function resetStore() {
  useConnectionStore.getState().reset()
}

beforeEach(() => {
  resetStore()
  vi.clearAllMocks()
})

/* ------------------------------------------------------------------ */
/*  Initial render state                                               */
/* ------------------------------------------------------------------ */

describe('ModelSelector — initial render', () => {
  it('renders a "Fetch Models" button', () => {
    render(<ModelSelector />)
    expect(
      screen.getByRole('button', { name: 'Fetch Models' }),
    ).toBeInTheDocument()
  })

  it('renders a disabled model select with "No models loaded"', () => {
    render(<ModelSelector />)
    const select = screen.getByLabelText('Model') as HTMLSelectElement
    expect(select).toBeDisabled()
    expect(select).toHaveValue('')
    expect(
      screen.getByText('No models loaded'),
    ).toBeInTheDocument()
  })

  it('renders a text input labelled "Or type a model name"', () => {
    render(<ModelSelector />)
    expect(
      screen.getByLabelText('Or type a model name'),
    ).toBeInTheDocument()
  })

  it('text input shows the current model from the store', () => {
    render(<ModelSelector />)
    const input = screen.getByLabelText(
      'Or type a model name',
    ) as HTMLInputElement
    expect(input).toHaveValue('llama3.2')
  })

  it('does NOT show an error alert initially', () => {
    render(<ModelSelector />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does NOT show "No models found." on initial render', () => {
    render(<ModelSelector />)
    expect(screen.queryByText('No models found.')).not.toBeInTheDocument()
  })

  it('text input has the correct placeholder', () => {
    render(<ModelSelector />)
    expect(screen.getByLabelText('Or type a model name')).toHaveAttribute(
      'placeholder',
      'e.g. llama3.2',
    )
  })
})

/* ------------------------------------------------------------------ */
/*  Fetch button — validation                                          */
/* ------------------------------------------------------------------ */

describe('ModelSelector — fetch validation', () => {
  it('shows an error when baseUrl is empty and fetch is clicked', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('')
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Base URL is required to fetch models',
    )
  })

  it('stores the validation error in the store', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('')
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    expect(useConnectionStore.getState().error).toBe(
      'Base URL is required to fetch models',
    )
  })

  it('does NOT call listModels when baseUrl is empty', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('')
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    expect(listModels).not.toHaveBeenCalled()
  })
})

/* ------------------------------------------------------------------ */
/*  Fetch button — loading state                                       */
/* ------------------------------------------------------------------ */

describe('ModelSelector — loading state', () => {
  it('shows "Fetching…" while loading', () => {
    useConnectionStore.getState().setLoading(true)
    render(<ModelSelector />)

    expect(
      screen.getByRole('button', { name: 'Fetching…' }),
    ).toBeInTheDocument()
  })

  it('disables the fetch button while loading', () => {
    useConnectionStore.getState().setLoading(true)
    render(<ModelSelector />)

    expect(screen.getByRole('button', { name: 'Fetching…' })).toBeDisabled()
  })
})

/* ------------------------------------------------------------------ */
/*  Fetch button — successful response                                 */
/* ------------------------------------------------------------------ */

describe('ModelSelector — successful fetch with models', () => {
  it('populates the select dropdown with model IDs', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [
        { id: 'llama3.2', name: 'Llama 3.2' },
        { id: 'mistral', name: 'Mistral' },
      ],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      const select = screen.getByLabelText('Model') as HTMLSelectElement
      expect(select).toBeEnabled()
      expect(select.options).toHaveLength(2)
      expect(select.options[0]).toHaveValue('llama3.2')
      expect(select.options[1]).toHaveValue('mistral')
    })
  })

  it('updates the store models array', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [{ id: 'gpt-4', name: 'GPT-4' }],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().models).toEqual(['gpt-4'])
    })
  })

  it('clears any previous error on successful fetch', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setError('old error')
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [{ id: 'llama3.2', name: 'Llama 3.2' }],
    })
    render(<ModelSelector />)

    expect(screen.getByRole('alert')).toHaveTextContent('old error')

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })

  it('re-enables the fetch button after successful fetch', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [{ id: 'llama3.2', name: 'Llama 3.2' }],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Fetch Models' }),
      ).toBeEnabled()
    })
  })

  it('sets loading to false after successful fetch', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [{ id: 'llama3.2', name: 'Llama 3.2' }],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().loading).toBe(false)
    })
  })

  it('calls listModels with the correct parameters', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('http://my-host:8080')
    useConnectionStore.getState().setModel('test-model')
    useConnectionStore.getState().setApiKey('sk-test')
    useConnectionStore.getState().setProviderType('groq')
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [{ id: 'test-model', name: 'Test' }],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(listModels).toHaveBeenCalledWith({
        base_url: 'http://my-host:8080',
        model: 'test-model',
        api_key: 'sk-test',
        provider_type: 'groq',
      })
    })
  })

  it('excludes apiKey from request when it is null', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('http://localhost:11434')
    useConnectionStore.getState().setApiKey(null)
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [{ id: 'llama3.2', name: 'Llama 3.2' }],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      const callParams = vi.mocked(listModels).mock.calls[0][0]
      expect(callParams).not.toHaveProperty('api_key')
    })
  })

  it('excludes providerType from request when it is empty string', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setBaseUrl('http://localhost:11434')
    useConnectionStore.getState().setProviderType('')
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [{ id: 'llama3.2', name: 'Llama 3.2' }],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      const callParams = vi.mocked(listModels).mock.calls[0][0]
      expect(callParams).not.toHaveProperty('provider_type')
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Fetch button — empty response                                      */
/* ------------------------------------------------------------------ */

describe('ModelSelector — successful fetch with no models', () => {
  it('shows "No models found." when API returns empty list', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.getByText('No models found.')).toBeInTheDocument()
    })
  })

  it('keeps the select disabled with "No models loaded" when empty', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      const select = screen.getByLabelText('Model') as HTMLSelectElement
      expect(select).toBeDisabled()
      expect(select).toHaveValue('')
      expect(screen.getByText('No models loaded')).toBeInTheDocument()
    })
  })

  it('sets store models to empty array when response has no models', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().models).toEqual([])
    })
  })

  it('hides "No models found." when loading after a previous empty fetch', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))
    await waitFor(() => {
      expect(screen.getByText('No models found.')).toBeInTheDocument()
    })

    // Trigger loading state to hide the empty result message
    act(() => {
      useConnectionStore.getState().setLoading(true)
    })

    expect(screen.queryByText('No models found.')).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Fetch button — API error                                           */
/* ------------------------------------------------------------------ */

describe('ModelSelector — API error response', () => {
  it('shows error when API returns ok: false', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: false,
      models: [],
      error: 'Invalid API key',
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid API key')
    })
  })

  it('shows a default error message when API returns ok: false with no error text', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: false,
      models: [],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Failed to fetch models',
      )
    })
  })

  it('does NOT populate models on API error', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: false,
      models: [],
      error: 'Server error',
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().models).toEqual([])
    })
  })

  it('does NOT show "No models found." after API error (fetchedOnce is false)', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockResolvedValue({
      ok: false,
      models: [],
      error: 'Server error',
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    expect(screen.queryByText('No models found.')).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Fetch button — network error                                       */
/* ------------------------------------------------------------------ */

describe('ModelSelector — network error', () => {
  it('shows error message when listModels throws', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockRejectedValue(new Error('Network failure'))
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Network failure')
    })
  })

  it('shows generic error when thrown value is not an Error', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockRejectedValue('raw string error')
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'An unexpected error occurred',
      )
    })
  })

  it('stores the network error in the store', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockRejectedValue(new Error('Connection refused'))
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().error).toBe('Connection refused')
    })
  })

  it('resets loading to false after network error', async () => {
    const user = userEvent.setup()
    vi.mocked(listModels).mockRejectedValue(new Error('Timeout'))
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(useConnectionStore.getState().loading).toBe(false)
    })
  })
})

/* ------------------------------------------------------------------ */
/*  Model select — interaction                                         */
/* ------------------------------------------------------------------ */

describe('ModelSelector — select interaction', () => {
  it('updates the store model when an option is selected', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setModels(['llama3.2', 'mistral'])
    render(<ModelSelector />)

    await user.selectOptions(screen.getByLabelText('Model'), 'mistral')

    expect(useConnectionStore.getState().model).toBe('mistral')
  })

  it('select reflects the current model from the store', () => {
    useConnectionStore.getState().setModels(['llama3.2', 'gpt-4', 'mistral'])
    useConnectionStore.getState().setModel('gpt-4')
    render(<ModelSelector />)

    const select = screen.getByLabelText('Model') as HTMLSelectElement
    expect(select).toHaveValue('gpt-4')
  })

  it('displays all model options passed from the store', () => {
    useConnectionStore.getState().setModels(['a', 'b', 'c', 'd'])
    render(<ModelSelector />)

    const select = screen.getByLabelText('Model') as HTMLSelectElement
    expect(select.options).toHaveLength(4)
    const labels = Array.from(select.options).map((o) => o.value)
    expect(labels).toEqual(['a', 'b', 'c', 'd'])
  })
})

/* ------------------------------------------------------------------ */
/*  Model input — interaction                                          */
/* ------------------------------------------------------------------ */

describe('ModelSelector — manual input interaction', () => {
  it('updates the store model when user types in the input', async () => {
    const user = userEvent.setup()
    render(<ModelSelector />)

    const input = screen.getByLabelText('Or type a model name')
    await user.clear(input)
    await user.type(input, 'custom-model-42')

    expect(useConnectionStore.getState().model).toBe('custom-model-42')
  })

  it('reflects an externally changed store model', () => {
    useConnectionStore.getState().setModel('gpt-4-turbo')
    render(<ModelSelector />)

    const input = screen.getByLabelText(
      'Or type a model name',
    ) as HTMLInputElement
    expect(input).toHaveValue('gpt-4-turbo')
  })

  it('both select and input stay in sync when model changes externally', () => {
    useConnectionStore.getState().setModels(['llama3.2', 'gpt-4', 'mistral'])
    useConnectionStore.getState().setModel('mistral')
    render(<ModelSelector />)

    const select = screen.getByLabelText('Model') as HTMLSelectElement
    const input = screen.getByLabelText(
      'Or type a model name',
    ) as HTMLInputElement

    expect(select).toHaveValue('mistral')
    expect(input).toHaveValue('mistral')
  })

  it('typing a custom value updates store and input even when select has no matching option', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setModels(['llama3.2', 'gpt-4'])
    render(<ModelSelector />)

    const input = screen.getByLabelText('Or type a model name')
    await user.clear(input)
    await user.type(input, 'custom-model')

    // The input shows the custom value
    expect(input).toHaveValue('custom-model')
    // The store is updated
    expect(useConnectionStore.getState().model).toBe('custom-model')
    // The select can't display the custom value (no matching <option>)
    // but its controlled value prop is driven by the store
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('ModelSelector — accessibility', () => {
  it('associates the model label with the select via htmlFor', () => {
    render(<ModelSelector />)
    const select = screen.getByLabelText('Model')
    expect(select.tagName).toBe('SELECT')
    expect(select).toHaveAttribute('id', 'model-select')
  })

  it('associates the manual input label with the input via htmlFor', () => {
    render(<ModelSelector />)
    const input = screen.getByLabelText('Or type a model name')
    expect(input.tagName).toBe('INPUT')
    expect(input).toHaveAttribute('id', 'model-input')
  })

  it('error message uses role="alert" for screen readers', () => {
    useConnectionStore.getState().setError('Something broke')
    render(<ModelSelector />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases                                                         */
/* ------------------------------------------------------------------ */

describe('ModelSelector — edge cases', () => {
  it('handles fetch when apiKey is null (local provider)', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setApiKey(null)
    useConnectionStore.getState().setProviderType('ollama')
    vi.mocked(listModels).mockResolvedValue({
      ok: true,
      models: [{ id: 'llama3.2', name: 'Llama 3.2' }],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.getByLabelText('Model')).toBeEnabled()
    })
    expect(listModels).toHaveBeenCalled()
    // api_key should not be in the params
    const params = vi.mocked(listModels).mock.calls[0][0]
    expect(params).not.toHaveProperty('api_key')
  })

  it('preserves previously loaded models when error occurs on refetch', async () => {
    const user = userEvent.setup()
    // First successful fetch
    vi.mocked(listModels).mockResolvedValueOnce({
      ok: true,
      models: [{ id: 'llama3.2', name: 'Llama 3.2' }],
    })
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Model')).toBeEnabled()
    })

    // Second fetch — fails
    vi.mocked(listModels).mockRejectedValueOnce(new Error('Server down'))
    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Server down')
    })

    // Previously loaded models should still be there
    expect(useConnectionStore.getState().models).toEqual(['llama3.2'])
    expect(screen.getByLabelText('Model')).toBeEnabled()
  })

  it('shows error when response.ok is true but models field is missing', async () => {
    const user = userEvent.setup()
    // TypeScript would catch this, but runtime could still happen
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(listModels).mockResolvedValue({ ok: true } as any)
    render(<ModelSelector />)

    await user.click(screen.getByRole('button', { name: 'Fetch Models' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Failed to fetch models',
      )
    })
  })
})
