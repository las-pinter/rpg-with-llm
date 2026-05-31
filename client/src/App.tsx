import { Routes, Route, Navigate } from 'react-router-dom'
import ConnectionPage from './pages/ConnectionPage'
import CharacterPage from './pages/CharacterPage'
import GamePage from './pages/GamePage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<ConnectionPage />} />
      <Route path="/character" element={<CharacterPage />} />
      <Route path="/game" element={<GamePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
