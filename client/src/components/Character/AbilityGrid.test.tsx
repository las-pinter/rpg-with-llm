/**
 * AbilityGrid tests — goblin-skeptic scrutiny of point-buy ability score controls.
 *
 * Covers: rendering of all 6 abilities, +/- button interaction, boundary
 * conditions (min/max scores, empty rules, empty standard_abilities),
 * store-driven updates, and edge cases.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useCharacterStore } from '../../stores/characterStore'
import type { CharacterRules } from '../../api/types'
import AbilityGrid from './AbilityGrid'

/** A realistic rules object matching the backend contract. */
const sampleRules: CharacterRules = {
  valid_classes: ['Fighter', 'Wizard', 'Rogue', 'Cleric'],
  standard_abilities: ['str', 'dex', 'con', 'int', 'wis', 'cha'],
  class_templates: {
    Fighter: { abilities: { str: 15, dex: 13, con: 14, int: 10, wis: 12, cha: 8 } },
    Wizard: { abilities: { str: 8, dex: 12, con: 13, int: 15, wis: 14, cha: 10 } },
  },
  point_buy: {
    costs: { '8': 0, '9': 1, '10': 2, '11': 3, '12': 4, '13': 5, '14': 7, '15': 9 },
    max_points: 27,
    min_score: 8,
    max_score: 15,
  },
  assisted_creation_questions: ['Question 1', 'Question 2', 'Question 3'],
}

/** Set up store with rules and a clean point-buy baseline (all 8s, 27 points). */
function setupStore() {
  useCharacterStore.getState().reset()
  useCharacterStore.getState().setState({
    rules: sampleRules,
    abilities: { str: 8, dex: 8, con: 8, int: 8, wis: 8, cha: 8 },
    selectedClass: '',
    remainingPoints: 27,
    storyAnswers: ['', '', ''],
    currentQuestion: 0,
  })
}

beforeEach(() => {
  setupStore()
})

/* ------------------------------------------------------------------ */
/*  Initial render                                                     */
/* ------------------------------------------------------------------ */

describe('AbilityGrid — initial render', () => {
  it('renders a heading "Ability Scores"', () => {
    render(<AbilityGrid />)
    expect(screen.getByText('Ability Scores')).toBeInTheDocument()
  })

  it('renders all 6 ability labels', () => {
    render(<AbilityGrid />)
    expect(screen.getByText('Strength')).toBeInTheDocument()
    expect(screen.getByText('Dexterity')).toBeInTheDocument()
    expect(screen.getByText('Constitution')).toBeInTheDocument()
    expect(screen.getByText('Intelligence')).toBeInTheDocument()
    expect(screen.getByText('Wisdom')).toBeInTheDocument()
    expect(screen.getByText('Charisma')).toBeInTheDocument()
  })

  it('shows default score of 8 for all abilities (fallback from store)', () => {
    render(<AbilityGrid />)
    // At score 8 for all six abilities
    const scoreElements = screen.getAllByText('8')
    expect(scoreElements.length).toBeGreaterThanOrEqual(6)
  })

  it('shows remaining points (27 by default)', () => {
    render(<AbilityGrid />)
    expect(screen.getByText('27')).toBeInTheDocument()
  })

  it('shows "Remaining:" label', () => {
    render(<AbilityGrid />)
    expect(screen.getByText('Remaining:')).toBeInTheDocument()
  })

  it('shows hint text about point-buy method', () => {
    render(<AbilityGrid />)
    expect(screen.getByText(/point-buy method/i)).toBeInTheDocument()
    expect(screen.getByText(/min 8/i)).toBeInTheDocument()
  })

  it('shows cost for each ability (0 pts at score 8)', () => {
    render(<AbilityGrid />)
    const costLabels = screen.getAllByText(/pts/)
    expect(costLabels).toHaveLength(6)
    costLabels.forEach((el) => {
      expect(el.textContent).toMatch(/^\d+ pts$/)
    })
  })

  it('has increase buttons with correct aria-labels', () => {
    render(<AbilityGrid />)
    expect(screen.getByLabelText('Increase Strength')).toBeInTheDocument()
    expect(screen.getByLabelText('Increase Dexterity')).toBeInTheDocument()
    expect(screen.getByLabelText('Increase Constitution')).toBeInTheDocument()
    expect(screen.getByLabelText('Increase Intelligence')).toBeInTheDocument()
    expect(screen.getByLabelText('Increase Wisdom')).toBeInTheDocument()
    expect(screen.getByLabelText('Increase Charisma')).toBeInTheDocument()
  })

  it('has decrease buttons with correct aria-labels', () => {
    render(<AbilityGrid />)
    expect(screen.getByLabelText('Decrease Strength')).toBeInTheDocument()
    expect(screen.getByLabelText('Decrease Dexterity')).toBeInTheDocument()
    expect(screen.getByLabelText('Decrease Constitution')).toBeInTheDocument()
    expect(screen.getByLabelText('Decrease Intelligence')).toBeInTheDocument()
    expect(screen.getByLabelText('Decrease Wisdom')).toBeInTheDocument()
    expect(screen.getByLabelText('Decrease Charisma')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Button disabled states                                             */
/* ------------------------------------------------------------------ */

describe('AbilityGrid — button disabled states', () => {
  it('decrease buttons are disabled at min score (8)', () => {
    render(<AbilityGrid />)
    expect(screen.getByLabelText('Decrease Strength')).toBeDisabled()
    expect(screen.getByLabelText('Decrease Dexterity')).toBeDisabled()
    expect(screen.getByLabelText('Decrease Constitution')).toBeDisabled()
    expect(screen.getByLabelText('Decrease Intelligence')).toBeDisabled()
    expect(screen.getByLabelText('Decrease Wisdom')).toBeDisabled()
    expect(screen.getByLabelText('Decrease Charisma')).toBeDisabled()
  })

  it('increase buttons are enabled at default score (8) with full points', () => {
    render(<AbilityGrid />)
    expect(screen.getByLabelText('Increase Strength')).toBeEnabled()
    expect(screen.getByLabelText('Increase Dexterity')).toBeEnabled()
  })

  it('increase buttons are disabled when ability is at max score (15)', () => {
    useCharacterStore.getState().setState({
      abilities: { str: 15, dex: 8, con: 8, int: 8, wis: 8, cha: 8 },
    })
    render(<AbilityGrid />)
    expect(screen.getByLabelText('Increase Strength')).toBeDisabled()
    // Other abilities not at max should still be enabled
    expect(screen.getByLabelText('Increase Dexterity')).toBeEnabled()
  })

  it('increase buttons are disabled when not enough remaining points', () => {
    useCharacterStore.getState().setState({
      abilities: { str: 14, dex: 8, con: 8, int: 8, wis: 8, cha: 8 },
      remainingPoints: 1,
    })
    // Increasing from 14 to 15 costs 2 points (9 - 7), so with 1 point it's disabled
    render(<AbilityGrid />)
    expect(screen.getByLabelText('Increase Strength')).toBeDisabled()
  })

  it('decrease buttons become enabled after increasing an ability', async () => {
    const user = userEvent.setup()
    render(<AbilityGrid />)

    await user.click(screen.getByLabelText('Increase Strength'))

    expect(screen.getByLabelText('Decrease Strength')).toBeEnabled()
  })
})

/* ------------------------------------------------------------------ */
/*  User interaction — store updates                                   */
/* ------------------------------------------------------------------ */

describe('AbilityGrid — user interaction', () => {
  it('clicking + calls increaseAbility and updates score', async () => {
    const user = userEvent.setup()
    render(<AbilityGrid />)

    await user.click(screen.getByLabelText('Increase Strength'))

    const state = useCharacterStore.getState()
    expect(state.abilities.str).toBe(9)
    expect(state.remainingPoints).toBe(26) // cost 1 point (9-8)
  })

  it('clicking - calls decreaseAbility and updates score', async () => {
    const user = userEvent.setup()
    // Set str to 10 so we can decrease it (above min)
    useCharacterStore.getState().setState({
      abilities: { str: 10, dex: 8, con: 8, int: 8, wis: 8, cha: 8 },
      remainingPoints: 25, // spent 2 on str 10
    })
    render(<AbilityGrid />)

    await user.click(screen.getByLabelText('Decrease Strength'))

    const state = useCharacterStore.getState()
    expect(state.abilities.str).toBe(9) // decreased by 1
    expect(state.remainingPoints).toBe(26) // refunded 1 point
  })

  it('clicking + updates the score displayed on screen', async () => {
    const user = userEvent.setup()
    render(<AbilityGrid />)

    await user.click(screen.getByLabelText('Increase Strength'))

    // Strength score should now say 9
    expect(screen.getByText('9')).toBeInTheDocument()
  })

  it('handles multiple increases and tracks remaining points', async () => {
    const user = userEvent.setup()
    render(<AbilityGrid />)

    // Increase str from 8 to 15 (costs 9 total)
    for (let i = 0; i < 7; i++) {
      await user.click(screen.getByLabelText('Increase Strength'))
    }

    const state = useCharacterStore.getState()
    expect(state.abilities.str).toBe(15)
    expect(state.remainingPoints).toBe(18) // 27 - 9 = 18
  })
})

/* ------------------------------------------------------------------ */
/*  Reflect store changes                                              */
/* ------------------------------------------------------------------ */

describe('AbilityGrid — reflects store changes', () => {
  it('reflects externally mutated ability scores', () => {
    useCharacterStore.getState().setState({
      abilities: { str: 14, dex: 12, con: 10, int: 9, wis: 8, cha: 8 },
    })
    render(<AbilityGrid />)
    expect(screen.getByText('14')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
  })

  it('reflects externally changed remaining points', () => {
    useCharacterStore.getState().setState({ remainingPoints: 5 })
    render(<AbilityGrid />)
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('remaining points gets the empty CSS class when 0', () => {
    useCharacterStore.getState().setState({ remainingPoints: 0 })
    const { container } = render(<AbilityGrid />)
    const remainingEl = container.querySelector('[class*="remainingValue"]')
    expect(remainingEl).toHaveClass(/empty/)
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases — null/empty rules                                      */
/* ------------------------------------------------------------------ */

describe('AbilityGrid — edge cases: null or empty rules', () => {
  it('returns null when rules is null', () => {
    useCharacterStore.getState().reset() // rules is null by default
    const { container } = render(<AbilityGrid />)
    expect(container).toBeEmptyDOMElement()
  })

  it('returns null when standard_abilities is empty', () => {
    const emptyRules: CharacterRules = {
      ...sampleRules,
      standard_abilities: [],
    }
    useCharacterStore.getState().setState({ rules: emptyRules })
    const { container } = render(<AbilityGrid />)
    expect(container).toBeEmptyDOMElement()
  })

  it('handles abilities with missing entries (falls back to MIN_SCORE 8)', () => {
    // Only set str, leave others undefined
    useCharacterStore.getState().setState({
      abilities: { str: 12 },
    })
    render(<AbilityGrid />)
    // str shows 12, the rest show 8 (MIN_SCORE)
    expect(screen.getByText('12')).toBeInTheDocument()
    // Other abilities still render with fallback 8
    expect(screen.getByText('Strength')).toBeInTheDocument()
    expect(screen.getByText('Dexterity')).toBeInTheDocument()
  })

  it('handles uppercase ability keys via ABILITY_LABELS mapping', () => {
    const rulesUpper: CharacterRules = {
      ...sampleRules,
      standard_abilities: ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
    }
    useCharacterStore.getState().setState({ rules: rulesUpper })
    render(<AbilityGrid />)
    expect(screen.getByText('Strength')).toBeInTheDocument()
    expect(screen.getByText('Dexterity')).toBeInTheDocument()
    expect(screen.getByText('Constitution')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('AbilityGrid — accessibility', () => {
  it('decrease buttons have aria-label', () => {
    render(<AbilityGrid />)
    const btn = screen.getByLabelText('Decrease Strength')
    expect(btn).toHaveAttribute('aria-label', 'Decrease Strength')
  })

  it('increase buttons have aria-label', () => {
    render(<AbilityGrid />)
    const btn = screen.getByLabelText('Increase Strength')
    expect(btn).toHaveAttribute('aria-label', 'Increase Strength')
  })
})
