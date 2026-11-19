import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Repositories } from './pages/Repositories'
import { RepositoryDetail } from './pages/RepositoryDetail'
import { DriftIssues } from './pages/DriftIssues'
import { Analyze } from './pages/Analyze'
import { DocsPage } from './pages/DocsPage'
import { Settings } from './pages/Settings'
import { AutoTracking } from './pages/AutoTracking'
import { LiveNotification } from './components/LiveNotification'

export default function App() {
  return (
    <>
      <LiveNotification />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/repositories" element={<Repositories />} />
          <Route path="/repositories/:id" element={<RepositoryDetail />} />
          <Route path="/drift" element={<DriftIssues />} />
          <Route path="/drift/:id" element={<DriftIssues />} />
          <Route path="/analyze" element={<Analyze />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/auto-tracking" element={<AutoTracking />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </>
  )
}
