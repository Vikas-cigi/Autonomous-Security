import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  INITIAL_APPROVALS,
  INITIAL_PIPELINE,
} from '../mocks/data'
import type { ApprovalItem, PipelineItem, StageStatus } from '../mocks/types'

interface DemoState {
  pipeline: PipelineItem[]
  approvals: ApprovalItem[]
  advancePipeline: () => void
  resetDemo: () => void
  setApproval: (id: string, state: 'approved' | 'rejected') => void
}

const DemoContext = createContext<DemoState | null>(null)

function nextStatus(current: StageStatus): StageStatus {
  if (current === 'pending') return 'running'
  if (current === 'running') return 'completed'
  return current
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const [pipeline, setPipeline] = useState(INITIAL_PIPELINE)
  const [approvals, setApprovals] = useState(INITIAL_APPROVALS)

  const advancePipeline = useCallback(() => {
    setPipeline((prev) => {
      const copy = prev.map((p) => ({ ...p }))
      const runningIdx = copy.findIndex((p) => p.status === 'running')
      if (runningIdx >= 0) {
        copy[runningIdx].status = 'completed'
        copy[runningIdx].detail = `${copy[runningIdx].label} completed (mock)`
        if (runningIdx + 1 < copy.length) {
          copy[runningIdx + 1].status = 'running'
          copy[runningIdx + 1].detail = `${copy[runningIdx + 1].label} in progress (mock)`
        }
        return copy
      }
      const pendingIdx = copy.findIndex((p) => p.status === 'pending')
      if (pendingIdx >= 0) {
        // Approval gate: only auto-start if approval stage already completed
        if (copy[pendingIdx].stage === 'execution') {
          const approval = copy.find((p) => p.stage === 'approval')
          if (approval && approval.status !== 'completed') {
            return copy
          }
        }
        copy[pendingIdx].status = nextStatus(copy[pendingIdx].status)
        if (copy[pendingIdx].status === 'running') {
          copy[pendingIdx].detail = `${copy[pendingIdx].label} in progress (mock)`
        }
      }
      return copy
    })
  }, [])

  const setApproval = useCallback((id: string, state: 'approved' | 'rejected') => {
    setApprovals((prev) =>
      prev.map((a) => (a.id === id ? { ...a, state } : a)),
    )
    if (state === 'approved') {
      setPipeline((prev) =>
        prev.map((p) =>
          p.stage === 'approval'
            ? {
                ...p,
                status: 'completed',
                detail: 'Approved by security-manager (mock)',
              }
            : p.stage === 'execution' && p.status === 'pending'
              ? {
                  ...p,
                  status: 'running',
                  detail: 'Execution authorized — running (mock)',
                }
              : p,
        ),
      )
    }
    if (state === 'rejected') {
      setPipeline((prev) =>
        prev.map((p) =>
          p.stage === 'approval'
            ? {
                ...p,
                status: 'failed',
                detail: 'Rejected — execution blocked (mock)',
              }
            : p,
        ),
      )
    }
  }, [])

  const resetDemo = useCallback(() => {
    setPipeline(INITIAL_PIPELINE)
    setApprovals(INITIAL_APPROVALS)
  }, [])

  const value = useMemo(
    () => ({ pipeline, approvals, advancePipeline, resetDemo, setApproval }),
    [pipeline, approvals, advancePipeline, resetDemo, setApproval],
  )

  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>
}

export function useDemo() {
  const ctx = useContext(DemoContext)
  if (!ctx) throw new Error('useDemo must be used within DemoProvider')
  return ctx
}
