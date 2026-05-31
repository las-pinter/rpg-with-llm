import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import ConnectionPage from './pages/ConnectionPage'
import CharacterPage from './pages/CharacterPage'
import GamePage from './pages/GamePage'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<ConnectionPage />} />
        <Route path="/character" element={<CharacterPage />} />
        <Route path="/game" element={<GamePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
