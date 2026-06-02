/**
 * StoryProgress tests — step-by-step goblin scrutiny of the campfire progress indicator.
 *
 * Covers: question counter, progress bar width, step dots (active/completed),
 * dot click interaction, null/empty rules edge cases, and accessibility.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useCharacterStore } from '../../stores/characterStore'
import type { CharacterRules } from '../../api/types'
import StoryProgress from './StoryProgress'

/** Rules with 3 assisted creation questions. */
const sampleRules: CharacterRules = {
  valid_classes: ['Fighter', 'Wizard'],
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
  assisted_creation_questions: [
    'What is your name?',
    'Describe your appearance.',
    'Tell your backstory.',
  ],
}

/** Reset store and configure the state with rules and story answers before each test. */
function setupStore(overrides?: Record<string, unknown>) {
  useCharacterStore.getState().reset()
  useCharacterStore.getState().setState({
    rules: sampleRules,
    storyAnswers: ['', '', ''],
    currentQuestion: 0,
    ...overrides,
  })
}

beforeEach(() => {
  setupStore()
})

/* ------------------------------------------------------------------ */
/*  Initial render                                                     */
/* ------------------------------------------------------------------ */

describe('StoryProgress — initial render', () => {
  it('shows "Question 1 of 3" on the first question', () => {
    render(<StoryProgress />)
    expect(screen.getByText('Question 1 of 3')).toBeInTheDocument()
  })

  it('shows "Question 2 of 3" on the second question', () => {
    setupStore({ currentQuestion: 1 })
    render(<StoryProgress />)
    expect(screen.getByText('Question 2 of 3')).toBeInTheDocument()
  })

  it('shows "Question 3 of 3" on the last question', () => {
    setupStore({ currentQuestion: 2 })
    render(<StoryProgress />)
    expect(screen.getByText('Question 3 of 3')).toBeInTheDocument()
  })

  it('renders a progress bar with role="progressbar"', () => {
    render(<StoryProgress />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toBeInTheDocument()
  })

  it('progress bar aria-valuenow reflects current question (1-indexed)', () => {
    setupStore({ currentQuestion: 1 })
    render(<StoryProgress />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '2')
    expect(bar).toHaveAttribute('aria-valuemin', '1')
    expect(bar).toHaveAttribute('aria-valuemax', '3')
  })
})

/* ------------------------------------------------------------------ */
/*  Progress bar width                                                 */
/* ------------------------------------------------------------------ */

describe('StoryProgress — progress bar width', () => {
  it('has 33% width on question 1 of 3', () => {
    render(<StoryProgress />)
    const fill = document.querySelector('[class*="fill"]') as HTMLElement
    expect(fill).toBeInTheDocument()
  })

  it('has 67% width on question 2 of 3', () => {
    setupStore({ currentQuestion: 1 })
    render(<StoryProgress />)
    const fill = document.querySelector('[class*="fill"]') as HTMLElement
    expect(fill).toBeInTheDocument()
  })

  it('has 100% width on question 3 of 3', () => {
    setupStore({ currentQuestion: 2 })
    render(<StoryProgress />)
    const fill = document.querySelector('[class*="fill"]') as HTMLElement
    expect(fill).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Step dots                                                          */
/* ------------------------------------------------------------------ */

describe('StoryProgress — step dots', () => {
  it('renders 3 step dots', () => {
    render(<StoryProgress />)
    const dots = screen.getAllByRole('tab')
    expect(dots).toHaveLength(3)
  })

  it('first dot is active when currentQuestion is 0', () => {
    render(<StoryProgress />)
    const dots = screen.getAllByRole('tab')
    expect(dots[0]).toHaveAttribute('aria-selected', 'true')
    expect(dots[1]).toHaveAttribute('aria-selected', 'false')
    expect(dots[2]).toHaveAttribute('aria-selected', 'false')
  })

  it('second dot is active when currentQuestion is 1', () => {
    setupStore({ currentQuestion: 1 })
    render(<StoryProgress />)
    const dots = screen.getAllByRole('tab')
    expect(dots[0]).toHaveAttribute('aria-selected', 'false')
    expect(dots[1]).toHaveAttribute('aria-selected', 'true')
    expect(dots[2]).toHaveAttribute('aria-selected', 'false')
  })

  it('third dot is active when currentQuestion is 2', () => {
    setupStore({ currentQuestion: 2 })
    render(<StoryProgress />)
    const dots = screen.getAllByRole('tab')
    expect(dots[0]).toHaveAttribute('aria-selected', 'false')
    expect(dots[1]).toHaveAttribute('aria-selected', 'false')
    expect(dots[2]).toHaveAttribute('aria-selected', 'true')
  })

  it('first dot has completed class when currentQuestion > 0', () => {
    setupStore({ currentQuestion: 2 })
    render(<StoryProgress />)
    const dots = screen.getAllByRole('tab')
    // First two dots should have completed class, last should not
    expect(dots[0].className).toMatch(/completed/)
    expect(dots[1].className).toMatch(/completed/)
    expect(dots[2].className).not.toMatch(/completed/)
  })

  it('each dot has an aria-label', () => {
    render(<StoryProgress />)
    expect(screen.getByLabelText('Go to question 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Go to question 2')).toBeInTheDocument()
    expect(screen.getByLabelText('Go to question 3')).toBeInTheDocument()
  })

  it('each dot has a title attribute', () => {
    render(<StoryProgress />)
    const dots = screen.getAllByRole('tab')
    expect(dots[0]).toHaveAttribute('title', 'Question 1')
    expect(dots[1]).toHaveAttribute('title', 'Question 2')
    expect(dots[2]).toHaveAttribute('title', 'Question 3')
  })
})

/* ------------------------------------------------------------------ */
/*  User interaction — dot clicks                                      */
/* ------------------------------------------------------------------ */

describe('StoryProgress — dot click interaction', () => {
  it('clicking dot 2 calls goToQuestion with index 1', async () => {
    const user = userEvent.setup()
    render(<StoryProgress />)

    await user.click(screen.getByLabelText('Go to question 2'))

    expect(useCharacterStore.getState().currentQuestion).toBe(1)
  })

  it('clicking dot 3 calls goToQuestion with index 2', async () => {
    const user = userEvent.setup()
    render(<StoryProgress />)

    await user.click(screen.getByLabelText('Go to question 3'))

    expect(useCharacterStore.getState().currentQuestion).toBe(2)
  })

  it('clicking dot 1 navigates back to first question', async () => {
    const user = userEvent.setup()
    setupStore({ currentQuestion: 2 })
    render(<StoryProgress />)

    await user.click(screen.getByLabelText('Go to question 1'))

    expect(useCharacterStore.getState().currentQuestion).toBe(0)
  })

  it('active dot aria-selected updates after clicking a different dot', async () => {
    const user = userEvent.setup()
    render(<StoryProgress />)

    await user.click(screen.getByLabelText('Go to question 2'))

    const dots = screen.getAllByRole('tab')
    expect(dots[0]).toHaveAttribute('aria-selected', 'false')
    expect(dots[1]).toHaveAttribute('aria-selected', 'true')
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases — empty/no questions                                    */
/* ------------------------------------------------------------------ */

describe('StoryProgress — edge cases: no questions', () => {
  it('returns null when rules is null', () => {
    useCharacterStore.getState().reset()
    const { container } = render(<StoryProgress />)
    expect(container).toBeEmptyDOMElement()
  })

  it('returns null when assisted_creation_questions is empty', () => {
    const emptyRules: CharacterRules = {
      ...sampleRules,
      assisted_creation_questions: [],
    }
    useCharacterStore.getState().setState({ rules: emptyRules })
    const { container } = render(<StoryProgress />)
    expect(container).toBeEmptyDOMElement()
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('StoryProgress — accessibility', () => {
  it('progress bar has role="progressbar" with aria attributes', () => {
    render(<StoryProgress />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '1')
    expect(bar).toHaveAttribute('aria-valuemin', '1')
    expect(bar).toHaveAttribute('aria-valuemax', '3')
  })

  it('dots container has role="tablist" with accessible label', () => {
    render(<StoryProgress />)
    const tablist = screen.getByRole('tablist')
    expect(tablist).toHaveAttribute('aria-label', 'Story questions')
  })

  it('each dot has role="tab"', () => {
    render(<StoryProgress />)
    const dots = screen.getAllByRole('tab')
    expect(dots).toHaveLength(3)
    dots.forEach((dot) => {
      expect(dot).toHaveAttribute('role', 'tab')
    })
  })
})
