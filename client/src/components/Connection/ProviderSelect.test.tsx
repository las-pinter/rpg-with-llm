/**
 * ProviderSelect tests — white-knuckled goblin scrutiny.
 *
 * Checks: rendering, store interaction, API key visibility toggle,
 * disabled state for local providers, and null API key edge cases.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useConnectionStore } from '../../stores/connectionStore'
import ProviderSelect from './ProviderSelect'

/** Reset the connection store before each test. */
function resetStore() {
  useConnectionStore.getState().reset()
}

beforeEach(() => {
  resetStore()
})

/* ------------------------------------------------------------------ */
/*  Provider select                                                    */
/* ------------------------------------------------------------------ */

describe('ProviderSelect — provider <select>', () => {
  it('renders a select element labelled "Provider"', () => {
    render(<ProviderSelect />)
    expect(screen.getByLabelText('Provider')).toBeInTheDocument()
  })

  it('renders all 5 provider options', () => {
    render(<ProviderSelect />)
    const select = screen.getByLabelText('Provider') as HTMLSelectElement
    expect(select.options).toHaveLength(5)
  })

  it('includes ollama, groq, openrouter, unsloth, llama.cpp options', () => {
    render(<ProviderSelect />)
    const select = screen.getByLabelText('Provider') as HTMLSelectElement
    const labels = Array.from(select.options).map((o) => o.label)
    expect(labels).toEqual([
      'Ollama',
      'Groq',
      'OpenRouter',
      'Unsloth',
      'llama.cpp',
    ])
  })

  it('uses the providerType from the store as the initial value', () => {
    // Default is ollama
    render(<ProviderSelect />)
    const select = screen.getByLabelText('Provider') as HTMLSelectElement
    expect(select.value).toBe('ollama')
  })

  it('updates the store when a different provider is selected', async () => {
    const user = userEvent.setup()
    render(<ProviderSelect />)

    await user.selectOptions(screen.getByLabelText('Provider'), 'groq')

    expect(useConnectionStore.getState().providerType).toBe('groq')
  })

  it('reflects a store value that was changed externally', () => {
    useConnectionStore.getState().setProviderType('openrouter')
    render(<ProviderSelect />)

    const select = screen.getByLabelText('Provider') as HTMLSelectElement
    expect(select.value).toBe('openrouter')
  })
})

/* ------------------------------------------------------------------ */
/*  Base URL input                                                     */
/* ------------------------------------------------------------------ */

describe('ProviderSelect — base URL <input>', () => {
  it('renders a text input labelled "Base URL"', () => {
    render(<ProviderSelect />)
    expect(screen.getByLabelText('Base URL')).toBeInTheDocument()
  })

  it('has the default placeholder', () => {
    render(<ProviderSelect />)
    expect(screen.getByLabelText('Base URL')).toHaveAttribute(
      'placeholder',
      'http://localhost:11434',
    )
  })

  it('displays the baseUrl from the store', () => {
    render(<ProviderSelect />)
    expect(screen.getByLabelText('Base URL')).toHaveValue(
      'http://localhost:11434',
    )
  })

  it('reflects an externally mutated store value', () => {
    useConnectionStore.getState().setBaseUrl('http://my-custom-host:8080')
    render(<ProviderSelect />)

    expect(screen.getByLabelText('Base URL')).toHaveValue(
      'http://my-custom-host:8080',
    )
  })

  it('updates the store when the user types a new URL', async () => {
    const user = userEvent.setup()
    render(<ProviderSelect />)

    const input = screen.getByLabelText('Base URL')
    await user.clear(input)
    await user.type(input, 'https://api.groq.com')

    expect(useConnectionStore.getState().baseUrl).toBe(
      'https://api.groq.com',
    )
  })
})

/* ------------------------------------------------------------------ */
/*  API key input — common behaviour                                   */
/* ------------------------------------------------------------------ */

describe('ProviderSelect — API key <input>', () => {
  it('renders an input labelled "API Key"', () => {
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toBeInTheDocument()
  })

  it('displays empty string when store apiKey is null', () => {
    // Default state has apiKey: null
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toHaveValue('')
  })

  it('displays the store apiKey when it is set to a non-null value', () => {
    useConnectionStore.getState().setApiKey('sk-test-123')
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toHaveValue('sk-test-123')
  })

  it('updates the store when the user types an API key', async () => {
    const user = userEvent.setup()
    // Switch to a key-requiring provider so the input is enabled
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)

    const input = screen.getByLabelText('API Key')
    await user.type(input, 'sk-my-secret-key')

    expect(useConnectionStore.getState().apiKey).toBe('sk-my-secret-key')
  })

  it('sets the store apiKey to null when the input is cleared', async () => {
    const user = userEvent.setup()
    // Switch to a key-requiring provider so the input is enabled
    useConnectionStore.getState().setProviderType('groq')
    // Pre-fill a key
    useConnectionStore.getState().setApiKey('sk-old-key')
    render(<ProviderSelect />)

    const input = screen.getByLabelText('API Key')
    await user.clear(input)

    expect(useConnectionStore.getState().apiKey).toBeNull()
  })
})

/* ------------------------------------------------------------------ */
/*  API key visibility toggle                                          */
/* ------------------------------------------------------------------ */

describe('ProviderSelect — API key show/hide toggle', () => {
  it('renders a toggle button when the provider requires an API key', () => {
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)
    expect(
      screen.getByRole('button', { name: /show api key/i }),
    ).toBeInTheDocument()
  })

  it('does not render a toggle button for ollama', () => {
    render(<ProviderSelect />) // default is ollama
    expect(
      screen.queryByRole('button', { name: /show api key/i }),
    ).not.toBeInTheDocument()
  })

  it('does not render a toggle button for llama.cpp', () => {
    useConnectionStore.getState().setProviderType('llama.cpp')
    render(<ProviderSelect />)
    expect(
      screen.queryByRole('button', { name: /show api key/i }),
    ).not.toBeInTheDocument()
  })

  it('input type is "password" when hidden (default)', () => {
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toHaveAttribute('type', 'password')
  })

  it('input type is "text" after toggling visibility', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)

    await user.click(screen.getByRole('button', { name: /show api key/i }))

    expect(screen.getByLabelText('API Key')).toHaveAttribute('type', 'text')
  })

  it('toggle button label changes to "Hide API key" after click', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)

    await user.click(screen.getByRole('button', { name: /show api key/i }))

    expect(
      screen.getByRole('button', { name: /hide api key/i }),
    ).toBeInTheDocument()
  })

  it('toggles back to "Show API key" on second click', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)

    await user.click(screen.getByRole('button', { name: /show api key/i }))
    await user.click(screen.getByRole('button', { name: /hide api key/i }))

    expect(
      screen.getByRole('button', { name: /show api key/i }),
    ).toBeInTheDocument()
  })

  it('toggle button has an accessible aria-label', () => {
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)
    const btn = screen.getByRole('button', { name: /show api key/i })
    expect(btn).toHaveAttribute('aria-label', 'Show API key')
  })
})

/* ------------------------------------------------------------------ */
/*  API key disabled state — local providers                           */
/* ------------------------------------------------------------------ */

describe('ProviderSelect — API key disabled for local providers', () => {
  it('disables the API key input for ollama (default)', () => {
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toBeDisabled()
  })

  it('disables the API key input for llama.cpp', () => {
    useConnectionStore.getState().setProviderType('llama.cpp')
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toBeDisabled()
  })

  it('enables the API key input for groq', () => {
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toBeEnabled()
  })

  it('enables the API key input for openrouter', () => {
    useConnectionStore.getState().setProviderType('openrouter')
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toBeEnabled()
  })

  it('enables the API key input for unsloth', () => {
    useConnectionStore.getState().setProviderType('unsloth')
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toBeEnabled()
  })

  it('toggles from enabled to disabled when switching from groq to ollama', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)

    expect(screen.getByLabelText('API Key')).toBeEnabled()

    await user.selectOptions(screen.getByLabelText('Provider'), 'ollama')

    expect(screen.getByLabelText('API Key')).toBeDisabled()
  })

  it('toggles from disabled to enabled when switching from ollama to groq', async () => {
    const user = userEvent.setup()
    render(<ProviderSelect />) // default ollama

    expect(screen.getByLabelText('API Key')).toBeDisabled()

    await user.selectOptions(screen.getByLabelText('Provider'), 'groq')

    expect(screen.getByLabelText('API Key')).toBeEnabled()
  })

  it('placeholder says "Not required for this provider" for ollama', () => {
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toHaveAttribute(
      'placeholder',
      'Not required for this provider',
    )
  })

  it('placeholder says "Enter API key..." for groq', () => {
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toHaveAttribute(
      'placeholder',
      'Enter API key...',
    )
  })
})

/* ------------------------------------------------------------------ */
/*  Hint text                                                          */
/* ------------------------------------------------------------------ */

describe('ProviderSelect — hint text', () => {
  it('shows a hint for ollama', () => {
    render(<ProviderSelect />)
    expect(
      screen.getByText('Ollama runs locally — no API key needed.'),
    ).toBeInTheDocument()
  })

  it('shows a hint for llama.cpp', () => {
    useConnectionStore.getState().setProviderType('llama.cpp')
    render(<ProviderSelect />)
    expect(
      screen.getByText('llama.cpp runs locally — no API key needed.'),
    ).toBeInTheDocument()
  })

  it('does not show a hint for groq', () => {
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)
    expect(
      screen.queryByText(/no API key needed/i),
    ).not.toBeInTheDocument()
  })

  it('does not show a hint for openrouter', () => {
    useConnectionStore.getState().setProviderType('openrouter')
    render(<ProviderSelect />)
    expect(
      screen.queryByText(/no API key needed/i),
    ).not.toBeInTheDocument()
  })

  it('does not show a hint for unsloth', () => {
    useConnectionStore.getState().setProviderType('unsloth')
    render(<ProviderSelect />)
    expect(
      screen.queryByText(/no API key needed/i),
    ).not.toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('ProviderSelect — accessibility', () => {
  it('associates the provider label with the select via htmlFor', () => {
    render(<ProviderSelect />)
    const select = screen.getByLabelText('Provider')
    expect(select.tagName).toBe('SELECT')
  })

  it('associates the base URL label with the input via htmlFor', () => {
    render(<ProviderSelect />)
    const input = screen.getByLabelText('Base URL')
    expect(input.tagName).toBe('INPUT')
  })

  it('associates the API key label with the input via htmlFor', () => {
    render(<ProviderSelect />)
    const input = screen.getByLabelText('API Key')
    expect(input.tagName).toBe('INPUT')
  })

  it('toggle button has a title attribute', () => {
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)
    const btn = screen.getByRole('button', { name: /show api key/i })
    expect(btn).toHaveAttribute('title', 'Show API key')
  })

  it('the API key input uses id "api-key" matching its label', () => {
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toHaveAttribute('id', 'api-key')
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases                                                         */
/* ------------------------------------------------------------------ */

describe('ProviderSelect — edge cases', () => {
  it('handles empty apiKey in store (null -> empty string display)', () => {
    useConnectionStore.getState().setApiKey(null)
    render(<ProviderSelect />)
    expect(screen.getByLabelText('API Key')).toHaveValue('')
  })

  it('removes the toggle button when switching from groq to ollama', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)

    // Toggle should be visible for groq
    expect(
      screen.getByRole('button', { name: /show api key/i }),
    ).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Provider'), 'ollama')

    // Toggle should be gone for ollama
    expect(
      screen.queryByRole('button', { name: /show api key/i }),
    ).not.toBeInTheDocument()
  })

  it('shows the toggle button when switching from ollama to groq', async () => {
    const user = userEvent.setup()
    render(<ProviderSelect />) // default ollama — no toggle

    expect(
      screen.queryByRole('button', { name: /show api key/i }),
    ).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Provider'), 'groq')

    expect(
      screen.getByRole('button', { name: /show api key/i }),
    ).toBeInTheDocument()
  })

  it('hides the hint when switching from ollama to groq', async () => {
    const user = userEvent.setup()
    render(<ProviderSelect />)

    expect(
      screen.getByText(/no API key needed/i),
    ).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Provider'), 'groq')

    expect(
      screen.queryByText(/no API key needed/i),
    ).not.toBeInTheDocument()
  })

  it('shows the hint when switching from groq to ollama', async () => {
    const user = userEvent.setup()
    useConnectionStore.getState().setProviderType('groq')
    render(<ProviderSelect />)

    expect(
      screen.queryByText(/no API key needed/i),
    ).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Provider'), 'ollama')

    expect(
      screen.getByText(/no API key needed/i),
    ).toBeInTheDocument()
  })
})
