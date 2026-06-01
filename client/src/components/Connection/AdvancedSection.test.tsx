/**
 * AdvancedSection tests — collapsible settings panel scrutiny.
 *
 * Covers: default collapsed state, expand/collapse toggle, DM settings
 * inputs and store updates, NPC toggle enable/disable, summarizer toggle
 * enable/disable, and number input parsing edge cases.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, within, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useConnectionStore } from '../../stores/connectionStore'
import AdvancedSection from './AdvancedSection'

/** Reset the connection store to defaults before each test. */
function resetStore() {
  useConnectionStore.getState().reset()
}

beforeEach(() => {
  resetStore()
})

/* ------------------------------------------------------------------ */
/*  Scoping helpers                                                    */
/* ------------------------------------------------------------------ */

/** Return the subsection wrapper that contains the given heading text. */
function getSubsection(name: string): HTMLElement {
  return screen.getByRole('heading', { name }).closest('div')!
}

const DM_NAME = 'Dungeon Master'
const NPC_NAME = 'NPC Agents'
const SUMMARIZER_NAME = 'Story Summarizer'

/* ------------------------------------------------------------------ */
/*  Default collapsed state                                            */
/* ------------------------------------------------------------------ */

describe('AdvancedSection — collapsed by default', () => {
  it('renders the "Advanced Settings" header button', () => {
    render(<AdvancedSection />)
    expect(
      screen.getByRole('button', { name: /advanced settings/i }),
    ).toBeInTheDocument()
  })

  it('has aria-expanded set to false', () => {
    render(<AdvancedSection />)
    expect(
      screen.getByRole('button', { name: /advanced settings/i }),
    ).toHaveAttribute('aria-expanded', 'false')
  })

  it('does NOT show the DM settings heading', () => {
    render(<AdvancedSection />)
    expect(screen.queryByRole('heading', { name: DM_NAME }))
      .not.toBeInTheDocument()
  })

  it('does NOT show the NPC settings heading', () => {
    render(<AdvancedSection />)
    expect(screen.queryByRole('heading', { name: NPC_NAME }))
      .not.toBeInTheDocument()
  })

  it('does NOT show the summarizer settings heading', () => {
    render(<AdvancedSection />)
    expect(screen.queryByRole('heading', { name: SUMMARIZER_NAME }))
      .not.toBeInTheDocument()
  })

  it('chevron is visible with aria-hidden', () => {
    render(<AdvancedSection />)
    const chevron = screen.getByText('▶')
    expect(chevron).toHaveAttribute('aria-hidden', 'true')
  })
})

/* ------------------------------------------------------------------ */
/*  Expand / collapse                                                  */
/* ------------------------------------------------------------------ */

describe('AdvancedSection — expand/collapse', () => {
  it('shows all three subsection headings when expanded', async () => {
    const user = userEvent.setup()
    render(<AdvancedSection />)

    await user.click(
      screen.getByRole('button', { name: /advanced settings/i }),
    )

    expect(
      screen.getByRole('heading', { name: DM_NAME }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: NPC_NAME }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: SUMMARIZER_NAME }),
    ).toBeInTheDocument()
  })

  it('hides subsection headings when collapsed after expansion', async () => {
    const user = userEvent.setup()
    render(<AdvancedSection />)

    const header = screen.getByRole('button', {
      name: /advanced settings/i,
    })
    await user.click(header)
    await user.click(header)

    expect(
      screen.queryByRole('heading', { name: DM_NAME }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: NPC_NAME }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: SUMMARIZER_NAME }),
    ).not.toBeInTheDocument()
  })

  it('toggles aria-expanded from false to true', async () => {
    const user = userEvent.setup()
    render(<AdvancedSection />)

    const header = screen.getByRole('button', {
      name: /advanced settings/i,
    })
    await user.click(header)

    expect(header).toHaveAttribute('aria-expanded', 'true')
  })

  it('toggles aria-expanded from true to false', async () => {
    const user = userEvent.setup()
    render(<AdvancedSection />)

    const header = screen.getByRole('button', {
      name: /advanced settings/i,
    })
    await user.click(header)
    await user.click(header)

    expect(header).toHaveAttribute('aria-expanded', 'false')
  })

  it('has aria-controls pointing to the content region', () => {
    render(<AdvancedSection />)
    expect(
      screen.getByRole('button', { name: /advanced settings/i }),
    ).toHaveAttribute('aria-controls', 'advanced-settings-content')
  })
})

/* ------------------------------------------------------------------ */
/*  DM settings — inputs and store interaction                         */
/* ------------------------------------------------------------------ */

describe('AdvancedSection — DM settings', () => {
  beforeEach(async () => {
    const user = userEvent.setup()
    render(<AdvancedSection />)
    await user.click(
      screen.getByRole('button', { name: /advanced settings/i }),
    )
  })

  it('renders DM max tokens input with default 16000', () => {
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Max Tokens')
    expect(input).toHaveValue(16000)
  })

  it('renders DM temperature input with default 0.8', () => {
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Temperature')
    expect(input).toHaveValue(0.8)
  })

  it('renders DM timeout input with default 120', () => {
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Timeout (s)')
    expect(input).toHaveValue(120)
  })

  it('DM max tokens has min=1', () => {
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Max Tokens')
    expect(input).toHaveAttribute('min', '1')
  })

  it('DM temperature has min=0, max=2, step=0.1', () => {
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Temperature')
    expect(input).toHaveAttribute('min', '0')
    expect(input).toHaveAttribute('max', '2')
    expect(input).toHaveAttribute('step', '0.1')
  })

  it('DM timeout has min=1', () => {
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Timeout (s)')
    expect(input).toHaveAttribute('min', '1')
  })

  it('updates dm_max_tokens in the store when changed', async () => {
    const user = userEvent.setup()
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Max Tokens')

    await user.tripleClick(input)
    await user.keyboard('8000')

    expect(useConnectionStore.getState().dm_max_tokens).toBe(8000)
  })

  it('updates dm_temperature in the store when changed', async () => {
    const user = userEvent.setup()
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Temperature')

    await user.tripleClick(input)
    await user.keyboard('0.5')

    expect(useConnectionStore.getState().dm_temperature).toBe(0.5)
  })

  it('updates dm_timeout in the store when changed', async () => {
    const user = userEvent.setup()
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Timeout (s)')

    await user.tripleClick(input)
    await user.keyboard('60')

    expect(useConnectionStore.getState().dm_timeout).toBe(60)
  })

  it('reflects an externally mutated dm_max_tokens in the store', async () => {
    act(() => {
      useConnectionStore.getState().setSettings({ dm_max_tokens: 32000 })
    })
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Max Tokens')
    expect(input).toHaveValue(32000)
  })

  it('reflects an externally mutated dm_temperature in the store', async () => {
    act(() => {
      useConnectionStore.getState().setSettings({ dm_temperature: 1.5 })
    })
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Temperature')
    expect(input).toHaveValue(1.5)
  })
})

/* ------------------------------------------------------------------ */
/*  NPC settings — toggle and store interaction                        */
/* ------------------------------------------------------------------ */

describe('AdvancedSection — NPC toggle', () => {
  beforeEach(async () => {
    const user = userEvent.setup()
    render(<AdvancedSection />)
    await user.click(
      screen.getByRole('button', { name: /advanced settings/i }),
    )
  })

  it('renders NPC enabled checkbox checked by default', () => {
    const checkbox = screen.getByLabelText(
      'Enable NPC Agents',
    ) as HTMLInputElement
    expect(checkbox).toBeChecked()
  })

  it('shows NPC max tokens input with default 1024 when enabled', () => {
    const section = getSubsection(NPC_NAME)
    const input = within(section).getByLabelText('Max Tokens')
    expect(input).toHaveValue(1024)
  })

  it('shows NPC temperature input with default 0.7 when enabled', () => {
    const section = getSubsection(NPC_NAME)
    const input = within(section).getByLabelText('Temperature')
    expect(input).toHaveValue(0.7)
  })

  it('shows NPC timeout input with default 60 when enabled', () => {
    const section = getSubsection(NPC_NAME)
    const input = within(section).getByLabelText('Timeout (s)')
    expect(input).toHaveValue(60)
  })

  it('hides NPC inputs when checkbox is unchecked', async () => {
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Enable NPC Agents'))

    const section = getSubsection(NPC_NAME)
    expect(
      within(section).queryByLabelText('Max Tokens'),
    ).not.toBeInTheDocument()
    expect(
      within(section).queryByLabelText('Temperature'),
    ).not.toBeInTheDocument()
    expect(
      within(section).queryByLabelText('Timeout (s)'),
    ).not.toBeInTheDocument()
  })

  it('shows NPC inputs again when re-enabled after disabling', async () => {
    const user = userEvent.setup()
    const checkbox = screen.getByLabelText('Enable NPC Agents')

    // Disable
    await user.click(checkbox)
    // Re-enable
    await user.click(checkbox)

    const section = getSubsection(NPC_NAME)
    expect(
      within(section).getByLabelText('Max Tokens'),
    ).toBeInTheDocument()
    expect(
      within(section).getByLabelText('Temperature'),
    ).toBeInTheDocument()
    expect(
      within(section).getByLabelText('Timeout (s)'),
    ).toBeInTheDocument()
  })

  it('sets npcEnabled to false in the store when unchecked', async () => {
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Enable NPC Agents'))

    expect(useConnectionStore.getState().npcEnabled).toBe(false)
  })

  it('sets npcEnabled to true in the store when re-checked', async () => {
    const user = userEvent.setup()
    const checkbox = screen.getByLabelText('Enable NPC Agents')

    await user.click(checkbox)
    await user.click(checkbox)

    expect(useConnectionStore.getState().npcEnabled).toBe(true)
  })

  it('preserves NPC store values when toggled off and back on', async () => {
    const user = userEvent.setup()

    // Set custom NPC values
    act(() => {
      useConnectionStore.getState().setSettings({
        npc_max_tokens: 2048,
        npc_temperature: 0.9,
        npc_timeout: 120,
      })
    })

    // Toggle off and on
    await user.click(screen.getByLabelText('Enable NPC Agents'))
    await user.click(screen.getByLabelText('Enable NPC Agents'))

    // Values should still be the custom ones
    expect(useConnectionStore.getState().npc_max_tokens).toBe(2048)
    expect(useConnectionStore.getState().npc_temperature).toBe(0.9)
    expect(useConnectionStore.getState().npc_timeout).toBe(120)
  })

  it('NPC temperature has min=0, max=2, step=0.1', () => {
    const section = getSubsection(NPC_NAME)
    const input = within(section).getByLabelText('Temperature')
    expect(input).toHaveAttribute('min', '0')
    expect(input).toHaveAttribute('max', '2')
    expect(input).toHaveAttribute('step', '0.1')
  })
})

/* ------------------------------------------------------------------ */
/*  Summarizer settings — toggle and store interaction                 */
/* ------------------------------------------------------------------ */

describe('AdvancedSection — summarizer toggle', () => {
  beforeEach(async () => {
    const user = userEvent.setup()
    render(<AdvancedSection />)
    await user.click(
      screen.getByRole('button', { name: /advanced settings/i }),
    )
  })

  it('renders summarizer enabled checkbox checked by default', () => {
    const checkbox = screen.getByLabelText(
      'Enable Story Summarizer',
    ) as HTMLInputElement
    expect(checkbox).toBeChecked()
  })

  it('shows summarizer max tokens input with default 16000 when enabled', () => {
    const section = getSubsection(SUMMARIZER_NAME)
    const input = within(section).getByLabelText('Max Tokens')
    expect(input).toHaveValue(16000)
  })

  it('shows summarizer temperature input with default 0.7 when enabled', () => {
    const section = getSubsection(SUMMARIZER_NAME)
    const input = within(section).getByLabelText('Temperature')
    expect(input).toHaveValue(0.7)
  })

  it('shows summarizer timeout input with default 120 when enabled', () => {
    const section = getSubsection(SUMMARIZER_NAME)
    const input = within(section).getByLabelText('Timeout (s)')
    expect(input).toHaveValue(120)
  })

  it('hides summarizer inputs when checkbox is unchecked', async () => {
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Enable Story Summarizer'))

    const section = getSubsection(SUMMARIZER_NAME)
    expect(
      within(section).queryByLabelText('Max Tokens'),
    ).not.toBeInTheDocument()
    expect(
      within(section).queryByLabelText('Temperature'),
    ).not.toBeInTheDocument()
    expect(
      within(section).queryByLabelText('Timeout (s)'),
    ).not.toBeInTheDocument()
  })

  it('shows summarizer inputs again when re-enabled after disabling', async () => {
    const user = userEvent.setup()
    const checkbox = screen.getByLabelText('Enable Story Summarizer')

    await user.click(checkbox)
    await user.click(checkbox)

    const section = getSubsection(SUMMARIZER_NAME)
    expect(
      within(section).getByLabelText('Max Tokens'),
    ).toBeInTheDocument()
    expect(
      within(section).getByLabelText('Temperature'),
    ).toBeInTheDocument()
    expect(
      within(section).getByLabelText('Timeout (s)'),
    ).toBeInTheDocument()
  })

  it('sets summarizerEnabled to false in the store when unchecked', async () => {
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Enable Story Summarizer'))

    expect(useConnectionStore.getState().summarizerEnabled).toBe(false)
  })

  it('sets summarizerEnabled to true in the store when re-checked', async () => {
    const user = userEvent.setup()
    const checkbox = screen.getByLabelText('Enable Story Summarizer')

    await user.click(checkbox)
    await user.click(checkbox)

    expect(useConnectionStore.getState().summarizerEnabled).toBe(true)
  })

  it('preserves summarizer store values when toggled off and back on', async () => {
    const user = userEvent.setup()

    act(() => {
      useConnectionStore.getState().setSettings({
        summarizer_max_tokens: 8000,
        summarizer_temperature: 0.5,
        summarizer_timeout: 60,
      })
    })

    await user.click(screen.getByLabelText('Enable Story Summarizer'))
    await user.click(screen.getByLabelText('Enable Story Summarizer'))

    expect(useConnectionStore.getState().summarizer_max_tokens).toBe(8000)
    expect(useConnectionStore.getState().summarizer_temperature).toBe(0.5)
    expect(useConnectionStore.getState().summarizer_timeout).toBe(60)
  })

  it('summarizer temperature has min=0, max=2, step=0.1', () => {
    const section = getSubsection(SUMMARIZER_NAME)
    const input = within(section).getByLabelText('Temperature')
    expect(input).toHaveAttribute('min', '0')
    expect(input).toHaveAttribute('max', '2')
    expect(input).toHaveAttribute('step', '0.1')
  })
})

/* ------------------------------------------------------------------ */
/*  Number input parsing — edge cases                                  */
/* ------------------------------------------------------------------ */

describe('AdvancedSection — number input parsing', () => {
  beforeEach(async () => {
    const user = userEvent.setup()
    render(<AdvancedSection />)
    await user.click(
      screen.getByRole('button', { name: /advanced settings/i }),
    )
  })

  it('parses integer values from max tokens input', async () => {
    const user = userEvent.setup()
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Max Tokens')

    await user.tripleClick(input)
    await user.keyboard('42')

    expect(useConnectionStore.getState().dm_max_tokens).toBe(42)
  })

  it('parses float values from temperature input', async () => {
    const user = userEvent.setup()
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Temperature')

    await user.tripleClick(input)
    await user.keyboard('1.25')

    expect(useConnectionStore.getState().dm_temperature).toBe(1.25)
  })

  it('does NOT update store when max tokens input is empty', async () => {
    const user = userEvent.setup()
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Max Tokens')

    await user.clear(input)

    // Store should still be the default
    expect(useConnectionStore.getState().dm_max_tokens).toBe(16000)
  })

  it('does NOT update store when temperature input contains only a decimal point', async () => {
    const user = userEvent.setup()
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Temperature')

    await user.clear(input)
    await user.type(input, '.')

    expect(useConnectionStore.getState().dm_temperature).toBe(0.8)
  })

  it('does NOT update store when timeout input is cleared', async () => {
    const user = userEvent.setup()
    const section = getSubsection(DM_NAME)
    const input = within(section).getByLabelText('Timeout (s)')

    await user.clear(input)

    expect(useConnectionStore.getState().dm_timeout).toBe(120)
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('AdvancedSection — accessibility', () => {
  beforeEach(async () => {
    const user = userEvent.setup()
    render(<AdvancedSection />)
    await user.click(
      screen.getByRole('button', { name: /advanced settings/i }),
    )
  })

  it('associates DM max tokens label with input via htmlFor/id', () => {
    const section = getSubsection(DM_NAME)
    const label = within(section).getByText('Max Tokens')
    expect(label).toHaveAttribute('for', 'dm-max-tokens')
    const input = within(section).getByLabelText('Max Tokens')
    expect(input).toHaveAttribute('id', 'dm-max-tokens')
  })

  it('associates DM temperature label with input via htmlFor/id', () => {
    const section = getSubsection(DM_NAME)
    const label = within(section).getByText('Temperature')
    expect(label).toHaveAttribute('for', 'dm-temperature')
    const input = within(section).getByLabelText('Temperature')
    expect(input).toHaveAttribute('id', 'dm-temperature')
  })

  it('associates DM timeout label with input via htmlFor/id', () => {
    const section = getSubsection(DM_NAME)
    const label = within(section).getByText('Timeout (s)')
    expect(label).toHaveAttribute('for', 'dm-timeout')
    const input = within(section).getByLabelText('Timeout (s)')
    expect(input).toHaveAttribute('id', 'dm-timeout')
  })

  it('associates NPC toggle label with checkbox via htmlFor/id', () => {
    const label = screen.getByText('Enable NPC Agents')
    expect(label).toHaveAttribute('for', 'npc-enabled')
    const checkbox = screen.getByLabelText('Enable NPC Agents')
    expect(checkbox).toHaveAttribute('id', 'npc-enabled')
  })

  it('associates summarizer toggle label with checkbox via htmlFor/id', () => {
    const label = screen.getByText('Enable Story Summarizer')
    expect(label).toHaveAttribute('for', 'summarizer-enabled')
    const checkbox = screen.getByLabelText('Enable Story Summarizer')
    expect(checkbox).toHaveAttribute('id', 'summarizer-enabled')
  })

  it('uses heading role for subsection titles', () => {
    expect(
      screen.getByRole('heading', { name: DM_NAME }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: NPC_NAME }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: SUMMARIZER_NAME }),
    ).toBeInTheDocument()
  })
})
