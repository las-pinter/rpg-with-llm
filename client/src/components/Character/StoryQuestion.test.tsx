/**
 * StoryQuestion tests — chapter-by-chapter goblin scrutiny of the story answer card.
 *
 * Covers: prompt rendering, textarea binding, store interaction via
 * saveCurrentAnswer, answered badge visibility, character counter,
 * chapter number heading, and edge cases.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { act } from 'react'
import userEvent from '@testing-library/user-event'
import { useCharacterStore } from '../../stores/characterStore'
import type { CharacterRules } from '../../api/types'
import StoryQuestion from './StoryQuestion'

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

/** Reset store and configure with rules and initialized story answers. */
function setupStore() {
  useCharacterStore.getState().reset()
  useCharacterStore.getState().setState({
    rules: sampleRules,
    storyAnswers: ['', '', ''],
    currentQuestion: 0,
  })
}

beforeEach(() => {
  setupStore()
})

const QUESTION_TEXT = 'What is your name?'
const CHAPTER_INDEX = 0

/* ------------------------------------------------------------------ */
/*  Initial render                                                     */
/* ------------------------------------------------------------------ */

describe('StoryQuestion — initial render', () => {
  it('shows the chapter number', () => {
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByText('Chapter 1')).toBeInTheDocument()
  })

  it('shows "Chapter 2" for the second question', () => {
    render(<StoryQuestion question="Describe your appearance." questionIndex={1} />)
    expect(screen.getByText('Chapter 2')).toBeInTheDocument()
  })

  it('renders the question prompt text', () => {
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByText(QUESTION_TEXT)).toBeInTheDocument()
  })

  it('renders a textarea for the answer', () => {
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toBeInTheDocument()
  })

  it('textarea has a placeholder', () => {
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByPlaceholderText('Type your answer here...')).toBeInTheDocument()
  })

  it('textarea is empty when no answer is stored', () => {
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
    expect(textarea).toHaveValue('')
  })

  it('does NOT show "Answered" badge when textarea is empty', () => {
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.queryByText(/Answered/)).not.toBeInTheDocument()
  })

  it('shows "0 characters" when textarea is empty', () => {
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByText('0 characters')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Store value display                                                */
/* ------------------------------------------------------------------ */

describe('StoryQuestion — displays store value', () => {
  it('displays the saved answer from the store', () => {
    useCharacterStore.getState().setState({
      storyAnswers: ['Aragorn', '', ''],
    })
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
    expect(textarea).toHaveValue('Aragorn')
  })

  it('shows "Answered" badge when store has a value', () => {
    useCharacterStore.getState().setState({
      storyAnswers: ['Gandalf', '', ''],
    })
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByText(/Answered/)).toBeInTheDocument()
  })

  it('shows correct character count from stored answer', () => {
    useCharacterStore.getState().setState({
      storyAnswers: ['Frodo', '', ''],
    })
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByText('5 characters')).toBeInTheDocument()
  })

  it('displays the answer for the second question index', () => {
    useCharacterStore.getState().setState({
      storyAnswers: ['', '', 'I was born in the Shire...'],
    })
    render(
      <StoryQuestion question="Tell your backstory." questionIndex={2} />,
    )
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
    expect(textarea).toHaveValue('I was born in the Shire...')
  })
})

/* ------------------------------------------------------------------ */
/*  User interaction                                                   */
/* ------------------------------------------------------------------ */

describe('StoryQuestion — user interaction', () => {
  it('calls saveCurrentAnswer when the user types', async () => {
    const user = userEvent.setup()
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)

    const textarea = screen.getByRole('textbox')
    await user.type(textarea, 'Legolas')

    expect(useCharacterStore.getState().storyAnswers[0]).toBe('Legolas')
  })

  it('updates character count as the user types', async () => {
    const user = userEvent.setup()
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)

    const textarea = screen.getByRole('textbox')
    await user.type(textarea, 'Hello')

    expect(screen.getByText('5 characters')).toBeInTheDocument()
  })

  it('shows "Answered" badge after typing', async () => {
    const user = userEvent.setup()
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)

    const textarea = screen.getByRole('textbox')
    await user.type(textarea, 'Gimli')

    expect(screen.getByText(/Answered/)).toBeInTheDocument()
  })

  it('updates the textarea value as the user types', async () => {
    const user = userEvent.setup()
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)

    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
    await user.type(textarea, 'Samwise')

    expect(textarea).toHaveValue('Samwise')
  })
})

/* ------------------------------------------------------------------ */
/*  Edge cases                                                         */
/* ------------------------------------------------------------------ */

describe('StoryQuestion — edge cases', () => {
  it('handles storyAnswers being shorter than questionIndex (falls back to "")', () => {
    useCharacterStore.getState().setState({
      storyAnswers: [], // empty array, no answers
    })
    render(<StoryQuestion question="Q1" questionIndex={0} />)
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
    expect(textarea).toHaveValue('')
  })

  it('handles storyAnswers index beyond array length (defaults to "")', () => {
    useCharacterStore.getState().setState({
      storyAnswers: ['only answer'],
    })
    render(<StoryQuestion question="Where?" questionIndex={5} />)
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
    expect(textarea).toHaveValue('')
    expect(screen.getByText('0 characters')).toBeInTheDocument()
  })

  it('shows correct character count for long answers', () => {
    const longAnswer = 'A'.repeat(100)
    useCharacterStore.getState().setState({
      storyAnswers: [longAnswer, '', ''],
    })
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByText('100 characters')).toBeInTheDocument()
  })

  it('hides "Answered" badge when answer is cleared', async () => {
    const user = userEvent.setup()
    useCharacterStore.getState().setState({
      storyAnswers: ['Boromir', '', ''],
    })
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)

    // Initially shows answered
    expect(screen.getByText(/Answered/)).toBeInTheDocument()

    // Clear the textarea
    const textarea = screen.getByRole('textbox')
    await user.clear(textarea)

    // Badge should be gone
    expect(screen.queryByText(/Answered/)).not.toBeInTheDocument()
  })

  it('shows "0 characters" after clearing a previously filled answer', async () => {
    const user = userEvent.setup()
    useCharacterStore.getState().setState({
      storyAnswers: ['Merry', '', ''],
    })
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)

    const textarea = screen.getByRole('textbox')
    await user.clear(textarea)

    expect(screen.getByText('0 characters')).toBeInTheDocument()
  })
})

/* ------------------------------------------------------------------ */
/*  Accessibility                                                      */
/* ------------------------------------------------------------------ */

describe('StoryQuestion — accessibility', () => {
  it('textarea has an aria-label that includes the chapter number', () => {
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toHaveAttribute(
      'aria-label',
      `Answer for question 1: ${QUESTION_TEXT}`,
    )
  })

  it('second question textarea has correct aria-label', () => {
    const q2 = 'Describe your appearance.'
    render(<StoryQuestion question={q2} questionIndex={1} />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toHaveAttribute('aria-label', `Answer for question 2: ${q2}`)
  })
})

/* ------------------------------------------------------------------ */
/*  Character count                                                    */
/* ------------------------------------------------------------------ */

describe('StoryQuestion — character count', () => {
  it('shows correct count for a short answer', () => {
    useCharacterStore.getState().setState({
      storyAnswers: ['Hi', '', ''],
    })
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByText('2 characters')).toBeInTheDocument()
  })

  it('shows correct count for an answer with spaces', () => {
    useCharacterStore.getState().setState({
      storyAnswers: ['a b c', '', ''],
    })
    render(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByText('5 characters')).toBeInTheDocument()
  })

  it('updates count via store mutation externally', () => {
    const { rerender } = render(
      <StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />,
    )
    act(() => {
      useCharacterStore.getState().saveCurrentAnswer('Updated')
    })
    rerender(<StoryQuestion question={QUESTION_TEXT} questionIndex={CHAPTER_INDEX} />)
    expect(screen.getByText('7 characters')).toBeInTheDocument()
  })
})
