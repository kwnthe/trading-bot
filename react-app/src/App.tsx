import { Navigate, Route, Routes } from 'react-router-dom'

import BacktestFormPage from './pages/BacktestFormPage'
import JobPage from './pages/JobPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<BacktestFormPage />} />
      <Route path="/jobs/:jobId" element={<JobPage />} />
      <Route path="/jobs/:jobId/" element={<JobPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
