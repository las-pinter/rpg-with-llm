/**
 * ThinkingIndicator — bouncing dots animation shown while the DM is thinking.
 *
 * Reads isThinking from the game store. Fades in/out with smooth opacity
 * transitions. Uses CSS keyframes for the bounce animation with staggered
 * delays on each dot.
 */

import { useGameStore } from '../../stores/gameStore'
import styles from './ThinkingIndicator.module.css'

export default function ThinkingIndicator() {
  const isThinking = useGameStore((s) => s.isThinking)

  return (
    <div
      className={`${styles.wrapper} ${isThinking ? styles.visible : styles.hidden}`}
      role="status"
      aria-live="polite"
      aria-label={isThinking ? 'DM is thinking' : undefined}
    >
      <span className={styles.label}>Thinking</span>
      <span className={styles.dots} aria-hidden="true">
        <span className={styles.dot} />
        <span className={styles.dot} />
        <span className={styles.dot} />
      </span>
    </div>
  )
}
