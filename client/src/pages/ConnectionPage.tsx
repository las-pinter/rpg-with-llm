/**
 * ConnectionPage — LLM provider configuration form.
 *
 * Composes ProviderSelect, ModelSelector, TestConnectionButton, and
 * AdvancedSection into a single scrollable setup page. "Start Adventure"
 * is disabled until connectionTested === true.
 */

import { useNavigate } from 'react-router-dom'
import { useSettings } from '../hooks/useSettings'
import { useConnectionStore } from '../stores/connectionStore'
import ProviderSelect from '../components/Connection/ProviderSelect'
import ModelSelector from '../components/Connection/ModelSelector'
import TestConnectionButton from '../components/Connection/TestConnectionButton'
import AdvancedSection from '../components/Connection/AdvancedSection'
import styles from './ConnectionPage.module.css'

export default function ConnectionPage() {
  const navigate = useNavigate()
  const { loading, error } = useSettings()
  const connectionTested = useConnectionStore((s) => s.connectionTested)

  return (
    <div className={styles.page}>
      {/* ---- Title ---- */}
      <h1 className={styles.title}>&#x2694;&#xFE0F; Connection Setup</h1>
      <p className={styles.subtitle}>
        Configure your LLM provider to begin the adventure
      </p>
      <hr className={styles.accentBar} />

      {/* ---- Loading banner ---- */}
      {loading && (
        <div className={styles.loadingBanner} role="status">
          <span className={styles.spinner} aria-hidden="true" />
          <span>Loading settings...</span>
        </div>
      )}

      {/* ---- Error banner ---- */}
      {!loading && error && (
        <div className={styles.errorBanner} role="alert">
          <span>&#x26A0;&#xFE0F;</span>
          <span>
            Could not load saved settings. You can still configure manually.
          </span>
        </div>
      )}

      {/* ---- Form sections ---- */}
      <div className={styles.section}>
        <ProviderSelect />
      </div>

      <div className={styles.section}>
        <ModelSelector />
      </div>

      <div className={styles.section}>
        <TestConnectionButton />
      </div>

      <div className={styles.section}>
        <AdvancedSection />
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

        <button
          type="button"
          className={styles.startButton}
          disabled={!connectionTested}
          onClick={() => navigate('/character')}
        >
          Start Adventure &rarr;
        </button>
      </div>
    </div>
  )
}
