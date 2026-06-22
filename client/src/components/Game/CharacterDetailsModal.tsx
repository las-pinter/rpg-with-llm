/**
 * CharacterDetailsModal — full character sheet modal with derived data,
 * formula breakdowns, and interactive expandable sections.
 *
 * Reads `currentCharacter` and `derivedSheet` from the character store.
 * Returns null when closed or when there is no character data.
 *
 * Follows the same overlay / focus-trap / Escape-to-close pattern as
 * StoryModal.
 */

import { useEffect, useCallback, useRef, useState } from 'react'
import { useCharacterStore } from '../../stores/characterStore'
import { ItemType } from '../../api/types'
import type { DerivedSheet } from '../../api/types'
import styles from './CharacterDetailsModal.module.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CharacterDetailsModalProps {
  /** Whether the modal is visible. */
  isOpen: boolean
  /** Called to close / dismiss the modal. */
  onClose: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Ordered ability-score keys. */
const ABILITY_KEYS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const

/** D&D 5e XP thresholds for levels 1-20. */
const XP_THRESHOLDS = [
  0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
  85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000,
  305000, 355000,
]

/** All 18 D&D 5e skills with their names and associated ability. */
const ALL_SKILLS: { name: string; key: string; ability: string }[] = [
  { name: 'Acrobatics', key: 'acrobatics', ability: 'DEX' },
  { name: 'Animal Handling', key: 'animal_handling', ability: 'WIS' },
  { name: 'Arcana', key: 'arcana', ability: 'INT' },
  { name: 'Athletics', key: 'athletics', ability: 'STR' },
  { name: 'Deception', key: 'deception', ability: 'CHA' },
  { name: 'History', key: 'history', ability: 'INT' },
  { name: 'Insight', key: 'insight', ability: 'WIS' },
  { name: 'Intimidation', key: 'intimidation', ability: 'CHA' },
  { name: 'Investigation', key: 'investigation', ability: 'INT' },
  { name: 'Medicine', key: 'medicine', ability: 'WIS' },
  { name: 'Nature', key: 'nature', ability: 'INT' },
  { name: 'Perception', key: 'perception', ability: 'WIS' },
  { name: 'Performance', key: 'performance', ability: 'CHA' },
  { name: 'Persuasion', key: 'persuasion', ability: 'CHA' },
  { name: 'Religion', key: 'religion', ability: 'INT' },
  { name: 'Sleight of Hand', key: 'sleight_of_hand', ability: 'DEX' },
  { name: 'Stealth', key: 'stealth', ability: 'DEX' },
  { name: 'Survival', key: 'survival', ability: 'WIS' },
]

/** Icon per item type — matches sidebar conventions. */
const ITEM_TYPE_ICONS: Record<ItemType, string> = {
  [ItemType.WEAPON]: '⚔️',
  [ItemType.ARMOR]: '🛡️',
  [ItemType.CONSUMABLE]: '🧪',
  [ItemType.TOOL]: '🔧',
  [ItemType.CONTAINER]: '📦',
  [ItemType.QUEST]: '⭐',
  [ItemType.MISC]: '📜',
}

/** Human-readable group label for each item type. */
const ITEM_TYPE_LABELS: Record<ItemType, string> = {
  [ItemType.WEAPON]: 'Weapons',
  [ItemType.ARMOR]: 'Armor',
  [ItemType.CONSUMABLE]: 'Consumables',
  [ItemType.TOOL]: 'Tools',
  [ItemType.CONTAINER]: 'Containers',
  [ItemType.QUEST]: 'Quest Items',
  [ItemType.MISC]: 'Miscellaneous',
}

/** Ordered item types for consistent display. */
const ITEM_TYPE_ORDER: ItemType[] = [
  ItemType.WEAPON,
  ItemType.ARMOR,
  ItemType.CONSUMABLE,
  ItemType.TOOL,
  ItemType.CONTAINER,
  ItemType.QUEST,
  ItemType.MISC,
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** HP bar colour based on remaining-health ratio. */
function hpColorClass(ratio: number): string {
  if (ratio > 0.6) return styles.hpGreen
  if (ratio > 0.3) return styles.hpYellow
  return styles.hpRed
}

/** Format a numeric modifier with a + sign for non-negatives. */
function formatMod(val: number): string {
  return val >= 0 ? `+${val}` : `${val}`
}

/** CSS class for modifier colouring. */
function modColorClass(
  val: number,
  posClass: string,
  negClass: string,
): string {
  if (val > 0) return posClass
  if (val < 0) return negClass
  return ''
}

/** Compute the XP threshold for the current level. */
function xpForLevel(level: number): { current: number; next: number } {
  const idx = Math.min(level - 1, XP_THRESHOLDS.length - 2)
  return { current: XP_THRESHOLDS[idx], next: XP_THRESHOLDS[idx + 1] }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Click-to-expand formula breakdown. */
function FormulaBreakdown({
  label,
  formula,
  expanded,
  onToggle,
}: {
  label: string
  formula: string | undefined
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <div className={styles.formulaWrapper}>
      <button
        type="button"
        className={styles.formulaToggle}
        onClick={onToggle}
        aria-expanded={expanded}
      >
        {label} {expanded ? '▾' : '▸'}
      </button>
      {expanded && formula && (
        <div className={styles.formulaBreakdown}>
          {formula}
        </div>
      )}
    </div>
  )
}

/** A single stat card in the attributes row. */
function StatCard({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className={styles.statCard}>
      <span className={styles.statLabel}>{label}</span>
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CharacterDetailsModal({
  isOpen,
  onClose,
}: CharacterDetailsModalProps) {
  const character = useCharacterStore((s) => s.currentCharacter)
  const derivedSheet = useCharacterStore((s) => s.derivedSheet)

  const modalRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  // ---------- Local UI state ----------
  const [expandedAbility, setExpandedAbility] = useState<string | null>(null)
  const [acFormulaExpanded, setAcFormulaExpanded] = useState(false)
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())

  const toggleAbility = (key: string) => {
    setExpandedAbility((prev) => (prev === key ? null : key))
  }

  const toggleItemExpand = (itemId: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev)
      if (next.has(itemId)) {
        next.delete(itemId)
      } else {
        next.add(itemId)
      }
      return next
    })
  }

  // ---------- Focus first focusable element on modal open ----------
  useEffect(() => {
    if (!isOpen) return
    const raf = requestAnimationFrame(() => {
      const first = modalRef.current?.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      first?.focus()
    })
    return () => cancelAnimationFrame(raf)
  }, [isOpen])

  // ---------- Escape key + focus trap ----------
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCloseRef.current()
        return
      }

      if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }

        const isInside = modalRef.current.contains(document.activeElement)
        if (!isInside) {
          e.preventDefault()
          first.focus()
        }
      }
    },
    [],
  )

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, handleKeyDown])

  // ---------- Overlay click ----------
  const handleOverlayClick = useCallback(() => {
    onCloseRef.current()
  }, [])

  // ---------- Don't render when closed ----------
  if (!isOpen) return null

  // ---------- Empty state (no character) ----------
  if (!character) {
    return (
      <div
        className={styles.overlay}
        onClick={handleOverlayClick}
        role="dialog"
        aria-modal="true"
        aria-labelledby="character-details-title"
      >
        <div
          className={styles.modal}
          onClick={(e) => e.stopPropagation()}
          ref={modalRef}
        >
          {/* ---- Close button ---- */}
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Close character details dialog"
          >
            ✕
          </button>

          {/* ---- Title ---- */}
          <h2 id="character-details-title" className={styles.title}>
            Character Details
          </h2>

          {/* ---- Empty state ---- */}
          <div className={styles.emptyState}>
            <p className={styles.emptyText}>
              No character data available. Create a character first.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // ---------- Derived data ----------
  const hpValue: number =
    typeof character.resources?.hp?.value === 'number'
      ? character.resources.hp.value
      : 0
  const hpMax: number =
    typeof character.resources?.hp?.max === 'number'
      ? character.resources.hp.max
      : 0

  const dexScore: number =
    character.abilities['DEX'] ?? character.abilities['dex'] ?? 10
  const dexMod = Math.floor((dexScore - 10) / 2)
  const displayAc = derivedSheet?.ac ?? 10 + dexMod

  const hpRatio = hpMax > 0 ? Math.min(hpValue / hpMax, 1) : 0
  const hpPercent = Math.round(Math.max(hpRatio, 0) * 100)

  // Build ordered list of ability entries (handle uppercase/lowercase keys)
  const abilityEntries = ABILITY_KEYS.map((key) => {
    const value =
      character.abilities[key] ?? character.abilities[key.toLowerCase()]
    return { key, value: value ?? '-' }
  })

  // XP progress
  const xpBounds = xpForLevel(character.level)
  const xpProgress = xpBounds.next - xpBounds.current
  const xpInto = Math.max(0, character.xp - xpBounds.current)
  const xpRatio = xpProgress > 0 ? Math.min(xpInto / xpProgress, 1) : 0
  const xpPercent = Math.round(xpRatio * 100)

  // Ability modifiers (fallback to computed)
  const getAbilityMod = (key: string): number => {
    if (derivedSheet?.ability_modifiers?.[key] !== undefined) {
      return derivedSheet.ability_modifiers[key]
    }
    const score = character.abilities[key] ?? character.abilities[key.toLowerCase()] ?? 10
    return Math.floor((Number(score) - 10) / 2)
  }

  // Saving throw modifier
  const getSaveMod = (key: string): number | undefined => {
    return derivedSheet?.saving_throw_modifiers?.[key]
  }

  // Check if proficient in a saving throw
  const isProficientSave = (key: string): boolean => {
    const saveMod = derivedSheet?.saving_throw_modifiers?.[key]
    const abiMod = getAbilityMod(key)
    const prof = derivedSheet?.proficiency_bonus ?? 0
    if (saveMod === undefined) return false
    return saveMod === abiMod + prof
  }

  // Skill modifier
  const getSkillMod = (skillKey: string): number | undefined => {
    return derivedSheet?.skill_modifiers?.[skillKey.toLowerCase()]
  }

  // Group inventory by type
  const groupedInventory = ITEM_TYPE_ORDER.map((type) => ({
    type,
    label: ITEM_TYPE_LABELS[type],
    icon: ITEM_TYPE_ICONS[type],
    items: character.inventory.filter((item) => item.item_type === type),
  })).filter((group) => group.items.length > 0)

  // ---------- Render ----------
  return (
    <div
      className={styles.overlay}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="character-details-title"
    >
      <div
        className={styles.modal}
        onClick={(e) => e.stopPropagation()}
        ref={modalRef}
      >
        {/* ---- Close button ---- */}
        <button
          type="button"
          className={styles.closeBtn}
          onClick={onClose}
          aria-label="Close character details dialog"
        >
          ✕
        </button>

        {/* ---- Header ---- */}
        <h2 id="character-details-title" className={styles.title}>
          {character.name}
        </h2>
        <p className={styles.subtitle}>
          {character.character_class} (Level {character.level})
        </p>

        {/* ---- XP bar ---- */}
        <div className={styles.xpBarContainer}>
          <div className={styles.xpBarBg}>
            <div
              className={styles.xpBarFill}
              style={{ width: `${xpPercent}%` }}
              role="progressbar"
              aria-valuenow={character.xp}
              aria-valuemin={xpBounds.current}
              aria-valuemax={xpBounds.next}
              aria-label={`${character.xp} XP — ${xpPercent}% to next level`}
            />
          </div>
          <span className={styles.xpLabel}>
            {character.xp} XP (Level {character.level})
          </span>
        </div>

        {/* ---- Scrollable content ---- */}
        <div className={styles.content} data-testid="character-content">
          {/* ---- Attributes ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Attributes</h3>
            <div className={styles.attributesRow}>
              {/* HP */}
              <div className={styles.statCard}>
                <span className={styles.statLabel}>HP</span>
                <div className={styles.hpBarBg}>
                  <div
                    className={`${styles.hpBarFill} ${hpColorClass(hpRatio)}`}
                    style={{ width: `${hpPercent}%` }}
                    role="progressbar"
                    aria-valuenow={hpValue}
                    aria-valuemin={0}
                    aria-valuemax={hpMax}
                    aria-label={`${hpValue} of ${hpMax} hit points`}
                  />
                </div>
                <span className={styles.statValue}>
                  {hpValue}/{hpMax}
                </span>
              </div>

              {/* AC (togglable formula) */}
              <div className={styles.statCard}>
                <span className={styles.statLabel}>AC</span>
                <span className={styles.statValue}>{displayAc}</span>
                {derivedSheet && (
                  <FormulaBreakdown
                    label="Formula"
                    formula={derivedSheet.formulas?.ac}
                    expanded={acFormulaExpanded}
                    onToggle={() => setAcFormulaExpanded((v) => !v)}
                  />
                )}
              </div>

              {/* Initiative */}
              <div className={styles.statCard}>
                <span className={styles.statLabel}>Initiative</span>
                <span className={styles.statValue}>
                  {derivedSheet?.initiative != null
                    ? formatMod(derivedSheet.initiative)
                    : formatMod(dexMod)}
                </span>
              </div>

              {/* Speed */}
              <div className={styles.statCard}>
                <span className={styles.statLabel}>Speed</span>
                <span className={styles.statValue}>
                  {derivedSheet?.speed ?? '-'}
                </span>
              </div>

              {/* Proficiency Bonus */}
              <div className={styles.statCard}>
                <span className={styles.statLabel}>Proficiency</span>
                <span className={styles.statValue}>
                  {derivedSheet?.proficiency_bonus != null
                    ? formatMod(derivedSheet.proficiency_bonus)
                    : '-'}
                </span>
              </div>

              {/* Hit Dice */}
              <div className={styles.statCard}>
                <span className={styles.statLabel}>Hit Dice</span>
                <span className={styles.statValue}>
                  {derivedSheet?.hit_dice ?? '-'}
                </span>
              </div>
            </div>
          </section>

          {/* ---- Abilities ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Abilities</h3>
            <div className={styles.abilitiesGrid}>
              {abilityEntries.map(({ key, value }) => {
                const mod = getAbilityMod(key)
                const saveMod = getSaveMod(key)
                const proficient = isProficientSave(key)
                const isExpanded = expandedAbility === key
                const posClass = styles.modPositive
                const negClass = styles.modNegative

                return (
                  <button
                    key={key}
                    type="button"
                    className={`${styles.abilityCard} ${isExpanded ? styles.abilityCardExpanded : ''}`}
                    onClick={() => toggleAbility(key)}
                    aria-expanded={isExpanded}
                  >
                    <span className={styles.abilityLabel}>{key}</span>
                    <span className={styles.abilityScore}>{value}</span>
                    <span
                      className={`${styles.abilityMod} ${modColorClass(mod, posClass, negClass)}`}
                    >
                      {formatMod(mod)}
                    </span>

                    {/* Expanded: saving throw + formula */}
                    {isExpanded && (
                      <div className={styles.abilityExtra}>
                        <div className={styles.saveRow}>
                          <span className={styles.saveLabel}>Save</span>
                          <span
                            className={`${styles.saveMod} ${modColorClass(saveMod ?? 0, posClass, negClass)}`}
                          >
                            {saveMod != null ? formatMod(saveMod) : '-'}
                          </span>
                          <span
                            className={`${styles.proficientDot} ${proficient ? styles.proficientDotActive : ''}`}
                            title={proficient ? 'Proficient' : 'Not proficient'}
                          />
                        </div>
                        {derivedSheet?.formulas?.[`save_${key.toLowerCase()}`] && (
                          <div className={styles.formulaBreakdown}>
                            {derivedSheet.formulas[`save_${key.toLowerCase()}`]}
                          </div>
                        )}
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          </section>

          {/* ---- Skills ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Skills</h3>
            {derivedSheet?.skill_modifiers ? (
              <div className={styles.skillsGrid}>
                {ALL_SKILLS.map((skill) => {
                  const mod = getSkillMod(skill.key)
                  const modClass =
                    mod != null
                      ? mod > 0
                        ? styles.skillModPositive
                        : mod < 0
                          ? styles.skillModNegative
                          : styles.skillModZero
                      : ''
                  return (
                    <div key={skill.key} className={styles.skillRow}>
                      <span className={styles.skillName}>{skill.name}</span>
                      <span className={`${styles.skillMod} ${modClass}`}>
                        {mod != null ? formatMod(mod) : '-'}
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : character.skills.length > 0 ? (
              <div className={styles.skillsList}>
                {character.skills.map((skill, i) => (
                  <span key={`${skill}-${i}`} className={styles.skillTag}>
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className={styles.emptySmall}>No skills</p>
            )}
          </section>

          {/* ---- Combat ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Combat</h3>

            {/* Attack bonuses */}
            {derivedSheet?.attack_bonus &&
              Object.keys(derivedSheet.attack_bonus).length > 0 && (
                <div className={styles.combatBlock}>
                  <span className={styles.combatBlockLabel}>
                    Attack Bonuses
                  </span>
                  {Object.entries(derivedSheet.attack_bonus).map(
                    ([weapon, bonus]) => (
                      <div key={weapon} className={styles.attackRow}>
                        <span className={styles.attackName}>{weapon}</span>
                        <span
                          className={`${styles.attackBonus} ${bonus >= 0 ? styles.modPositive : styles.modNegative}`}
                        >
                          {formatMod(bonus)}
                        </span>
                      </div>
                    ),
                  )}
                </div>
              )}

            {/* Hit dice (also shown in attributes, shown here for completeness) */}
            {derivedSheet?.hit_dice && (
              <div className={styles.combatBlock}>
                <span className={styles.combatBlockLabel}>Hit Dice</span>
                <span className={styles.combatValue}>
                  {derivedSheet.hit_dice}
                </span>
              </div>
            )}

            {/* Resistances */}
            {derivedSheet?.resistances &&
              derivedSheet.resistances.length > 0 && (
                <div className={styles.combatBlock}>
                  <span className={styles.combatBlockLabel}>
                    Resistances
                  </span>
                  <div className={styles.combatTags}>
                    {derivedSheet.resistances.map((r) => (
                      <span key={r} className={styles.combatTag}>
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}

            {/* Vulnerabilities */}
            {derivedSheet?.vulnerabilities &&
              derivedSheet.vulnerabilities.length > 0 && (
                <div className={styles.combatBlock}>
                  <span className={styles.combatBlockLabel}>
                    Vulnerabilities
                  </span>
                  <div className={styles.combatTags}>
                    {derivedSheet.vulnerabilities.map((v) => (
                      <span key={v} className={styles.combatTagCombat}>
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
              )}

            {(!derivedSheet?.attack_bonus ||
              Object.keys(derivedSheet.attack_bonus).length === 0) &&
              !derivedSheet?.hit_dice &&
              (!derivedSheet?.resistances ||
                derivedSheet.resistances.length === 0) &&
              (!derivedSheet?.vulnerabilities ||
                derivedSheet.vulnerabilities.length === 0) && (
                <p className={styles.emptySmall}>No combat data</p>
              )}
          </section>

          {/* ---- Inventory ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Inventory</h3>
            {character.inventory.length > 0 ? (
              <div className={styles.inventoryGroups}>
                {groupedInventory.map((group) => (
                  <div key={group.type} className={styles.inventoryGroup}>
                    <h4 className={styles.inventoryGroupTitle}>
                      <span className={styles.inventoryGroupIcon}>
                        {group.icon}
                      </span>
                      {group.label}
                    </h4>
                    <ul className={styles.itemList}>
                      {group.items.map((item) => {
                        const isExpanded = expandedItems.has(item.id)
                        const isEquipped =
                          character.equipped_items?.includes(item.id)
                        return (
                          <li key={item.id} className={styles.itemEntry}>
                            <button
                              type="button"
                              className={styles.itemHeader}
                              onClick={() => toggleItemExpand(item.id)}
                              aria-expanded={isExpanded}
                            >
                              <span className={styles.itemIcon}>
                                {group.icon}
                              </span>
                              <span className={styles.itemName}>
                                {item.name}
                              </span>
                              {item.quantity > 1 && (
                                <span className={styles.itemQuantity}>
                                  x{item.quantity}
                                </span>
                              )}
                              {item.weight > 0 && (
                                <span className={styles.itemWeight}>
                                  {item.weight} lb
                                </span>
                              )}
                              {isEquipped && (
                                <span
                                  className={styles.equippedBadge}
                                  title="Equipped"
                                >
                                  [E]
                                </span>
                              )}
                              <span className={styles.itemExpandArrow}>
                                {isExpanded ? '▾' : '▸'}
                              </span>
                            </button>
                            {isExpanded && item.description && (
                              <div className={styles.itemDescription}>
                                {item.description}
                              </div>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.emptySmall}>Nothing carried</p>
            )}
          </section>

          {/* ---- Details ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Details</h3>
            {character.appearance && (
              <div className={styles.detailBlock}>
                <span className={styles.detailLabel}>Appearance</span>
                <p className={styles.detailText}>{character.appearance}</p>
              </div>
            )}
            {character.personality && (
              <div className={styles.detailBlock}>
                <span className={styles.detailLabel}>Personality</span>
                <p className={styles.detailText}>{character.personality}</p>
              </div>
            )}
            {character.backstory && (
              <div className={styles.detailBlock}>
                <span className={styles.detailLabel}>Backstory</span>
                <p className={styles.detailText}>{character.backstory}</p>
              </div>
            )}
          </section>

          {/* ---- Plot Hooks ---- */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Plot Hooks</h3>
            {character.hooks.length > 0 ? (
              <ul className={styles.hookList}>
                {character.hooks.map((hook, i) => (
                  <li key={`${hook}-${i}`} className={styles.hookEntry}>
                    {hook}
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.emptySmall}>None</p>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
