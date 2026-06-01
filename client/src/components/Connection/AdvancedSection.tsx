/**
 * AdvancedSection — collapsible configuration panel for DM, NPC, and
 * summarizer generation settings.
 *
 * Default: collapsed. Three subsections: Dungeon Master generation
 * settings, NPC agent settings with enable toggle, and story summarizer
 * settings with enable toggle.
 */

import { useState, type ChangeEvent } from 'react'
import { useConnectionStore } from '../../stores/connectionStore'
import styles from './AdvancedSection.module.css'

export default function AdvancedSection() {
  const [expanded, setExpanded] = useState(false)

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

  /* ---- DM handlers ---- */

  function handleDmMaxTokens(e: ChangeEvent<HTMLInputElement>) {
    const val = parseInt(e.target.value, 10)
    if (!isNaN(val)) {
      useConnectionStore.getState().setSettings({ dm_max_tokens: val })
    }
  }

  function handleDmTemperature(e: ChangeEvent<HTMLInputElement>) {
    const val = parseFloat(e.target.value)
    if (!isNaN(val)) {
      useConnectionStore.getState().setSettings({ dm_temperature: val })
    }
  }

  function handleDmTimeout(e: ChangeEvent<HTMLInputElement>) {
    const val = parseInt(e.target.value, 10)
    if (!isNaN(val)) {
      useConnectionStore.getState().setSettings({ dm_timeout: val })
    }
  }

  /* ---- NPC handlers ---- */

  function handleNpcMaxTokens(e: ChangeEvent<HTMLInputElement>) {
    const val = parseInt(e.target.value, 10)
    if (!isNaN(val)) {
      useConnectionStore.getState().setSettings({ npc_max_tokens: val })
    }
  }

  function handleNpcTemperature(e: ChangeEvent<HTMLInputElement>) {
    const val = parseFloat(e.target.value)
    if (!isNaN(val)) {
      useConnectionStore.getState().setSettings({ npc_temperature: val })
    }
  }

  function handleNpcTimeout(e: ChangeEvent<HTMLInputElement>) {
    const val = parseInt(e.target.value, 10)
    if (!isNaN(val)) {
      useConnectionStore.getState().setSettings({ npc_timeout: val })
    }
  }

  function handleNpcToggle() {
    useConnectionStore.getState().setNpcEnabled(!npcEnabled)
  }

  /* ---- Summarizer handlers ---- */

  function handleSummarizerMaxTokens(e: ChangeEvent<HTMLInputElement>) {
    const val = parseInt(e.target.value, 10)
    if (!isNaN(val)) {
      useConnectionStore.getState().setSettings({
        summarizer_max_tokens: val,
      })
    }
  }

  function handleSummarizerTemperature(e: ChangeEvent<HTMLInputElement>) {
    const val = parseFloat(e.target.value)
    if (!isNaN(val)) {
      useConnectionStore.getState().setSettings({
        summarizer_temperature: val,
      })
    }
  }

  function handleSummarizerTimeout(e: ChangeEvent<HTMLInputElement>) {
    const val = parseInt(e.target.value, 10)
    if (!isNaN(val)) {
      useConnectionStore.getState().setSettings({
        summarizer_timeout: val,
      })
    }
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
        aria-controls="advanced-settings-content"
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
        <div
          id="advanced-settings-content"
          className={styles.content}
        >
          {/* ================================================================ */}
          {/*  A. DM Generation Settings                                       */}
          {/* ================================================================ */}
          <div className={styles.subsection}>
            <h4 className={styles.subsectionTitle}>Dungeon Master</h4>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="dm-max-tokens">
                Max Tokens
              </label>
              <input
                id="dm-max-tokens"
                className={styles.numberInput}
                type="number"
                min={1}
                value={dmMaxTokens}
                onChange={handleDmMaxTokens}
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="dm-temperature">
                Temperature
              </label>
              <input
                id="dm-temperature"
                className={styles.numberInput}
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={dmTemperature}
                onChange={handleDmTemperature}
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="dm-timeout">
                Timeout (s)
              </label>
              <input
                id="dm-timeout"
                className={styles.numberInput}
                type="number"
                min={1}
                value={dmTimeout}
                onChange={handleDmTimeout}
              />
            </div>
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
              <>
                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="npc-max-tokens"
                  >
                    Max Tokens
                  </label>
                  <input
                    id="npc-max-tokens"
                    className={styles.numberInput}
                    type="number"
                    min={1}
                    value={npcMaxTokens}
                    onChange={handleNpcMaxTokens}
                  />
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="npc-temperature"
                  >
                    Temperature
                  </label>
                  <input
                    id="npc-temperature"
                    className={styles.numberInput}
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={npcTemperature}
                    onChange={handleNpcTemperature}
                  />
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="npc-timeout"
                  >
                    Timeout (s)
                  </label>
                  <input
                    id="npc-timeout"
                    className={styles.numberInput}
                    type="number"
                    min={1}
                    value={npcTimeout}
                    onChange={handleNpcTimeout}
                  />
                </div>
              </>
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
              <>
                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="summarizer-max-tokens"
                  >
                    Max Tokens
                  </label>
                  <input
                    id="summarizer-max-tokens"
                    className={styles.numberInput}
                    type="number"
                    min={1}
                    value={summarizerMaxTokens}
                    onChange={handleSummarizerMaxTokens}
                  />
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="summarizer-temperature"
                  >
                    Temperature
                  </label>
                  <input
                    id="summarizer-temperature"
                    className={styles.numberInput}
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={summarizerTemperature}
                    onChange={handleSummarizerTemperature}
                  />
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="summarizer-timeout"
                  >
                    Timeout (s)
                  </label>
                  <input
                    id="summarizer-timeout"
                    className={styles.numberInput}
                    type="number"
                    min={1}
                    value={summarizerTimeout}
                    onChange={handleSummarizerTimeout}
                  />
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
