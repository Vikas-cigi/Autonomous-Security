/** Shared domain shapes for the Xolaris UI prototype (mock only). */

export type Severity = 'critical' | 'high' | 'medium' | 'low'
export type FindingStatus = 'open' | 'in_progress' | 'closed'
export type PipelineStage =
  | 'decision'
  | 'plan'
  | 'simulation'
  | 'approval'
  | 'execution'
  | 'verification'
  | 'reporting'

export type StageStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

export interface Finding {
  id: string
  title: string
  severity: Severity
  status: FindingStatus
  asset: string
  cve: string
  source: string
  discoveredAt: string
  trustScore: number
  riskScore: number
  decision: string
  recommendedAction: string
}

export interface PlanStep {
  sequence: number
  action: string
  target: string
  estimatedSeconds: number
}

export interface RemediationPlan {
  id: string
  findingId: string
  summary: string
  executionType: string
  steps: PlanStep[]
  rollbackSteps: string[]
  impact: string
  estimatedDurationMinutes: number
  changeWindow: string
  costEstimateUsd: number
}

export interface PipelineItem {
  stage: PipelineStage
  label: string
  status: StageStatus
  detail: string
}

export interface ApprovalItem {
  id: string
  planId: string
  findingTitle: string
  requester: string
  state: 'pending' | 'approved' | 'rejected'
  riskScore: number
}

export interface Kpi {
  label: string
  value: string
  hint: string
}
