import { Link, useParams } from 'react-router-dom'
import { PLANS } from '../mocks/data'

export function PlanPage() {
  const { planId } = useParams()
  const plan = planId ? PLANS[planId] : undefined

  if (!plan) {
    return (
      <div>
        <h1>Plan not found</h1>
        <p className="muted">Available demo plans:</p>
        <ul>
          {Object.keys(PLANS).map((id) => (
            <li key={id}>
              <Link to={`/plans/${id}`}>{id}</Link>
            </li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Remediation plan</h1>
          <p>
            Output of the Remediation Planner — structured steps, rollback, and
            impact estimates. Does not execute changes.
          </p>
        </div>
        <span className="badge info">{plan.executionType}</span>
      </header>

      <div className="grid two" style={{ marginBottom: '1rem' }}>
        <section className="panel stack">
          <h2>Summary</h2>
          <p style={{ margin: 0 }}>{plan.summary}</p>
          <div className="metric-box">
            <div>
              <div className="k">Plan ID</div>
              <div className="v">{plan.id}</div>
            </div>
            <div>
              <div className="k">Finding</div>
              <div className="v">
                <Link to={`/findings/${plan.findingId}`}>{plan.findingId}</Link>
              </div>
            </div>
            <div>
              <div className="k">Duration</div>
              <div className="v">{plan.estimatedDurationMinutes} min</div>
            </div>
            <div>
              <div className="k">Change window</div>
              <div className="v">{plan.changeWindow}</div>
            </div>
            <div>
              <div className="k">Impact</div>
              <div className="v" style={{ fontFamily: 'inherit', fontSize: '0.9rem' }}>
                {plan.impact}
              </div>
            </div>
            <div>
              <div className="k">Cost estimate</div>
              <div className="v">${plan.costEstimateUsd}</div>
            </div>
          </div>
        </section>

        <section className="panel">
          <h2>Rollback strategy</h2>
          <ol className="stack" style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {plan.rollbackSteps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          <div className="muted" style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
            Other demo plans:{' '}
            {Object.keys(PLANS)
              .filter((id) => id !== plan.id)
              .map((id, i, arr) => (
                <span key={id}>
                  <Link to={`/plans/${id}`}>{id}</Link>
                  {i < arr.length - 1 ? ' · ' : ''}
                </span>
              ))}
          </div>
        </section>
      </div>

      <section className="panel">
        <h2>Execution steps</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Action</th>
              <th>Target</th>
              <th>Est. seconds</th>
            </tr>
          </thead>
          <tbody>
            {plan.steps.map((s) => (
              <tr key={s.sequence}>
                <td className="mono">{s.sequence}</td>
                <td>{s.action}</td>
                <td className="mono">{s.target}</td>
                <td className="mono">{s.estimatedSeconds}s</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="row" style={{ marginTop: '1rem' }}>
          <Link className="btn primary" to="/pipeline">
            View in pipeline
          </Link>
          <Link className="btn" to="/approvals">
            Go to approvals
          </Link>
        </div>
      </section>
    </div>
  )
}
