import { Link } from 'react-router-dom'
import { useDemo } from '../state/DemoContext'

export function ApprovalsPage() {
  const { approvals, setApproval } = useDemo()

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Approvals</h1>
          <p>
            Mock Approval Engine inbox. Approving the OpenSSH plan unlocks
            Execution in the pipeline demo.
          </p>
        </div>
      </header>

      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>Approval</th>
              <th>Finding</th>
              <th>Plan</th>
              <th>Risk</th>
              <th>State</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {approvals.map((a) => (
              <tr key={a.id}>
                <td className="mono">{a.id}</td>
                <td>{a.findingTitle}</td>
                <td className="mono">
                  <Link to={`/plans/${a.planId}`}>{a.planId}</Link>
                </td>
                <td className="mono">{a.riskScore.toFixed(1)}</td>
                <td>
                  <span className={`badge ${a.state}`}>{a.state}</span>
                </td>
                <td>
                  <div className="row">
                    <button
                      type="button"
                      className="btn primary"
                      disabled={a.state !== 'pending'}
                      onClick={() => setApproval(a.id, 'approved')}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="btn danger"
                      disabled={a.state !== 'pending'}
                      onClick={() => setApproval(a.id, 'rejected')}
                    >
                      Reject
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
