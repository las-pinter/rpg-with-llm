/**
 * NpcThinkingIndicator — fade-in text showing an NPC is thinking.
 *
 * Reads npcThinking from the game store. Shows the NPC name and a brief
 * hint about what they are considering. Fades in with a smooth 1s
 * animation and hides immediately when npcThinking becomes null.
 */

import { useGameStore } from '../../stores/gameStore'
import styles from './NpcThinkingIndicator.module.css'

export default function NpcThinkingIndicator() {
  const npcThinking = useGameStore((s) => s.npcThinking)

  if (!npcThinking) return null

  const label = npcThinking.hint
    ? `${npcThinking.npcId} is pondering (${npcThinking.hint})…`
    : `${npcThinking.npcId} is pondering…`

  return (
    <div className={styles.wrapper} role="status" aria-live="polite">
      <span className={styles.label}>{label}</span>
    </div>
  )
}
