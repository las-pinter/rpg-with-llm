import { useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useGameStore } from '../../stores/gameStore'
import styles from './Layout.module.css'

const NAV_ITEMS = [
  { to: '/', icon: '⚡', label: 'Connection' },
  { to: '/character', icon: '🧙', label: 'Character' },
  { to: '/game', icon: '⚔️', label: 'Game' },
] as const

export default function Layout() {
  const isActive = useGameStore((s) => s.isActive)

  useEffect(() => {
    if (!isActive) return

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
    }

    window.addEventListener('beforeunload', handleBeforeUnload)

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [isActive])

  const handleNavClick = (e: React.MouseEvent, to: string) => {
    if (!isActive) return
    // Only block navigation away from game when a game is active
    if (to === '/' || to === '/character') {
      const leave = window.confirm(
        'Are you sure you want to exit the current game? Your progress will be lost.',
      )
      if (!leave) {
        e.preventDefault()
      }
    }
  }

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <h1>RPG</h1>
          <p className={styles.brandSubtitle}>LLM-Powered</p>
        </div>
        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={(e) => handleNavClick(e, item.to)}
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`
              }
            >
              <span className={styles.navIcon} aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className={styles.main}>
        <div className={styles.content}>
          <Outlet />
        </div>
        <footer className={styles.footer}>
          LLM-Powered RPG &mdash; A tale spun by living language
        </footer>
      </main>
    </div>
  )
}
