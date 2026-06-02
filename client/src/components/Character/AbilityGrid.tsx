/**
 * AbilityGrid — point-buy ability score controls.
 *
 * Displays a grid of the six standard abilities (Strength, Dexterity, etc.)
 * with +/- buttons for adjusting scores and cost display. Reads and writes
 * directly to characterStore.
 */

import { useCharacterStore } from '../../stores/characterStore'
import styles from './AbilityGrid.module.css'

/** Maps ability keys (from the server) to human-readable full names. */
const ABILITY_LABELS: Record<string, string> = {
  str: 'Strength',
  dex: 'Dexterity',
  con: 'Constitution',
  int: 'Intelligence',
  wis: 'Wisdom',
  cha: 'Charisma',
  STR: 'Strength',
  DEX: 'Dexterity',
  CON: 'Constitution',
  INT: 'Intelligence',
  WIS: 'Wisdom',
  CHA: 'Charisma',
}

/** Minimum score achievable via point-buy (D&D 5e standard). */
const MIN_SCORE = 8

export default function AbilityGrid() {
  const abilities = useCharacterStore((s) => s.abilities)
  const remainingPoints = useCharacterStore((s) => s.remainingPoints)
  const rules = useCharacterStore((s) => s.rules)
  const increaseAbility = useCharacterStore((s) => s.increaseAbility)
  const decreaseAbility = useCharacterStore((s) => s.decreaseAbility)
  const canIncrease = useCharacterStore((s) => s.canIncrease)
  const canDecrease = useCharacterStore((s) => s.canDecrease)
  const getCost = useCharacterStore((s) => s.getCost)

  if (!rules) return null

  const standardAbilities = rules.standard_abilities

  if (standardAbilities.length === 0) return null

  const isEmpty = remainingPoints <= 0

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <h3 className={styles.headerTitle}>Ability Scores</h3>
        <span className={styles.remainingBadge}>
          Remaining:
          <span className={`${styles.remainingValue} ${isEmpty ? styles.empty : ''}`}>
            {remainingPoints}
          </span>
        </span>
      </div>
      <p className={styles.hint}>
        Assign scores using the standard point-buy method (min {MIN_SCORE}). Your class
        choice will suggest starting values.
      </p>

      <div className={styles.grid}>
        {standardAbilities.map((abil) => {
          const score = abilities[abil] ?? MIN_SCORE
          const cost = getCost(score)
          const label = ABILITY_LABELS[abil] ?? abil.toUpperCase()

          return (
            <div key={abil} className={styles.card}>
              <span className={styles.label}>{label}</span>
              <span className={styles.score}>{score}</span>
              <div className={styles.controls}>
                <button
                  type="button"
                  className={styles.btn}
                  onClick={() => decreaseAbility(abil)}
                  disabled={!canDecrease(abil)}
                  aria-label={`Decrease ${label}`}
                >
                  −
                </button>
                <button
                  type="button"
                  className={styles.btn}
                  onClick={() => increaseAbility(abil)}
                  disabled={!canIncrease(abil)}
                  aria-label={`Increase ${label}`}
                >
                  +
                </button>
              </div>
              <span className={styles.cost}>{cost} pts</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
