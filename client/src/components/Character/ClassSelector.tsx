/**
 * ClassSelector — dropdown for choosing a character class.
 *
 * Reads valid_classes from rules, displays them in a select element,
 * and applies class default ability scores on change.
 */

import { useCharacterStore } from '../../stores/characterStore'
import styles from './ClassSelector.module.css'

export default function ClassSelector() {
  const selectedClass = useCharacterStore((s) => s.selectedClass)
  const rules = useCharacterStore((s) => s.rules)
  const setSelectedClass = useCharacterStore((s) => s.setSelectedClass)
  const applyClassDefaults = useCharacterStore((s) => s.applyClassDefaults)

  const classes = rules?.valid_classes ?? []

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value
    setSelectedClass(value)
    // applyClassDefaults reads the updated selectedClass from store
    requestAnimationFrame(() => {
      applyClassDefaults()
    })
  }

  if (!rules || classes.length === 0) return null

  return (
    <div className={styles.wrapper}>
      <label className={styles.label} htmlFor="char-class">
        Class
      </label>
      <select
        id="char-class"
        className={styles.select}
        value={selectedClass}
        onChange={handleChange}
      >
        {classes.map((cls) => (
          <option key={cls} value={cls}>
            {cls}
          </option>
        ))}
      </select>
    </div>
  )
}
