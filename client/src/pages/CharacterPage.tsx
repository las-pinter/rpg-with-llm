/**
 * CharacterPage — character creation and load management hub.
 *
 * Top-level tabs: Create ↔ Load (controlled by activeTab in store).
 * Create sub-tabs: Campfire ↔ Manual (controlled by creationMode in store).
 * Review mode (creationMode === 'review') replaces the sub-tab content
 * with the ReviewSheet.
 *
 * Follows the same pattern as ConnectionPage: CSS module, named export,
 * clean structure with loading/error states.
 */

import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCharacterStore } from '../stores/characterStore'
import { useCharacterRules } from '../hooks/useCharacterRules'
import {
  CampfireMode,
  ManualMode,
  ReviewSheet,
  LoadTab,
} from '../components/Character'
import styles from './CharacterPage.module.css'

export default function CharacterPage() {
  const navigate = useNavigate()

  // ---- Character store ----
  const activeTab = useCharacterStore((s) => s.activeTab)
  const creationMode = useCharacterStore((s) => s.creationMode)
  const setActiveTab = useCharacterStore((s) => s.setActiveTab)
  const setCreationMode = useCharacterStore((s) => s.setCreationMode)

  // ---- Fetch rules on mount (hook returns { loading, error } from store selectors) ----
  const { loading: rulesLoading, error: rulesError } = useCharacterRules()

  // ---- Handlers ----
  const handleTabChange = useCallback(
    (tab: 'create' | 'load') => {
      setActiveTab(tab)
    },
    [setActiveTab],
  )

  const handleModeChange = useCallback(
    (mode: 'campfire' | 'manual') => {
      setCreationMode(mode)
    },
    [setCreationMode],
  )

  // Already combined in the hook — just use those values directly.
  const isLoading = rulesLoading
  const hasError = rulesError

  // ---- Render ----
  return (
    <div className={styles.page}>
      {/* ---- Title ---- */}
      <h1 className={styles.title}>&#x2694;&#xFE0F; Character</h1>
      <p className={styles.subtitle}>Create or load your adventurer</p>
      <hr className={styles.accentBar} />

      {/* ---- Loading banner ---- */}
      {isLoading && (
        <div className={styles.loadingBanner} role="status">
          <span className={styles.spinner} aria-hidden="true" />
          <span>Loading character rules...</span>
        </div>
      )}

      {/* ---- Error banner ---- */}
      {!isLoading && hasError && (
        <div className={styles.errorBanner} role="alert">
          <span aria-hidden="true">&#x26A0;&#xFE0F;</span>
          <span>
            Could not load character rules. You can still create a character.
          </span>
        </div>
      )}

      {/* ---- Top-level tabs: Create / Load ---- */}
      <nav className={styles.tabBar} aria-label="Character page tabs">
        <button
          type="button"
          className={`${styles.tab} ${activeTab === 'create' ? styles.tabActive : ''}`}
          onClick={() => handleTabChange('create')}
          aria-current={activeTab === 'create' ? 'page' : undefined}
        >
          Create
        </button>
        <button
          type="button"
          className={`${styles.tab} ${activeTab === 'load' ? styles.tabActive : ''}`}
          onClick={() => handleTabChange('load')}
          aria-current={activeTab === 'load' ? 'page' : undefined}
        >
          Load
        </button>
      </nav>

      {/* ---- Tab content ---- */}
      <div className={styles.tabContent}>
        {activeTab === 'create' ? (
          <>
            {/* ---- Sub-tab bar: Campfire / Manual (hidden in review) ---- */}
            {creationMode !== 'review' && (
              <nav className={styles.subTabBar} aria-label="Creation mode tabs">
                <button
                  type="button"
                  className={`${styles.subTab} ${creationMode === 'campfire' ? styles.subTabActive : ''}`}
                  onClick={() => handleModeChange('campfire')}
                  aria-current={creationMode === 'campfire' ? 'page' : undefined}
                >
                  Campfire
                </button>
                <button
                  type="button"
                  className={`${styles.subTab} ${creationMode === 'manual' ? styles.subTabActive : ''}`}
                  onClick={() => handleModeChange('manual')}
                  aria-current={creationMode === 'manual' ? 'page' : undefined}
                >
                  Manual
                </button>
              </nav>
            )}

            {/* ---- Creation mode content ---- */}
            {creationMode === 'campfire' && <CampfireMode />}
            {creationMode === 'manual' && <ManualMode />}
            {creationMode === 'review' && <ReviewSheet />}
          </>
        ) : (
          <LoadTab />
        )}
      </div>

      {/* ---- Navigation footer ---- */}
      <div className={styles.footer}>
        <button
          type="button"
          className={styles.backButton}
          onClick={() => navigate('/')}
        >
          &larr; Back
        </button>
      </div>
    </div>
  )
}
