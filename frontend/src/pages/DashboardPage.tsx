import { Link } from 'react-router-dom'
import { ACTIVITY, ASSETS, DASHBOARD_KPIS, FINDINGS, PLANS } from '../mocks/data'
import { useDemo } from '../state/DemoContext'

export function DashboardPage() {
  const { approvals, pipeline } = useDemo()
  const open = FINDINGS.filter((f) => f.status !== 'closed')
  const pendingApprovals = approvals.filter((a) => a.state === 'pending').length
  const nextStage = pipeline.find(
    (p) => p.status === 'running' || p.status === 'pending',
  )
  const criticalOpen = open.filter((f) => f.severity === 'critical')

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Operations dashboard</h1>
          <p>
            Enterprise visibility across findings, risk, approvals, and the
            remediation control plane — prototype with dummy data.
          </p>
        </div>
        <Link className="btn primary" to="/findings">
          Browse findings
        </Link>
      </header>

      <div className="grid kpi" style={{ marginBottom: '1rem' }}>
        {DASHBOARD_KPIS.map((k) => (
          <div key={k.label} className="kpi-card">
            <div className="value">{k.value}</div>
            <div className="label">{k.label}</div>
            <div className="hint">{k.hint}</div>
          </div>
        ))}
      </div>

      <div className="grid two" style={{ marginBottom: '1rem' }}>
        <section className="panel">
          <h2>Active findings ({open.length})</h2>
          <table>
            <thead>
              <tr>
                <th>Finding</th>
                <th>Severity</th>
                <th>Risk</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {open.map((f) => (
                <tr key={f.id}>
                  <td>
                    <Link to={`/findings/${f.id}`}>{f.title}</Link>
                    <div className="muted mono">{f.asset}</div>
                  </td>
                  <td>
                    <span className={`badge ${f.severity}`}>{f.severity}</span>
                  </td>
                  <td className="mono">{f.riskScore.toFixed(1)}</td>
                  <td>
                    <span className={`badge ${f.status}`}>{f.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="panel stack">
          <h2>Control-plane pulse</h2>
          <div className="metric-box">
            <div>
              <div className="k">Pending approvals</div>
              <div className="v">{pendingApprovals}</div>
            </div>
            <div>
              <div className="k">Critical open</div>
              <div className="v">{criticalOpen.length}</div>
            </div>
            <div>
              <div className="k">Demo plans</div>
              <div className="v">{Object.keys(PLANS).length}</div>
            </div>
            <div>
              <div className="k">Next stage</div>
              <div className="v" style={{ fontSize: '0.95rem' }}>
                {nextStage?.label ?? 'Idle'}
              </div>
            </div>
          </div>
          <p className="muted" style={{ margin: 0 }}>
            {nextStage?.detail ?? 'Pipeline complete in this demo session.'}
          </p>
          <div className="row">
            <Link className="btn primary" to="/pipeline">
              Open pipeline
            </Link>
            <Link className="btn" to="/approvals">
              Review approvals
            </Link>
            <Link className="btn" to="/plans/plan-5001">
              Sample plan
            </Link>
          </div>
        </section>
      </div>

      <div className="grid two">
        <section className="panel">
          <h2>Recent activity</h2>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Event</th>
              </tr>
            </thead>
            <tbody>
              {ACTIVITY.map((e) => (
                <tr key={e.id}>
                  <td className="mono muted">
                    {new Date(e.time).toLocaleString()}
                  </td>
                  <td className="mono">{e.actor}</td>
                  <td>{e.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="panel">
          <h2>Assets ({ASSETS.length})</h2>
          <table>
            <thead>
              <tr>
                <th>Asset</th>
                <th>Env</th>
                <th>Criticality</th>
                <th>Open findings</th>
              </tr>
            </thead>
            <tbody>
              {ASSETS.map((a) => (
                <tr key={a.id}>
                  <td className="mono">{a.id}</td>
                  <td>{a.env}</td>
                  <td>
                    <span
                      className={`badge ${
                        a.criticality === 'critical'
                          ? 'critical'
                          : a.criticality === 'high'
                            ? 'high'
                            : a.criticality === 'medium'
                              ? 'medium'
                              : 'low'
                      }`}
                    >
                      {a.criticality}
                    </span>
                  </td>
                  <td className="mono">{a.findings}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  )
}
