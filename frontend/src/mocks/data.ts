/**
 * Mock data for the Xolaris frontend prototype.
 * TODO: replace with /api/v1/* calls when wiring the FastAPI backend.
 */

import type {
  ApprovalItem,
  Finding,
  Kpi,
  PipelineItem,
  RemediationPlan,
} from './types'

export const FINDINGS: Finding[] = [
  {
    id: 'fnd-1001',
    title: 'OpenSSH CVE-2024-6387 on prod-web-01',
    severity: 'critical',
    status: 'in_progress',
    asset: 'prod-web-01',
    cve: 'CVE-2024-6387',
    source: 'nuclei',
    discoveredAt: '2026-07-28T09:14:00Z',
    trustScore: 0.82,
    riskScore: 86.4,
    decision: 'remediate',
    recommendedAction: 'package_upgrade',
  },
  {
    id: 'fnd-1002',
    title: 'Exposed .env via misconfigured nginx',
    severity: 'high',
    status: 'open',
    asset: 'prod-api-02',
    cve: 'N/A',
    source: 'nuclei',
    discoveredAt: '2026-07-29T11:02:00Z',
    trustScore: 0.74,
    riskScore: 71.2,
    decision: 'remediate',
    recommendedAction: 'config_hardening',
  },
  {
    id: 'fnd-1003',
    title: 'Outdated TLS cipher suite on edge LB',
    severity: 'medium',
    status: 'open',
    asset: 'edge-lb-01',
    cve: 'N/A',
    source: 'nuclei',
    discoveredAt: '2026-07-30T08:40:00Z',
    trustScore: 0.61,
    riskScore: 48.0,
    decision: 'monitor',
    recommendedAction: 'investigate',
  },
  {
    id: 'fnd-1004',
    title: 'WordPress XML-RPC amplification',
    severity: 'high',
    status: 'closed',
    asset: 'cms-web-03',
    cve: 'CVE-2023-28121',
    source: 'nuclei',
    discoveredAt: '2026-07-20T16:22:00Z',
    trustScore: 0.88,
    riskScore: 12.5,
    decision: 'remediate',
    recommendedAction: 'config_hardening',
  },
  {
    id: 'fnd-1005',
    title: 'Apache path traversal (CVE-2021-41773)',
    severity: 'critical',
    status: 'open',
    asset: 'legacy-app-01',
    cve: 'CVE-2021-41773',
    source: 'nuclei',
    discoveredAt: '2026-08-01T07:05:00Z',
    trustScore: 0.91,
    riskScore: 92.0,
    decision: 'remediate',
    recommendedAction: 'package_upgrade',
  },
  {
    id: 'fnd-1006',
    title: 'Missing security headers on marketing CDN',
    severity: 'low',
    status: 'open',
    asset: 'cdn-edge-01',
    cve: 'N/A',
    source: 'nuclei',
    discoveredAt: '2026-08-02T10:18:00Z',
    trustScore: 0.55,
    riskScore: 22.0,
    decision: 'monitor',
    recommendedAction: 'investigate',
  },
  {
    id: 'fnd-1007',
    title: 'Redis unbound to 0.0.0.0 without AUTH',
    severity: 'critical',
    status: 'in_progress',
    asset: 'cache-redis-01',
    cve: 'N/A',
    source: 'nuclei',
    discoveredAt: '2026-07-31T14:44:00Z',
    trustScore: 0.86,
    riskScore: 88.1,
    decision: 'remediate',
    recommendedAction: 'config_hardening',
  },
  {
    id: 'fnd-1008',
    title: 'Jenkins script console exposed',
    severity: 'high',
    status: 'closed',
    asset: 'ci-jenkins-01',
    cve: 'N/A',
    source: 'nuclei',
    discoveredAt: '2026-07-15T12:00:00Z',
    trustScore: 0.79,
    riskScore: 18.0,
    decision: 'remediate',
    recommendedAction: 'config_hardening',
  },
]

export const PLANS: Record<string, RemediationPlan> = {
  'plan-5001': {
    id: 'plan-5001',
    findingId: 'fnd-1001',
    summary: 'Upgrade OpenSSH package and restart sshd on prod-web-01',
    executionType: 'package_upgrade',
    steps: [
      {
        sequence: 1,
        action: 'Backup current OpenSSH package state',
        target: 'prod-web-01',
        estimatedSeconds: 20,
      },
      {
        sequence: 2,
        action: 'Upgrade openssh-server to patched version',
        target: 'prod-web-01',
        estimatedSeconds: 90,
      },
      {
        sequence: 3,
        action: 'Restart sshd and verify listener',
        target: 'prod-web-01',
        estimatedSeconds: 30,
      },
      {
        sequence: 4,
        action: 'Post-change health check',
        target: 'prod-web-01',
        estimatedSeconds: 25,
      },
    ],
    rollbackSteps: [
      'Downgrade openssh-server to previous version',
      'Restart sshd',
      'Confirm SSH access restored',
    ],
    impact: 'Brief SSH restart — existing sessions may drop (~30s)',
    estimatedDurationMinutes: 8,
    changeWindow: 'Tue 02:00–04:00 UTC',
    costEstimateUsd: 0,
  },
  'plan-5002': {
    id: 'plan-5002',
    findingId: 'fnd-1002',
    summary: 'Remove public .env exposure and harden nginx location blocks',
    executionType: 'config_hardening',
    steps: [
      {
        sequence: 1,
        action: 'Snapshot current nginx config',
        target: 'prod-api-02',
        estimatedSeconds: 15,
      },
      {
        sequence: 2,
        action: 'Deny access to .env and hidden files',
        target: 'prod-api-02',
        estimatedSeconds: 40,
      },
      {
        sequence: 3,
        action: 'Reload nginx and smoke-test API',
        target: 'prod-api-02',
        estimatedSeconds: 35,
      },
    ],
    rollbackSteps: [
      'Restore previous nginx config from snapshot',
      'Reload nginx',
    ],
    impact: 'API reload only — no expected downtime',
    estimatedDurationMinutes: 5,
    changeWindow: 'Wed 01:00–03:00 UTC',
    costEstimateUsd: 0,
  },
  'plan-5003': {
    id: 'plan-5003',
    findingId: 'fnd-1005',
    summary: 'Patch Apache httpd and disable vulnerable path-handling module path',
    executionType: 'package_upgrade',
    steps: [
      {
        sequence: 1,
        action: 'Drain traffic from legacy-app-01',
        target: 'legacy-app-01',
        estimatedSeconds: 60,
      },
      {
        sequence: 2,
        action: 'Upgrade httpd to patched release',
        target: 'legacy-app-01',
        estimatedSeconds: 120,
      },
      {
        sequence: 3,
        action: 'Restart httpd and reattach to LB',
        target: 'legacy-app-01',
        estimatedSeconds: 45,
      },
    ],
    rollbackSteps: [
      'Reinstall previous httpd package',
      'Restart service and reattach to LB',
    ],
    impact: 'Maintenance window required — ~3 minutes unavailable',
    estimatedDurationMinutes: 15,
    changeWindow: 'Thu 03:00–05:00 UTC',
    costEstimateUsd: 25,
  },
}

/** Primary demo plan (OpenSSH) */
export const PLAN = PLANS['plan-5001']

export const INITIAL_PIPELINE: PipelineItem[] = [
  {
    stage: 'decision',
    label: 'Decision Service',
    status: 'completed',
    detail: 'Decision = remediate (confidence 0.91) for fnd-1001',
  },
  {
    stage: 'plan',
    label: 'Remediation Planner',
    status: 'completed',
    detail: 'Plan plan-5001 generated with 4 steps + rollback',
  },
  {
    stage: 'simulation',
    label: 'Simulation Engine',
    status: 'completed',
    detail: 'safe_to_execute = true · blast radius = low',
  },
  {
    stage: 'approval',
    label: 'Approval Engine',
    status: 'pending',
    detail: 'Waiting for security-manager approval',
  },
  {
    stage: 'execution',
    label: 'Execution Engine',
    status: 'pending',
    detail: 'Blocked until approval',
  },
  {
    stage: 'verification',
    label: 'Verification Engine',
    status: 'pending',
    detail: 'Post-remediation checks not started',
  },
  {
    stage: 'reporting',
    label: 'Reporting & Analytics',
    status: 'pending',
    detail: 'Will aggregate after verification',
  },
]

export const INITIAL_APPROVALS: ApprovalItem[] = [
  {
    id: 'apr-9001',
    planId: 'plan-5001',
    findingTitle: 'OpenSSH CVE-2024-6387 on prod-web-01',
    requester: 'soc-automation',
    state: 'pending',
    riskScore: 86.4,
  },
  {
    id: 'apr-9002',
    planId: 'plan-5002',
    findingTitle: 'Exposed .env via misconfigured nginx',
    requester: 'analyst.j',
    state: 'pending',
    riskScore: 71.2,
  },
  {
    id: 'apr-9003',
    planId: 'plan-5003',
    findingTitle: 'Apache path traversal (CVE-2021-41773)',
    requester: 'soc-automation',
    state: 'pending',
    riskScore: 92.0,
  },
  {
    id: 'apr-8990',
    planId: 'plan-4990',
    findingTitle: 'Jenkins script console exposed',
    requester: 'platform-ops',
    state: 'approved',
    riskScore: 64.0,
  },
]

export interface ActivityEvent {
  id: string
  time: string
  actor: string
  message: string
}

export const ACTIVITY: ActivityEvent[] = [
  {
    id: 'evt-1',
    time: '2026-08-03T10:12:00Z',
    actor: 'nuclei-adapter',
    message: 'Scan completed on 12 assets · 3 new findings ingested',
  },
  {
    id: 'evt-2',
    time: '2026-08-03T10:15:00Z',
    actor: 'trust-engine',
    message: 'Trust scored fnd-1005 = 0.91 (high confidence evidence)',
  },
  {
    id: 'evt-3',
    time: '2026-08-03T10:16:00Z',
    actor: 'risk-engine',
    message: 'Enterprise risk for fnd-1005 = 92.0 (critical asset)',
  },
  {
    id: 'evt-4',
    time: '2026-08-03T10:18:00Z',
    actor: 'decision-service',
    message: 'Decision remediate for fnd-1001 · plan-5001 created',
  },
  {
    id: 'evt-5',
    time: '2026-08-03T10:20:00Z',
    actor: 'simulation-engine',
    message: 'Simulation passed for plan-5001 · safe_to_execute=true',
  },
  {
    id: 'evt-6',
    time: '2026-08-03T09:55:00Z',
    actor: 'verification-engine',
    message: 'Verification passed for cms-web-03 · finding closed',
  },
]

export const ASSETS = [
  { id: 'prod-web-01', env: 'production', criticality: 'high', findings: 1 },
  { id: 'prod-api-02', env: 'production', criticality: 'high', findings: 1 },
  { id: 'edge-lb-01', env: 'production', criticality: 'medium', findings: 1 },
  { id: 'legacy-app-01', env: 'production', criticality: 'critical', findings: 1 },
  { id: 'cache-redis-01', env: 'production', criticality: 'high', findings: 1 },
  { id: 'cms-web-03', env: 'production', criticality: 'medium', findings: 0 },
  { id: 'ci-jenkins-01', env: 'internal', criticality: 'medium', findings: 0 },
  { id: 'cdn-edge-01', env: 'edge', criticality: 'low', findings: 1 },
]

function computeKpis(): Kpi[] {
  const open = FINDINGS.filter((f) => f.status !== 'closed')
  const avgRisk =
    open.reduce((sum, f) => sum + f.riskScore, 0) / Math.max(open.length, 1)
  const pending = INITIAL_APPROVALS.filter((a) => a.state === 'pending').length
  return [
    {
      label: 'Open findings',
      value: String(open.length),
      hint: `${FINDINGS.filter((f) => f.severity === 'critical' && f.status !== 'closed').length} critical open`,
    },
    {
      label: 'Avg risk score',
      value: avgRisk.toFixed(1),
      hint: 'Across open findings',
    },
    {
      label: 'Pending approvals',
      value: String(pending),
      hint: 'Awaiting human decision',
    },
    {
      label: 'Assets in scope',
      value: String(ASSETS.length),
      hint: 'Mock inventory coverage',
    },
    {
      label: 'MTTR (mock)',
      value: '18h',
      hint: 'Mean time to remediate',
    },
    {
      label: 'Verification success',
      value: '91%',
      hint: 'Last 30 days (mock)',
    },
  ]
}

export const DASHBOARD_KPIS: Kpi[] = computeKpis()

export const CHAT_STARTERS = [
  'What should we do about CVE-2024-6387 on prod-web-01?',
  'Summarize open high-severity findings',
  'Explain the remediation plan for OpenSSH',
  'Which assets are most at risk right now?',
]
