import { Link, useParams } from 'react-router-dom'
import { FINDINGS, PLAN } from '../mocks/data'

export function FindingDetailPage() {
  const { findingId } = useParams()
  const finding = FINDINGS.find((f) => f.id === findingId)
  const linkedPlanId =
    findingId === 'fnd-1001'
      ? 'plan-5001'
      : findingId === 'fnd-1002'
        ? 'plan-5002'
        : findingId === 'fnd-1005'
          ? 'plan-5003'
          : null

  if (!finding) {
    return (
      <div>
        <h1>Finding not found</h1>
        <Link to="/findings">Back to findings</Link>
      </div>
    )
  }

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>{finding.title}</h1>
          <p>
            Detail view combining Trust Scoring, Risk Engine, and Decision
            Service outputs (mocked).
          </p>
        </div>
        <span className={`badge ${finding.severity}`}>{finding.severity}</span>
      </header>

      <div className="grid two">
        <section className="panel stack">
          <h2>Finding context</h2>
          <div className="metric-box">
            <div>
              <div className="k">Finding ID</div>
              <div className="v">{finding.id}</div>
            </div>
            <div>
              <div className="k">Asset</div>
              <div className="v">{finding.asset}</div>
            </div>
            <div>
              <div className="k">CVE</div>
              <div className="v">{finding.cve}</div>
            </div>
            <div>
              <div className="k">Source</div>
              <div className="v">{finding.source}</div>
            </div>
            <div>
              <div className="k">Status</div>
              <div className="v">{finding.status}</div>
            </div>
            <div>
              <div className="k">Discovered</div>
              <div className="v">{new Date(finding.discoveredAt).toLocaleString()}</div>
            </div>
          </div>
        </section>

        <section className="panel stack">
          <h2>Scoring & decision</h2>
          <div className="metric-box">
            <div>
              <div className="k">Trust score</div>
              <div className="v">{finding.trustScore.toFixed(2)}</div>
            </div>
            <div>
              <div className="k">Enterprise risk</div>
              <div className="v">{finding.riskScore.toFixed(1)}</div>
            </div>
            <div>
              <div className="k">Decision</div>
              <div className="v">{finding.decision}</div>
            </div>
            <div>
              <div className="k">Recommended action</div>
              <div className="v">{finding.recommendedAction}</div>
            </div>
          </div>
          {linkedPlanId ? (
            <Link className="btn primary" to={`/plans/${linkedPlanId}`}>
              Open remediation plan
            </Link>
          ) : (
            <p className="muted" style={{ margin: 0 }}>
              No remediation plan in this demo for this finding
              {finding.id === PLAN.findingId ? '' : ' yet'}.
            </p>
          )}
        </section>
      </div>
    </div>
  )
}
