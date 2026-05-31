import { NavLink, Outlet } from 'react-router-dom'
import styles from './Layout.module.css'

const NAV_ITEMS = [
  { to: '/', icon: '⚡', label: 'Connection' },
  { to: '/character', icon: '🧙', label: 'Character' },
  { to: '/game', icon: '⚔️', label: 'Game' },
] as const

export default function Layout() {
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
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`
              }
            >
              <span className={styles.navIcon}>{item.icon}</span>
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
