import { useNavigate } from 'react-router-dom'

export default function ConnectionPage() {
  const navigate = useNavigate()

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      <h1>LLM-Powered RPG</h1>
      <p className="subtitle">Connection — Configure your LLM provider</p>
      <p style={{ marginTop: '1rem', color: '#7a6e5a' }}>
        (Connection form coming soon)
      </p>
      <button
        className="btn btn-primary"
        style={{ marginTop: '1rem' }}
        onClick={() => navigate('/character')}
      >
        Continue to Character
      </button>
    </div>
  )
}
