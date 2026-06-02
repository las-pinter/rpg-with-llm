/**
 * StoryProgress — progress indicator for the campfire story flow.
 *
 * Shows current question number / total, a progress bar, and clickable
 * step dots for navigating between questions.
 */

import { useCharacterStore } from '../../stores/characterStore'
import styles from './StoryProgress.module.css'

export default function StoryProgress() {
  const currentQuestion = useCharacterStore((s) => s.currentQuestion)
  const rules = useCharacterStore((s) => s.rules)
  const goToQuestion = useCharacterStore((s) => s.goToQuestion)

  const total = rules?.assisted_creation_questions?.length ?? 0

  if (total === 0) return null

  const questionNum = currentQuestion + 1
  const progressPct = (questionNum / total) * 100

  return (
    <div className={styles.wrapper}>
      <div className={styles.progressText}>
        <span className={styles.counter}>
          Question {questionNum} of {total}
        </span>
      </div>

      <div
        className={styles.bar}
        role="progressbar"
        aria-valuenow={questionNum}
        aria-valuemin={1}
        aria-valuemax={total}
      >
        <div className={styles.fill} style={{ width: `${progressPct}%` }} />
      </div>

      <div className={styles.dots} role="tablist" aria-label="Story questions">
        {Array.from({ length: total }, (_, i) => (
          <button
            key={i}
            type="button"
            className={`${styles.dot} ${
              i === currentQuestion ? styles.active : ''
            } ${i < currentQuestion ? styles.completed : ''}`}
            onClick={() => goToQuestion(i)}
            role="tab"
            aria-selected={i === currentQuestion}
            aria-label={`Go to question ${i + 1}`}
            title={`Question ${i + 1}`}
          />
        ))}
      </div>
    </div>
  )
}
