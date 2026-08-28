import { useMemo, useState } from 'react'
import { CHAT_STARTERS } from '../mocks/data'

interface Message {
  role: 'user' | 'assistant'
  text: string
}

function mockReply(input: string): string {
  const q = input.toLowerCase()
  if (q.includes('cve-2024-6387') || q.includes('openssh')) {
    return (
      'Mock RavenX: Finding fnd-1001 is critical on prod-web-01. ' +
      'Trust 0.82 / Risk 86.4 → Decision Service recommends remediate ' +
      '(package_upgrade). Remediation Planner produced plan-5001 with 4 steps ' +
      'and rollback. Next: Simulation (safe) → Approval → Execution → Verification.'
    )
  }
  if (q.includes('open') && (q.includes('high') || q.includes('critical'))) {
    return (
      'Mock RavenX: Open high/critical findings in this prototype:\n' +
      '• OpenSSH CVE-2024-6387 (critical, in_progress)\n' +
      '• Apache path traversal CVE-2021-41773 (critical, open)\n' +
      '• Redis unbound without AUTH (critical, in_progress)\n' +
      '• Exposed .env on prod-api-02 (high, open)'
    )
  }
  if (q.includes('plan') || q.includes('remediation')) {
    return (
      'Mock RavenX: Plan plan-5001 upgrades OpenSSH, restarts sshd, and runs a ' +
      'health check. Estimated ~8 minutes in Tue 02:00–04:00 UTC. ' +
      'Also available: plan-5002 (.env harden) and plan-5003 (Apache patch).'
    )
  }
  if (q.includes('asset') || q.includes('risk')) {
    return (
      'Mock RavenX: Highest-risk open assets right now — legacy-app-01 (risk 92), ' +
      'cache-redis-01 (88.1), prod-web-01 (86.4). Dummy inventory only.'
    )
  }
  return (
    'Mock RavenX: Prototype chat only — no LLMService call. Ask about ' +
    'CVE-2024-6387, open high findings, assets at risk, or remediation plans.'
  )
}

export function ChatPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      text: 'Mock RavenX online. Backend chat is not wired — replies are scripted for demos.',
    },
  ])

  const canSend = useMemo(() => input.trim().length > 0, [input])

  function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return
    setMessages((m) => [
      ...m,
      { role: 'user', text: trimmed },
      { role: 'assistant', text: mockReply(trimmed) },
    ])
    setInput('')
  }

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Chat (RavenX)</h1>
          <p>
            Placeholder for LLMService (DecisionEngine → Context → Prompt →
            Providers). Scripted answers only.
          </p>
        </div>
      </header>

      <section className="panel chat">
        <div>
          <div className="starters">
            {CHAT_STARTERS.map((s) => (
              <button key={s} type="button" className="starter" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
          <div className="chat-log">
            {messages.map((m, i) => (
              <div key={`${m.role}-${i}`} className={`bubble ${m.role}`}>
                {m.text}
              </div>
            ))}
          </div>
        </div>
        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about a finding or plan…"
          />
          <button type="submit" className="btn primary" disabled={!canSend}>
            Send
          </button>
        </form>
      </section>
    </div>
  )
}
