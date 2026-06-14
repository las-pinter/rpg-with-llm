/**
 * ConnectionStatus — shows the current health check state.
 *
 * Renders a colored dot + status text in one of four states:
 * idle, loading (pulsing), success (with latency), or error.
 */

import { useConnectionStore } from '../../stores/connectionStore'
import styles from './ConnectionStatus.module.css'

type StatusState = 'idle' | 'loading' | 'success' | 'error'

/** Derive the current visual state from store values. */
function getStatus(
  checking: boolean,
  healthOk: boolean | null,
): StatusState {
  if (checking) return 'loading'
  if (healthOk === true) return 'success'
  if (healthOk === false) return 'error'
  return 'idle'
}

const DOT_CLASS: Record<StatusState, string> = {
  idle: styles.dotIdle,
  loading: styles.dotLoading,
  success: styles.dotSuccess,
  error: styles.dotError,
}

const STATUS_LABEL: Record<StatusState, string> = {
  idle: 'Not tested',
  loading: 'Testing connection…',
  success: 'Connected',
  error: '', // filled from healthError below
}

export default function ConnectionStatus() {
  const checking = useConnectionStore((state) => state.checking)
  const healthOk = useConnectionStore((state) => state.healthOk)
  const healthError = useConnectionStore((state) => state.healthError)
  const latencyMs = useConnectionStore((state) => state.latencyMs)

  const status = getStatus(checking, healthOk)
  const dotClass = DOT_CLASS[status]

  const statusText =
    status === 'error'
      ? healthError ?? 'Connection failed'
      : STATUS_LABEL[status]

  return (
    <div className={styles.row} role="status">
      <span className={`${styles.dot} ${dotClass}`} aria-hidden="true" />
      <span className={styles.text}>{statusText}</span>
      {status === 'success' && latencyMs !== null && (
        <span className={styles.latency}>{latencyMs}ms</span>
      )}
    </div>
  )
}
