/**
 * AdvancedSection — collapsible configuration panel for DM, NPC, and
 * summarizer generation settings.
 *
 * Default: collapsed. Three subsections: Dungeon Master generation
 * settings, NPC agent settings with enable toggle, and story summarizer
 * settings with enable toggle.
 */

import { useState, useId, type ChangeEvent } from 'react'
import { useConnectionStore } from '../../stores/connectionStore'
import styles from './AdvancedSection.module.css'

/** Factory for integer-setting handlers (max_tokens, timeout). */
function makeIntHandler(key: string) {
  return (e: ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10)
    if (!isNaN(val) && val >= 1) {
      useConnectionStore.getState().setSettings({ [key]: val })
    }
  }
}

/** Factory for float-setting handlers (temperature, 0–2 range). */
function makeFloatHandler(key: string) {
  return (e: ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value)
    if (!isNaN(val) && val >= 0 && val <= 2) {
      useConnectionStore.getState().setSettings({ [key]: val })
    }
  }
}

/** Renders the three standard settings fields for a given prefix. */
function SettingsFields({
  prefix,
  maxTokens,
  temperature,
  timeout,
}: {
  prefix: string
  maxTokens: number
  temperature: number
  timeout: number
}) {
  return (
    <>
      <div className={styles.field}>
        <label className={styles.label} htmlFor={`${prefix}-max-tokens`}>
          Max Tokens
        </label>
        <input
          id={`${prefix}-max-tokens`}
          className={styles.numberInput}
          type="number"
          min={1}
          value={maxTokens}
          onChange={makeIntHandler(`${prefix}_max_tokens`)}
        />
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor={`${prefix}-temperature`}>
          Temperature
        </label>
        <input
          id={`${prefix}-temperature`}
          className={styles.numberInput}
          type="number"
          min={0}
          max={2}
          step={0.1}
          value={temperature}
          onChange={makeFloatHandler(`${prefix}_temperature`)}
        />
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor={`${prefix}-timeout`}>
          Timeout (s)
        </label>
        <input
          id={`${prefix}-timeout`}
          className={styles.numberInput}
          type="number"
          min={1}
          value={timeout}
          onChange={makeIntHandler(`${prefix}_timeout`)}
        />
      </div>
    </>
  )
}

export default function AdvancedSection() {
  const [expanded, setExpanded] = useState(false)
  const contentId = useId()

  // DM settings
  const dmMaxTokens = useConnectionStore((s) => s.dm_max_tokens)
  const dmTemperature = useConnectionStore((s) => s.dm_temperature)
  const dmTimeout = useConnectionStore((s) => s.dm_timeout)

  // NPC settings
  const npcMaxTokens = useConnectionStore((s) => s.npc_max_tokens)
  const npcTemperature = useConnectionStore((s) => s.npc_temperature)
  const npcTimeout = useConnectionStore((s) => s.npc_timeout)
  const npcEnabled = useConnectionStore((s) => s.npcEnabled)

  // Summarizer settings
  const summarizerMaxTokens = useConnectionStore(
    (s) => s.summarizer_max_tokens,
  )
  const summarizerTemperature = useConnectionStore(
    (s) => s.summarizer_temperature,
  )
  const summarizerTimeout = useConnectionStore(
    (s) => s.summarizer_timeout,
  )
  const summarizerEnabled = useConnectionStore(
    (s) => s.summarizerEnabled,
  )

  function toggleExpanded() {
    setExpanded((prev) => !prev)
  }

  function handleNpcToggle() {
    useConnectionStore.getState().setNpcEnabled(!npcEnabled)
  }

  function handleSummarizerToggle() {
    useConnectionStore.getState().setSummarizerEnabled(!summarizerEnabled)
  }

  return (
    <div className={styles.container}>
      {/* ---- Collapsible Header ---- */}
      <button
        type="button"
        className={styles.header}
        onClick={toggleExpanded}
        aria-expanded={expanded}
        aria-controls={contentId}
      >
        <span>Advanced Settings</span>
        <span
          className={`${styles.chevron} ${expanded ? styles.chevronExpanded : ''}`}
          aria-hidden="true"
        >
          ▶
        </span>
      </button>

      {/* ---- Collapsible Content ---- */}
      {expanded && (
        <div id={contentId} className={styles.content}>
          {/* ================================================================ */}
          {/*  A. DM Generation Settings                                       */}
          {/* ================================================================ */}
          <div className={styles.subsection}>
            <h4 className={styles.subsectionTitle}>Dungeon Master</h4>

            <SettingsFields
              prefix="dm"
              maxTokens={dmMaxTokens}
              temperature={dmTemperature}
              timeout={dmTimeout}
            />
          </div>

          {/* ================================================================ */}
          {/*  B. NPC Agent Settings                                           */}
          {/* ================================================================ */}
          <div className={styles.subsection}>
            <h4 className={styles.subsectionTitle}>NPC Agents</h4>

            <div className={styles.toggleRow}>
              <input
                id="npc-enabled"
                className={styles.checkbox}
                type="checkbox"
                checked={npcEnabled}
                onChange={handleNpcToggle}
              />
              <label className={styles.toggleLabel} htmlFor="npc-enabled">
                Enable NPC Agents
              </label>
            </div>

            {npcEnabled && (
              <SettingsFields
                prefix="npc"
                maxTokens={npcMaxTokens}
                temperature={npcTemperature}
                timeout={npcTimeout}
              />
            )}
          </div>

          {/* ================================================================ */}
          {/*  C. Story Summarizer Settings                                    */}
          {/* ================================================================ */}
          <div className={styles.subsection}>
            <h4 className={styles.subsectionTitle}>Story Summarizer</h4>

            <div className={styles.toggleRow}>
              <input
                id="summarizer-enabled"
                className={styles.checkbox}
                type="checkbox"
                checked={summarizerEnabled}
                onChange={handleSummarizerToggle}
              />
              <label
                className={styles.toggleLabel}
                htmlFor="summarizer-enabled"
              >
                Enable Story Summarizer
              </label>
            </div>

            {summarizerEnabled && (
              <SettingsFields
                prefix="summarizer"
                maxTokens={summarizerMaxTokens}
                temperature={summarizerTemperature}
                timeout={summarizerTimeout}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
