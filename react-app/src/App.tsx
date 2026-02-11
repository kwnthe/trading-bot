import { Navigate, Route, Routes } from 'react-router-dom'

import BacktestFormPage from './pages/BacktestFormPage'
import JobPage from './pages/JobPage'
import LivePage from './pages/LivePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<BacktestFormPage />} />
      <Route path="/jobs/:jobId" element={<JobPage />} />
      <Route path="/jobs/:jobId/" element={<JobPage />} />
      <Route path="/live/:sessionId" element={<LivePage />} />
      <Route path="/live/:sessionId/" element={<LivePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
