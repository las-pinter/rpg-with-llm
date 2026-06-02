/**
 * ClassSelector tests — paranoid goblin scrutiny of class selection dropdown.
 *
 * Covers: rendering class options, store interaction via setSelectedClass
 * and applyClassDefaults, null/empty rules edge cases, accessibility, and
 * externally driven store value reflection.
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useCharacterStore } from '../../stores/characterStore'
import type { CharacterRules } from '../../api/types'
import ClassSelector from './ClassSelector'

/** A realistic rules object with multiple classes. */
const sampleRules: CharacterRules = {
  valid_classes: ['Fighter', 'Wizard', 'Rogue', 'Cleric'],
  standard_abilities: ['str', 'dex', 'con', 'int', 'wis', 'cha'],
  class_templates: {
    Fighter: { abilities: { str: 15, dex: 13, con: 14, int: 10, wis: 12, cha: 8 } },
    Wizard: { abilities: { str: 8, dex: 12, con: 13, int: 15, wis: 14, cha: 10 } },
    Rogue: { abilities: { str: 10, dex: 15, con: 12, int: 13, wis: 8, cha: 14 } },
    Cleric: { abilities: { str: 12, dex: 8, con: 13, int: 10, wis: 15, cha: 14 } },
  },
  point_buy: {
    costs: { '8': 0, '9': 1, '10': 2, '11': 3, '12': 4, '13': 5, '14': 7, '15': 9 },
    max_points: 27,
    min_score: 8,
    max_score: 15,
  },
  assisted_creation_questions: ['Q1', 'Q2', 'Q3'],
}

/** Reset store, set up rules+defaults, and mock requestAnimationFrame to run synchronously. */
function setupStore() {
  useCharacterStore.getState().reset()
  useCharacterStore.getState().setState({ rules: sampleRules })
  // initDefaults sets the selectedClass to first valid class and applies class defaults
  useCharacterStore.getState().initDefaults()
}

beforeEach(() => {
  setupStore()
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(
    (cb: FrameRequestCallback) => {
      cb(0)
      return 0
    },
  )
})

afterEach(() => {
  vi.restoreAllMocks()
})

/* ------------------------------------------------------------------ */
/*  Initial render                                                     */
/* ------------------------------------------------------------------ */

describe('ClassSelector — initial render', () => {
  it('renders a select element labelled "Class"', () => {
    render(<ClassSelector />)
    expect(screen.getByLabelText('Class')).toBeInTheDocument()
  })

  it('renders all 4 class options', () => {
    render(<ClassSelector />)
    const select = screen.getByLabelText('Class') as HTMLSelectElement
    expect(select.options).toHaveLength(4)
  })

  it('renders correct class labels', () => {
    render(<ClassSelector />)
    const select = screen.getByLabelText('Class') as HTMLSelectElement
    const labels = Array.from(select.options).map((o) => o.label)
    expect(labels).toEqual(['Fighter', 'Wizard', 'Rogue', 'Cleric'])
  })

  it('uses the first class from valid_classes as default selectedClass', () => {
    render(<ClassSelector />)
    const select = screen.getByLabelText('Class') as HTMLSelectElement
    expect(select.value).toBe('Fighter')
  })

  it('applies first class default abilities on initial render via initDefaults', () => {
    render(<ClassSelector />)
    const state = useCharacterStore.getState()
    // Fighter defaults: str:15, dex:13, con:14, int:10, wis:12, cha:8
    expect(state.abilities.str).toBe(15)
    expect(state.abilities.dex).toBe(13)
    expect(state.abilities.con).toBe(14)
    expect(state.abilities.int).toBe(10)
    expect(state.abilities.wis).toBe(12)
    expect(state.abilities.cha).toBe(8)
  })
})

/* ------------------------------------------------------------------ */
/*  User interaction — store updates                                   */
/* ------------------------------------------------------------------ */

describe('ClassSelector — user interaction', () => {
  it('updates selectedClass in the store when a different class is selected', async () => {
    const user = userEvent.setup()
    render(<ClassSelector />)

    await user.selectOptions(screen.getByLabelText('Class'), 'Wizard')

    expect(useCharacterStore.getState().selectedClass).toBe('Wizard')
  })

  it('applies class defaults when a different class is selected', async () => {
    const user = userEvent.setup()
    render(<ClassSelector />)

    await user.selectOptions(screen.getByLabelText('Class'), 'Wizard')

    // Wizard defaults: str:8, dex:12, con:13, int:15, wis:14, cha:10
    const state = useCharacterStore.getState()
    expect(state.abilities.str).toBe(8)
    expect(state.abilities.dex).toBe(12)
    expect(state.abilities.con).toBe(13)
    expect(state.abilities.int).toBe(15)
    expect(state.abilities.wis).toBe(14)
    expect(state.abilities.cha).toBe(10)
  })

  it('select reflects the store selectedClass value', () => {
    useCharacterStore.getState().setSelectedClass('Rogue')
    render(<ClassSelector />)
    const select = screen.getByLabelText('Class') as HTMLSelectElement
    expect(select.value).toBe('Rogue')
  })

  it('switches to Rogue and applies its class defaults', async () => {
    const user = userEvent.setup()
    render(<ClassSelector />)

    await user.selectOptions(screen.getByLabelText('Class'), 'Rogue')

    // Rogue defaults: str:10, dex:15, con:12, int:13, wis:8, cha:14
    const state = useCharacterStore.getState()
    expect(state.abilities.dex).toBe(15)
    expect(state.abilities.cha).toBe(14)
    expect(state.abilities.wis).toBe(8)
  })
})

/* ------------------------------------------------------------------ */
/*  Reflect store changes                                              */
/* ------------------------------------------------------------------ */

describe('ClassSelector — reflects store changes', () => {
  it('reflects an externally mutated selectedClass', () => {
    useCharacterStore.getState().setSelectedClass('Cleric')
    render(<ClassSelector />)
    const select = screen.getByLabelText('Class') as HTMLSelectElement
    expect(select.value).toBe('Cleric')
  })

  it('applies class defaults after external setSelectedClass + applyClassDefaults', () => {
    useCharacterStore.getState().setSelectedClass('Cleric')
    useCharacterStore.getState().applyClassDefaults()
    render(<ClassSelector />)
    const state = useCharacterStore.getState()
    // Cleric defaults: str:12, dex:8, con:13, int:10, wis:15, cha:14
    expect(state.abilities.wis).toBe(15)
    expect(state.abilities.str).toBe(12)
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases — null/empty rules                                      */
/* ------------------------------------------------------------------ */

describe('ClassSelector — edge cases: null or empty rules', () => {
  it('returns null when rules is null', () => {
    useCharacterStore.getState().reset() // rules is null by default
    const { container } = render(<ClassSelector />)
    expect(container).toBeEmptyDOMElement()
  })

  it('returns null when valid_classes is empty', () => {
    const emptyRules: CharacterRules = {
      ...sampleRules,
      valid_classes: [],
    }
    useCharacterStore.getState().setState({ rules: emptyRules })
    const { container } = render(<ClassSelector />)
    expect(container).toBeEmptyDOMElement()
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('ClassSelector — accessibility', () => {
  it('associates the class label with the select via htmlFor', () => {
    render(<ClassSelector />)
    const select = screen.getByLabelText('Class')
    expect(select.tagName).toBe('SELECT')
    expect(select).toHaveAttribute('id', 'char-class')
  })

  it('label has correct htmlFor attribute', () => {
    render(<ClassSelector />)
    const label = screen.getByText('Class')
    expect(label.tagName).toBe('LABEL')
    expect(label).toHaveAttribute('for', 'char-class')
  })
})
