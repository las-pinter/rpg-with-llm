import { useNavigate } from 'react-router-dom'

export default function CharacterPage() {
  const navigate = useNavigate()

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      <h1>Character</h1>
      <p className="subtitle">Create or load your adventurer</p>
      <p style={{ marginTop: '1rem', color: '#7a6e5a' }}>
        (Character creation form coming soon)
      </p>
      <div
        style={{
          marginTop: '1rem',
          display: 'flex',
          gap: '0.5rem',
          justifyContent: 'center',
        }}
      >
        <button className="btn" onClick={() => navigate('/')}>
          Back to Connection
        </button>
        <button className="btn btn-primary" onClick={() => navigate('/game')}>
          Continue to Game
        </button>
      </div>
    </div>
  )
}
