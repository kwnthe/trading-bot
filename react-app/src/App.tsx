import { Navigate, Route, Routes } from 'react-router-dom'

import BacktestFormPage from './pages/BacktestFormPage'
import BacktestPage from './pages/BacktestPage'
import LivePage from './pages/LivePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<BacktestFormPage />} />
      <Route path="/jobs/:jobId" element={<BacktestPage />} />
      <Route path="/jobs/:jobId/" element={<BacktestPage />} />
      <Route path="/live/:sessionId" element={<LivePage />} />
      <Route path="/live/:sessionId/" element={<LivePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
