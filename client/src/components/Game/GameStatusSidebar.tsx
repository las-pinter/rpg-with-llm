/**
 * GameStatusSidebar — collapsible stats panel for the game view.
 *
 * Reads worldState from the game store and displays character stats,
 * abilities, inventory, NPCs, and token usage in a dark fantasy styled
 * sidebar. Can collapse to a narrow strip for more game-space.
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useGameStore } from '../../stores/gameStore'
import { useCharacterStore } from '../../stores/characterStore'
import type { Item } from '../../api/types'
import CharacterDetailsModal from './CharacterDetailsModal'
import styles from './GameStatusSidebar.module.css'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Ability keys displayed in the read-only grid. */
const ABILITY_KEYS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const

/** Abbreviation keys (lowercase alternative). */
const ABILITY_LOWER: Record<string, string> = {
  str: 'STR',
  dex: 'DEX',
  con: 'CON',
  int: 'INT',
  wis: 'WIS',
  cha: 'CHA',
}

/** Key skills to display in the skills section. */
const KEY_SKILLS = [
  'Perception',
  'Stealth',
  'Investigation',
  'Insight',
  'Athletics',
  'Acrobatics',
]

/** Mapping from ItemType to display icon/emoji. */
const ITEM_TYPE_ICON: Record<string, string> = {
  weapon: '\u2694\uFE0F',
  armor: '\uD83D\uDEE1\uFE0F',
  consumable: '\uD83E\uDDEA',
  tool: '\uD83D\uDD27',
  container: '\uD83D\uDCE6',
  quest: '\u2B50',
  misc: '\uD83D\uDCDC',
}

const MOBILE_BREAKPOINT = '(max-width: 768px)'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert snake_case to Title Case: "dark_forest" → "Dark Forest". */
function formatLocation(value: string): string {
  return value
    .split('_')
    .map((word) => {
      if (word.length === 0) return word
      return word.charAt(0).toUpperCase() + word.slice(1)
    })
    .join(' ')
}

/** Determine HP bar color class based on health ratio. */
function hpColorClass(ratio: number): string {
  if (ratio > 0.6) return styles.hpGreen
  if (ratio > 0.3) return styles.hpYellow
  return styles.hpRed
}

/** Resolve ability display key from any casing. */
function resolveAbilityKey(key: string): string {
  return ABILITY_LOWER[key] ?? key.toUpperCase()
}

/** Format an ability modifier with sign prefix. */
function formatModifier(mod: number): string {
  return mod >= 0 ? `+${mod}` : `${mod}`
}

/** Get display icon for an item type. */
function getItemTypeIcon(itemType: string): string {
  return ITEM_TYPE_ICON[itemType] ?? ITEM_TYPE_ICON.MISC
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Read-only abilities grid — 3x2 matching AbilityGrid styling, with modifiers. */
function AbilitiesGrid({
  abilities,
  modifiers,
}: {
  abilities: Record<string, number>
  modifiers?: Record<string, number> | null
}) {
  const keys = ABILITY_KEYS.filter((k) => k in abilities)

  if (keys.length === 0) {
    // Try lowercase keys
    const lowerKeys = ABILITY_KEYS.filter(
      (k) => abilities[k.toLowerCase()] !== undefined,
    )
    if (lowerKeys.length === 0) return null

    return (
      <div className={styles.abilitiesGrid}>
        {lowerKeys.map((abil) => {
          const mod = modifiers?.[abil.toLowerCase()] ?? modifiers?.[abil]
          return (
            <div key={abil} className={styles.abilityCard}>
              <span className={styles.abilityLabel}>{abil}</span>
              <span className={styles.abilityScore}>
                {abilities[abil.toLowerCase()] ?? '-'}
              </span>
              {mod !== undefined && (
                <span
                  className={`${styles.abilityModifier} ${mod >= 0 ? styles.modPositive : styles.modNegative}`}
                >
                  {formatModifier(mod)}
                </span>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className={styles.abilitiesGrid}>
      {keys.map((abil) => {
        const mod = modifiers?.[abil]
        return (
          <div key={abil} className={styles.abilityCard}>
            <span className={styles.abilityLabel}>{abil}</span>
            <span className={styles.abilityScore}>
              {abilities[abil] ?? '-'}
            </span>
            {mod !== undefined && (
              <span
                className={`${styles.abilityModifier} ${mod >= 0 ? styles.modPositive : styles.modNegative}`}
              >
                {formatModifier(mod)}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** Saving throws section with proficiency indicators. */
function SavingThrowsSection({
  saves,
  abilityMods,
  proficiencyBonus,
}: {
  saves: Record<string, number>
  abilityMods?: Record<string, number> | null
  proficiencyBonus?: number
}) {
  const entries = Object.entries(saves)
  if (entries.length === 0) return null

  return (
    <div className={styles.section}>
      <h3 className={styles.sectionTitle}>Saving Throws</h3>
      <div className={styles.savesGrid}>
        {entries.map(([key, mod]) => {
          const abilityMod = abilityMods?.[key] ?? abilityMods?.[key.toUpperCase()] ?? 0
          const isProficient =
            proficiencyBonus !== undefined &&
            mod === abilityMod + proficiencyBonus

          return (
            <div key={key} className={styles.saveRow}>
              <span className={styles.saveLabel}>
                {isProficient && (
                  <span
                    className={styles.saveProficient}
                    title="Proficient"
                  >
                    ●
                  </span>
                )}
                {key.toUpperCase().slice(0, 3)}
              </span>
              <span
                className={`${styles.saveMod} ${mod >= 0 ? styles.modPositive : styles.modNegative}`}
              >
                {formatModifier(mod)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** Skills section showing key skill modifiers. */
function SkillsSection({
  skills,
  keys,
}: {
  skills: Record<string, number>
  keys: string[]
}) {
  const entries = keys
    .filter((k) => skills[k] !== undefined)
    .map((k) => [k, skills[k]] as [string, number])

  if (entries.length === 0) return null

  return (
    <div className={styles.section}>
      <h3 className={styles.sectionTitle}>Skills</h3>
      <div className={styles.skillsList}>
        {entries.map(([name, mod]) => (
          <div key={name} className={styles.skillRow}>
            <span className={styles.skillLabel}>{name}</span>
            <span
              className={`${styles.skillMod} ${mod >= 0 ? styles.modPositive : styles.modNegative}`}
            >
              {formatModifier(mod)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Item list with type icons and equipped indicators. */
function InventoryList({
  items,
  equippedIds,
}: {
  items: Item[]
  equippedIds: string[]
}) {
  if (items.length === 0) {
    return <p className={styles.emptySmall}>Nothing</p>
  }

  return (
    <ul className={styles.itemList}>
      {items.map((item, i) => (
        <li key={`${item.id}-${i}`} className={styles.itemEntry}>
          <span className={styles.itemIcon} aria-hidden="true">
            {getItemTypeIcon(item.item_type)}
          </span>
          <span className={styles.itemName}>{item.name}</span>
          {item.quantity > 1 && (
            <span className={styles.itemQty}>x{item.quantity}</span>
          )}
          {equippedIds.includes(item.id) && (
            <span className={styles.equippedIndicator}>[E]</span>
          )}
        </li>
      ))}
    </ul>
  )
}

/** NPC entries with last-seen turn info. */
function NpcList({
  npcs,
}: {
  npcs: Record<string, { name: string; last_seen_turn: number }>
}) {
  const entries = Object.values(npcs)

  if (entries.length === 0) {
    return <p className={styles.emptySmall}>No NPCs encountered yet.</p>
  }

  return (
    <ul className={styles.npcList}>
      {entries.map((npc, i) => (
        <li key={`${npc.name}-${i}`} className={styles.npcEntry}>
          <span className={styles.npcName}>{npc.name}</span>
          <span className={styles.npcSeen}>
            Last seen: turn {npc.last_seen_turn}
          </span>
        </li>
      ))}
    </ul>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function GameStatusSidebar() {
  const worldState = useGameStore((s) => s.worldState)
  const tokenTotal = useGameStore((s) => s.tokenUsage.total.total_tokens)
  const tokenLatest = useGameStore((s) => s.tokenUsage.latest.total_tokens)
  const totalPrompt = useGameStore((s) => s.tokenUsage.total.prompt_tokens)
  const totalCompletion = useGameStore((s) => s.tokenUsage.total.completion_tokens)
  const showTokens = useGameStore((s) => s.showTokens)
  const currentCharacter = useCharacterStore((s) => s.currentCharacter)
  const derivedSheet = useCharacterStore((s) => s.derivedSheet)

  const [collapsed, setCollapsed] = useState(false)
  const [showSheet, setShowSheet] = useState(false)

  // On mobile/small screens, collapse by default
  useEffect(() => {
    const mq = window.matchMedia(MOBILE_BREAKPOINT)

    const handler = (e: MediaQueryListEvent | MediaQueryList) => {
      if (e.matches) {
        setCollapsed(true)
      }
    }

    // Set initial state
    handler(mq)

    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const toggleCollapse = useCallback(() => {
    setCollapsed((c) => !c)
  }, [])

  const handleOpenSheet = useCallback(() => {
    setShowSheet(true)
  }, [])

  const handleCloseSheet = useCallback(() => {
    setShowSheet(false)
  }, [])

  // Extract data from world state
  const character = worldState?._character as
    | Record<string, unknown>
    | undefined

  const name =
    typeof character?.name === 'string'
      ? character.name
      : currentCharacter?.name
        ? currentCharacter.name
        : 'Unknown'
  const charClass =
    typeof character?.character_class === 'string'
      ? character.character_class
      : null
  const level =
    typeof character?.level === 'number' ? character.level : 1

  // Read HP from resources.hp.value / resources.hp.max
  const resources = character?.resources as
    | Record<string, { value: number; max: number }>
    | undefined
  const hp = resources?.hp?.value ?? 0
  const maxHp = resources?.hp?.max ?? 1

  // Read AC from derived sheet with fallback to world state
  const rawAc = typeof character?.ac === 'number' ? character.ac : null
  const ac = derivedSheet?.ac ?? rawAc

  const xp = typeof character?.xp === 'number' ? character.xp : null
  const abilities = character?.abilities as
    | Record<string, number>
    | undefined

  const gold =
    typeof worldState?.gold === 'number' ? worldState.gold : null
  const location =
    typeof worldState?.current_location === 'string'
      ? worldState.current_location
      : null

  // Read inventory from character object (Item[]) with fallback
  const inventoryItems: Item[] = Array.isArray(character?.inventory)
    ? (character.inventory as Item[])
    : (Array.isArray(worldState?.inventory)
        ? (worldState.inventory as Item[])
        : [])

  // Read equipped items
  const equippedItemIds: string[] = Array.isArray(character?.equipped_items)
    ? (character.equipped_items as string[])
    : []

  const activeNpcs = (worldState?.active_npcs as Record<
    string,
    { name: string; last_seen_turn: number }
  >) ?? {}

  // Compute HP display values
  const hpRatio = maxHp > 0 ? Math.min(hp / maxHp, 1) : 0
  const hpPercent = Math.round(hpRatio * 100)

  // Formatted location string (memoized — involves string split/map/join)
  const formattedLocation = useMemo(() => {
    return location ? formatLocation(location) : null
  }, [location])

  // Resolve ability keys (handle both uppercase and lowercase)
  const resolvedAbilities: Record<string, number> | null = useMemo(() => {
    if (!abilities || Object.keys(abilities).length === 0) return null

    return Object.fromEntries(
      Object.entries(abilities).map(([k, v]) => [
        resolveAbilityKey(k),
        v,
      ]),
    )
  }, [abilities])

  // -------------------------------------------------------------------
  // Render: Empty State
  // -------------------------------------------------------------------

  if (!worldState) {
    return (
      <aside className={styles.sidebar} aria-label="Character status">
        <div className={styles.emptyState}>
          <p className={styles.emptyText}>
            Start your adventure to see character stats
          </p>
        </div>
      </aside>
    )
  }

  // -------------------------------------------------------------------
  // Render: Collapsed State
  // -------------------------------------------------------------------

  if (collapsed) {
    return (
      <aside
        className={`${styles.sidebar} ${styles.collapsed}`}
        aria-label="Character status"
      >
        <button
          type="button"
          className={`${styles.toggleBtn} ${styles.toggleBtnCollapsed}`}
          onClick={toggleCollapse}
          aria-label="Expand sidebar"
        >
          ▶
        </button>
        <div className={styles.collapsedBody}>
          <span className={styles.collapsedInitial}>
            {name ? name.charAt(0).toUpperCase() : '?'}
          </span>
          <span className={styles.collapsedLevel}>
            {charClass ?? `Lv${level}`}
          </span>
          {/* Collapsed derived stats summary */}
          <div className={styles.collapsedDerivedStats}>
            <span className={styles.collapsedStat} title={`${hp}/${maxHp} HP`}>
              ❤️{hp}/{maxHp}
            </span>
            <span className={styles.collapsedStat} title={`AC ${ac}`}>
              🛡️{ac ?? '?'}
            </span>
          </div>
        </div>
      </aside>
    )
  }

  // -------------------------------------------------------------------
  // Render: Expanded State
  // -------------------------------------------------------------------

  return (
    <aside className={styles.sidebar} aria-label="Character status">
      {/* Header with toggle */}
      <div className={styles.header}>
        <div className={styles.charInfo}>
          <span className={styles.charName}>{name}</span>
          <span className={styles.charSub}>
            {charClass
              ? `${charClass} (Level ${level})`
              : `Level ${level}`}
          </span>
        </div>
        <button
          type="button"
          className={styles.toggleBtn}
          onClick={toggleCollapse}
          aria-label="Collapse sidebar"
        >
          ◀
        </button>
      </div>

      {/* HP Bar */}
      <div className={styles.hpSection}>
        <div className={styles.hpLabel}>
          <span>HP</span>
          <span>
            {hp}/{maxHp}
          </span>
        </div>
        <div className={styles.hpBarBg}>
          <div
            className={`${styles.hpBarFill} ${hpColorClass(hpRatio)}`}
            style={{ width: `${hpPercent}%` }}
            role="progressbar"
            aria-valuenow={hp}
            aria-valuemin={0}
            aria-valuemax={maxHp}
            aria-label={`${hp} of ${maxHp} hit points`}
          />
        </div>
        <div className={styles.charMeta}>
          {ac !== null && (
            <span
              className={styles.charMetaItem}
              title={derivedSheet?.formulas?.ac ?? ''}
            >
              AC <span className={styles.charMetaValue}>{ac}</span>
            </span>
          )}
          {xp !== null && (
            <span className={styles.charMetaItem}>
              XP <span className={styles.charMetaValue}>{xp}</span>
            </span>
          )}
        </div>
      </div>

      {/* Character Sheet button */}
      <div className={styles.sheetBtnWrapper}>
        <button
          type="button"
          className={styles.charSheetBtn}
          onClick={handleOpenSheet}
          aria-label="Open character sheet"
        >
          📋 Character Sheet
        </button>
      </div>

      {/* Scrollable body */}
      <div className={styles.body}>
        {/* Abilities */}
        {resolvedAbilities && (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Abilities</h3>
            <AbilitiesGrid
              abilities={resolvedAbilities}
              modifiers={derivedSheet?.ability_modifiers}
            />
          </div>
        )}

        {/* Saving Throws */}
        {derivedSheet?.saving_throw_modifiers &&
          Object.keys(derivedSheet.saving_throw_modifiers).length > 0 && (
            <SavingThrowsSection
              saves={derivedSheet.saving_throw_modifiers}
              abilityMods={derivedSheet.ability_modifiers}
              proficiencyBonus={derivedSheet.proficiency_bonus}
            />
          )}

        {/* Skills */}
        {derivedSheet?.skill_modifiers &&
          Object.keys(derivedSheet.skill_modifiers).length > 0 && (
            <SkillsSection
              skills={derivedSheet.skill_modifiers}
              keys={KEY_SKILLS}
            />
          )}

        {/* Gold & Location */}
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>World</h3>
          <div className={styles.infoRows}>
            {gold !== null && (
              <div className={styles.infoRow}>
                <span className={styles.infoIcon} aria-hidden="true">◆</span>
                <span>{gold} gold</span>
              </div>
            )}
            {location !== null && (
              <div className={styles.infoRow}>
                <span className={styles.infoLabel}>Location:</span>
                <span>{formattedLocation}</span>
              </div>
            )}
            {gold === null && location === null && (
              <p className={styles.emptySmall}>No world data yet.</p>
            )}
          </div>
        </div>

        {/* Inventory */}
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Inventory</h3>
          <InventoryList
            items={inventoryItems}
            equippedIds={equippedItemIds}
          />
        </div>

        {/* NPCs */}
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>NPCs</h3>
          <NpcList npcs={activeNpcs} />
        </div>
      </div>

      {/* Token Usage (only when showTokens is true) */}
      {showTokens && (
        <div
          className={styles.tokenSection}
          title={`Prompt: ${totalPrompt.toLocaleString()} | Completion: ${totalCompletion.toLocaleString()}`}
        >
          <span className={styles.tokenIcon} aria-hidden="true">⚡</span>
          <span className={styles.tokenTotal}>
            {tokenTotal.toLocaleString()}
          </span>
          <span className={styles.tokenBreakdown}>
            {tokenLatest > 0 && (
              <>+{tokenLatest.toLocaleString()} this turn</>
            )}
          </span>
        </div>
      )}

      {/* Character Details Modal */}
      <CharacterDetailsModal
        isOpen={showSheet}
        onClose={handleCloseSheet}
      />
    </aside>
  )
}
