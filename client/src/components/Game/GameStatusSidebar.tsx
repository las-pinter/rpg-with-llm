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

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Read-only abilities grid — 3x2 matching AbilityGrid styling. */
function AbilitiesGrid({
  abilities,
}: {
  abilities: Record<string, number>
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
        {lowerKeys.map((abil) => (
          <div key={abil} className={styles.abilityCard}>
            <span className={styles.abilityLabel}>{abil}</span>
            <span className={styles.abilityScore}>
              {abilities[abil.toLowerCase()] ?? '-'}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className={styles.abilitiesGrid}>
      {keys.map((abil) => (
        <div key={abil} className={styles.abilityCard}>
          <span className={styles.abilityLabel}>{abil}</span>
          <span className={styles.abilityScore}>
            {abilities[abil] ?? '-'}
          </span>
        </div>
      ))}
    </div>
  )
}

/** Item list with bullet-pointed entries. */
function InventoryList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className={styles.emptySmall}>Nothing</p>
  }

  return (
    <ul className={styles.itemList}>
      {items.map((item, i) => (
        <li key={`${item}-${i}`} className={styles.itemEntry}>
          {item}
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
  const tokenUsage = useGameStore((s) => s.tokenUsage)
  const showTokens = useGameStore((s) => s.showTokens)
  const currentCharacter = useCharacterStore((s) => s.currentCharacter)

  const [collapsed, setCollapsed] = useState(false)

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
  const hp = typeof character?.hp === 'number' ? character.hp : 0
  const maxHp =
    typeof character?.max_hp === 'number' ? character.max_hp : 1
  const ac = typeof character?.ac === 'number' ? character.ac : null
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
  const inventory = Array.isArray(worldState?.inventory)
    ? (worldState.inventory as string[])
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
            <span className={styles.charMetaItem}>
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

      {/* Scrollable body */}
      <div className={styles.body}>
        {/* Abilities */}
        {resolvedAbilities && (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Abilities</h3>
            <AbilitiesGrid abilities={resolvedAbilities} />
          </div>
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
          <InventoryList items={inventory} />
        </div>

        {/* NPCs */}
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>NPCs</h3>
          <NpcList npcs={activeNpcs} />
        </div>
      </div>

      {/* Token Usage (only when showTokens is true) */}
      {showTokens && (
        <div className={styles.tokenSection}>
          Token Usage: {tokenUsage.accumulated} (latest:{' '}
          {tokenUsage.latest})
        </div>
      )}
    </aside>
  )
}
