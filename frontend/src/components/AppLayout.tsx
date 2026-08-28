import { NavLink, Outlet } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/findings', label: 'Findings' },
  { to: '/plans/plan-5001', label: 'Remediation Plan' },
  { to: '/pipeline', label: 'Pipeline' },
  { to: '/approvals', label: 'Approvals' },
  { to: '/chat', label: 'Chat (RavenX)' },
]

export function AppLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">XOLARIS</div>
          <div className="brand-sub">Autonomous remediation control plane</div>
        </div>
        <nav className="nav">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) => (isActive ? 'active' : undefined)}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <strong>Prototype · mock data only</strong>
          <br />
          Not connected to FastAPI yet. Share this folder with the frontend
          engineer — swap mocks for <span className="mono">/api/v1/*</span> later.
        </div>
      </aside>
      <main className="main">
        <div className="banner">
          <strong>Demo mode:</strong> all screens use local mock state. Backend
          engines (Trust → Reporting) remain separate until API wiring.
        </div>
        <Outlet />
      </main>
    </div>
  )
}
