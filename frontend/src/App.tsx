import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { ApprovalsPage } from './pages/ApprovalsPage'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { FindingDetailPage } from './pages/FindingDetailPage'
import { FindingsPage } from './pages/FindingsPage'
import { PipelinePage } from './pages/PipelinePage'
import { PlanPage } from './pages/PlanPage'
import { DemoProvider } from './state/DemoContext'

export default function App() {
  return (
    <DemoProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="findings" element={<FindingsPage />} />
            <Route path="findings/:findingId" element={<FindingDetailPage />} />
            <Route path="plans/:planId" element={<PlanPage />} />
            <Route path="pipeline" element={<PipelinePage />} />
            <Route path="approvals" element={<ApprovalsPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DemoProvider>
  )
}
