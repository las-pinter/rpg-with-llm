/**
 * StoryQuestion — a single "journal chapter" card for campfire story creation.
 *
 * Displays the question prompt, a textarea for the answer, and a character
 * count / "answered" indicator.
 */

import { useCharacterStore } from '../../stores/characterStore'
import styles from './StoryQuestion.module.css'

export interface StoryQuestionProps {
  /** The question prompt text. */
  question: string
  /** Index of this question within the story flow. */
  questionIndex: number
}

export default function StoryQuestion({ question, questionIndex }: StoryQuestionProps) {
  const storyAnswers = useCharacterStore((s) => s.storyAnswers)
  const saveCurrentAnswer = useCharacterStore((s) => s.saveCurrentAnswer)

  const currentValue = storyAnswers[questionIndex] ?? ''
  const charCount = currentValue.length
  const isAnswered = charCount > 0

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    saveCurrentAnswer(e.target.value, questionIndex)
  }

  return (
    <div className={styles.card}>
      <div className={styles.chapterNumber}>Chapter {questionIndex + 1}</div>

      <p className={styles.question}>{question}</p>

      <textarea
        className={styles.textarea}
        value={currentValue}
        onChange={handleChange}
        placeholder="Type your answer here…"
        aria-label={`Answer for question ${questionIndex + 1}: ${question}`}
        autoFocus
      />

      <div className={styles.footer}>
        {isAnswered && <span className={styles.answeredBadge}>&#10003; Answered</span>}
        <span className={styles.charCount}>{charCount} characters</span>
      </div>
    </div>
  )
}
