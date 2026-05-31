import { useNavigate } from 'react-router-dom'

export default function GamePage() {
  const navigate = useNavigate()

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      <h1>Game</h1>
      <p className="subtitle">Your adventure awaits</p>
      <p style={{ marginTop: '1rem', color: '#7a6e5a' }}>(Game view coming soon)</p>
      <button
        className="btn"
        style={{ marginTop: '1rem' }}
        onClick={() => navigate('/character')}
      >
        Back to Character
      </button>
    </div>
  )
}
