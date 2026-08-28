import { useDemo } from '../state/DemoContext'

export function PipelinePage() {
  const { pipeline, advancePipeline, resetDemo } = useDemo()

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Remediation pipeline</h1>
          <p>
            Decision → Plan → Simulation → Approval → Execution → Verification →
            Reporting. Click advance to walk the mock flow (approval may gate
            execution).
          </p>
        </div>
        <div className="row">
          <button type="button" className="btn primary" onClick={advancePipeline}>
            Advance stage
          </button>
          <button type="button" className="btn" onClick={resetDemo}>
            Reset demo
          </button>
        </div>
      </header>

      <section className="panel">
        <div className="pipeline">
          {pipeline.map((step, idx) => (
            <div key={step.stage} className={`pipeline-step ${step.status}`}>
              <div className="step-index">{idx + 1}</div>
              <div>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <strong>{step.label}</strong>
                  <span className={`badge ${step.status}`}>{step.status}</span>
                </div>
                <div className="muted" style={{ marginTop: '0.35rem' }}>
                  {step.detail}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
