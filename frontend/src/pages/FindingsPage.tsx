import { Link } from 'react-router-dom'
import { FINDINGS } from '../mocks/data'

export function FindingsPage() {
  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Security findings</h1>
          <p>
            Mock inventory as if produced by Nuclei → Normalization. Click a
            row to see trust, risk, and decision context.
          </p>
        </div>
      </header>

      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Source</th>
              <th>Severity</th>
              <th>Trust</th>
              <th>Risk</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {FINDINGS.map((f) => (
              <tr key={f.id} className="clickable">
                <td className="mono">
                  <Link to={`/findings/${f.id}`}>{f.id}</Link>
                </td>
                <td>
                  <Link to={`/findings/${f.id}`}>{f.title}</Link>
                  <div className="muted">{f.asset}</div>
                </td>
                <td className="mono">{f.source}</td>
                <td>
                  <span className={`badge ${f.severity}`}>{f.severity}</span>
                </td>
                <td className="mono">{f.trustScore.toFixed(2)}</td>
                <td className="mono">{f.riskScore.toFixed(1)}</td>
                <td className="mono">{f.decision}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
