import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { api, sendChat } from './api'
import type { Article, Audit, Knowledge, Result, SoftwareRequest, Source, Stats, System, Ticket } from './api'
import './App.css'

type Screen = 'portal' | 'dashboard' | 'analysis' | 'knowledge'
const screens: { id: Screen; label: string; icon: string; description: string }[] = [
  { id: 'portal', label: 'Employee portal', icon: 'chat', description: 'A little help. A better workday.' },
  { id: 'dashboard', label: 'ITSM dashboard', icon: 'grid', description: 'Every request, with the full picture.' },
  { id: 'analysis', label: 'AI analysis', icon: 'spark', description: 'See the reasoning behind the response.' },
  { id: 'knowledge', label: 'Knowledge base', icon: 'book', description: 'Trusted guidance, one search away.' },
]
const examples = [
  { icon: 'network', title: 'Connect to VPN', text: 'My VPN is not connecting.', hint: 'Report a connection issue' },
  { icon: 'key', title: 'Reset my password', text: 'My password has expired.', hint: 'Try approved demo self-healing' },
  { icon: 'mail', title: 'Troubleshoot Outlook', text: 'How do I troubleshoot Outlook synchronisation?', hint: 'Get guidance with sources' },
  { icon: 'code', title: 'Request software', text: 'I need Visual Studio Code.', hint: 'Explore mock provisioning' },
]
function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    chat: <><path d="M21 11a8 8 0 0 1-8 8H6l-4 3V11a9 9 0 0 1 19 0Z" /><path d="M7 9h10M7 13h6" /></>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
    spark: <><path d="m12 3 2.8 6.2L21 12l-6.2 2.8L12 21l-2.8-6.2L3 12l6.2-2.8L12 3ZM20 2v4M18 4h4" /></>,
    book: <><path d="M12 5C8 2 3 3 3 3v16s5-1 9 2c4-3 9-2 9-2V3s-5-1-9 2v16" /><path d="M6 7h3M15 7h3M6 11h3M15 11h3" /></>,
    network: <><rect x="7" y="2" width="10" height="6" rx="1" /><rect x="2" y="16" width="7" height="5" rx="1" /><rect x="15" y="16" width="7" height="5" rx="1" /><path d="M12 8v4M5 16v-4h14v4" /></>,
    key: <><circle cx="8" cy="8" r="5" /><path d="m12 12 9 9m-4-4 3-3m-6 0 3-3" /></>,
    mail: <><rect x="2" y="4" width="20" height="16" rx="3" /><path d="m3 6 9 7 9-7" /></>,
    code: <path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-14-2 16" />,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    send: <path d="m21 3-7 18-4-7-7-4L21 3ZM10 14 21 3" />,
    shield: <><path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4Z" /><path d="m8 12 3 3 5-6" /></>,
    search: <><circle cx="10" cy="10" r="6" /><path d="m15 15 6 6" /></>,
    refresh: <path d="M20 7A9 9 0 1 0 21 15M20 2v6h-6" />,
    check: <path d="m5 12 4 4L19 6" />,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></>,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    link: <path d="m10 14 4-4M9 16l-2 2a4 4 0 0 1-5-5l5-5a4 4 0 0 1 5 0m0 8a4 4 0 0 0 5 0l5-5a4 4 0 0 0-5-5l-2 2" />,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.chat}</svg>
}
const readable = (value: string) => value.replaceAll('_', ' ').replace(/^./, s => s.toUpperCase())
const stamp = (date: string) => new Date(date).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
function Badge({ status }: { status: string }) {
  return <span className={`badge ${['resolved', 'completed', 'passed', 'validated', 'answered', 'ready', 'connected'].includes(status) ? 'good' : ['failed', 'unavailable'].includes(status) ? 'bad' : 'neutral'}`}><span />{readable(status)}</span>
}
function Empty({ children }: { children: ReactNode }) { return <div className="empty"><Icon name="book" size={28} /><p>{children}</p></div> }
function Sources({ sources }: { sources: Source[] }) {
  return sources.length ? <div className="sources"><p className="eyebrow">Retrieved evidence</p>{sources.map(s => <details key={s.chunk_id}><summary><Icon name="book" size={15} /><span>{s.title}</span><small>{s.article_id} · {s.similarity.toFixed(2)}</small></summary><p>{s.passage}</p><small>Cosine similarity; not a probability. Chunk: {s.chunk_id}</small></details>)}</div> : null
}
function initialScreen(): Screen {
  const value = window.location.hash.slice(1)
  return screens.some(s => s.id === value) ? value as Screen : 'portal'
}

async function fetchWorkspace() {
  return Promise.allSettled([
    api<System>('/api/system'), api<Stats>('/api/dashboard'), api<Ticket[]>('/api/tickets'),
    api<Result[]>('/api/analysis'), api<Audit[]>('/api/audit'), api<SoftwareRequest[]>('/api/requests'), api<Knowledge>('/api/knowledge'),
  ] as const)
}

function App() {
  const [screen, setScreen] = useState<Screen>(initialScreen)
  const [system, setSystem] = useState<System | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [requests, setRequests] = useState<SoftwareRequest[]>([])
  const [results, setResults] = useState<Result[]>([])
  const [audit, setAudit] = useState<Audit[]>([])
  const [knowledge, setKnowledge] = useState<Knowledge | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [pendingMessage, setPendingMessage] = useState('')
  const [chatError, setChatError] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null)
  const [ticketFilter, setTicketFilter] = useState('all')
  const [ticketSearch, setTicketSearch] = useState('')
  const [kbQuery, setKbQuery] = useState('')
  const [kbCategory, setKbCategory] = useState('')
  const [searching, setSearching] = useState(false)
  const [kbError, setKbError] = useState('')
  const [kbSearched, setKbSearched] = useState(false)
  const [openArticle, setOpenArticle] = useState<Article | null>(null)
  const retry = useRef<{ message: string; id: string; escalate: boolean } | null>(null)
  const endOfChat = useRef<HTMLDivElement>(null)
  const composer = useRef<HTMLTextAreaElement>(null)
  const modal = useRef<HTMLElement>(null)

  const applyWorkspace = useCallback((calls: Awaited<ReturnType<typeof fetchWorkspace>>) => {
    const [s, metrics, ts, history, logs, rs, kb] = calls
    if (s.status === 'fulfilled') setSystem(s.value)
    if (metrics.status === 'fulfilled') setStats(metrics.value)
    if (ts.status === 'fulfilled') setTickets(ts.value)
    if (history.status === 'fulfilled') setResults(history.value.slice().reverse())
    if (logs.status === 'fulfilled') setAudit(logs.value)
    if (rs.status === 'fulfilled') setRequests(rs.value)
    if (kb.status === 'fulfilled') setKnowledge(current => current ? { ...kb.value, results: current.results } : kb.value)
    const labels = ['System', 'Metrics', 'Tickets', 'History', 'Audit', 'Requests', 'Knowledge']
    setErrors(calls.flatMap((r, i) => r.status === 'rejected' ? [`${labels[i]}: ${r.reason instanceof Error ? r.reason.message : 'Unavailable'}`] : []))
    setLoading(false); setRefreshing(false)
  }, [])
  const load = useCallback(async () => applyWorkspace(await fetchWorkspace()), [applyWorkspace])
  useEffect(() => {
    let active = true
    void fetchWorkspace().then(data => { if (active) applyWorkspace(data) })
    return () => { active = false }
  }, [applyWorkspace])
  useEffect(() => {
    const changed = () => setScreen(initialScreen())
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  useEffect(() => { endOfChat.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [results.length, sending])
  useEffect(() => {
    const timer = window.setInterval(() => { void api<System>('/api/system').then(setSystem).catch(() => setSystem(null)) }, 30_000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    if (!openArticle && !selectedTicket) return
    const previous = document.activeElement as HTMLElement | null
    const close = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setOpenArticle(null); setSelectedTicket(null) }
      if (e.key === 'Tab') {
        const focusable = modal.current?.querySelectorAll<HTMLElement>('button, a, input, summary, select, [tabindex="0"]')
        if (!focusable?.length) return
        const first = focusable[0], last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    modal.current?.querySelector('button')?.focus()
    document.addEventListener('keydown', close)
    return () => { document.removeEventListener('keydown', close); previous?.focus() }
  }, [openArticle, selectedTicket])

  function navigate(next: Screen) { window.location.hash = next; setScreen(next) }
  async function submit(message = draft, escalate = false) {
    message = message.trim()
    if (message.length < 3 || sending) return
    const requestId = retry.current?.message === message && retry.current.escalate === escalate ? retry.current.id : crypto.randomUUID()
    retry.current = { message, id: requestId, escalate }
    setSending(true); setPendingMessage(message); setChatError(''); setDraft('')
    try {
      const result = await sendChat(message, requestId, escalate)
      setResults(current => [...current.filter(r => r.request_id !== result.request_id), result])
      setSelectedId(result.request_id); retry.current = null
      await load()
    } catch (err) { setChatError(err instanceof Error ? err.message : 'Request failed.'); setDraft(message) }
    finally { setSending(false); setPendingMessage('') }
  }
  async function searchKnowledge(event: FormEvent) {
    event.preventDefault(); setSearching(true); setKbError('')
    try {
      setKnowledge(await api<Knowledge>(`/api/knowledge?q=${encodeURIComponent(kbQuery)}&category=${encodeURIComponent(kbCategory)}`))
      setKbSearched(Boolean(kbQuery.trim()))
    } catch (err) { setKbError(err instanceof Error ? err.message : 'Search failed.') }
    finally { setSearching(false) }
  }
  const selected = results.find(r => r.request_id === selectedId) || results.at(-1)
  const activeScreen = screens.find(s => s.id === screen)!
  const filteredTickets = tickets.filter(t => (ticketFilter === 'all' || t.status === ticketFilter) && `${t.title} ${t.ticket_id}`.toLowerCase().includes(ticketSearch.toLowerCase()))
  const selectedAudit = selected?.ticket ? audit.filter(a => a.ticket_id === selected.ticket!.ticket_id).slice().reverse() : []
  const visibleArticles = (knowledge?.articles || []).filter(a => !kbCategory || a.category === kbCategory)

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#portal" onClick={() => navigate('portal')}><span className="brand-mark"><Icon name="spark" size={23} /></span><span>sorim<span className="brand-dot">.ai</span><small>SERVICE DESK</small></span></a>
      <div className="workspace"><span className="workspace-icon">A</span><div>Avinash's workspace<small>Technical assessment</small></div><span className="workspace-dot" /></div>
      <p className="nav-label">WORKSPACE</p>
      <nav aria-label="Main navigation">{screens.map(s => <button key={s.id} className={`nav-item ${screen === s.id ? 'active' : ''}`} onClick={() => navigate(s.id)} aria-current={screen === s.id ? 'page' : undefined}><Icon name={s.icon} /><span>{s.label}</span>{screen === s.id && <span className="active-dot" />}</button>)}</nav>
      <div className="sidebar-note"><span className="note-icon"><Icon name="shield" /></span><h3>Built on trusted knowledge</h3><p>Grounded answers. Approved actions. A clear audit trail.</p><button onClick={() => navigate('knowledge')}>Explore the knowledge base <Icon name="arrow" size={16} /></button></div>
      <div className="sidebar-footer"><span className="avatar">AV</span><div>Avinash<small>Demo employee · no sign-in</small></div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{activeScreen.label}</strong></div><div className="topbar-right"><span className="environment">LOCAL PROTOTYPE</span><button className={`icon-button ${refreshing ? 'spin' : ''}`} title="Refresh backend data" aria-label="Refresh backend data" disabled={refreshing} onClick={() => { setRefreshing(true); void load() }}><Icon name="refresh" size={17} /></button><span className="avatar small">AV</span></div></header>
      <main className={`page page-${screen}`}>
        <div className="page-heading"><div><p className="eyebrow">{screen === 'portal' ? 'YOUR IT SUPPORT, CONNECTED' : 'SERVICE OPERATIONS'}</p><h1>{activeScreen.label}</h1><p className="subheading">{activeScreen.description}</p></div><div className="system-status"><span className={`status-dot ${system?.database === 'connected' ? 'online' : ''}`} /><span>{system?.database === 'connected' ? 'Atlas connected' : 'Backend / database unavailable'}<small>ServiceNow: {system?.servicenow_mode || 'unavailable'}</small></span></div></div>
        <div className="demo-banner"><Icon name="shield" size={17} /><span><strong>Demo environment.</strong> You are using a fictional employee account. Account recovery and software provisioning change demo records only.</span><span className="demo-tag">MOCK ACTIONS</span></div>
        {loading && <div className="loading-bar" role="status">Connecting to the helpdesk and loading your workspace…</div>}
        {!!errors.length && <div className="error-banner" role="alert"><strong>Some live data is unavailable.</strong><details><summary>View details ({errors.length})</summary>{errors.map(e => <p key={e}>{e}</p>)}</details><button className="text-button" onClick={() => { setRefreshing(true); void load() }}>Retry connection</button></div>}

        {screen === 'portal' && <>
          <section className="welcome"><div><div className="welcome-label"><span>✧</span> KNOWLEDGE + INTELLIGENT AUTOMATION</div><h2>Hi Avinash,<br />let's get you back to work.</h2><p>Ask a question, report an issue or request software.<br />Your assistant connects the right knowledge to the right next step.</p></div><div className="welcome-visual" aria-hidden="true"><span className="orbit orbit-one" /><span className="orbit orbit-two" /><div className="visual-core"><Icon name="spark" size={45} /></div><span className="float-icon one"><Icon name="book" size={21} /></span><span className="float-icon two"><Icon name="shield" size={21} /></span><span className="float-icon three"><Icon name="network" size={21} /></span></div></section>
          <div className="section-title"><h2>What can we help with?</h2><span>Choose a starting point</span></div>
          <div className="quick-actions">{examples.map(e => <button key={e.title} onClick={() => { setDraft(e.text); composer.current?.focus() }} disabled={sending}><span className={`action-icon ${e.icon}`}><Icon name={e.icon} /></span><strong>{e.title}</strong><small>{e.hint}</small><span className="card-arrow"><Icon name="arrow" size={16} /></span></button>)}</div>
          <div className="portal-columns"><section className="panel chat-panel" aria-label="IT assistant"><div className="panel-header"><div className="assistant-title"><span className="assistant-icon"><Icon name="spark" size={19} /></span><div><h2>Your IT assistant</h2><small>Powered by local Qwen + approved knowledge</small></div></div><Badge status={system?.ai.status || 'unavailable'} /></div>
            <div className="chat-messages" aria-live="polite" aria-busy={sending}>
              {!results.length && <div className="greeting"><span className="assistant-icon"><Icon name="spark" size={20} /></span><div><strong>A good place to start.</strong><p>Tell me what's happening. I'll look for trusted guidance, create an incident when needed, or run an approved demo workflow.</p><small>Try “My VPN is not connecting.”</small></div></div>}
              {results.slice(-12).map(r => <div className="conversation" key={r.request_id}><div className="user-message"><span>You · {stamp(r.created_at)}</span><p>{r.message}</p></div><div className="assistant-message"><div className="response-heading"><span className="assistant-icon"><Icon name="spark" size={16} /></span><strong>IT assistant</strong><Badge status={r.status} /></div><p className="answer-text">{r.answer}</p>{r.ticket && <div className="ticket-reference"><Icon name="link" size={16} /><span>{r.ticket.ticket_id}<small>{r.ticket.servicenow ? `${r.ticket.servicenow.number} · ServiceNow ${r.ticket.servicenow.mode}` : 'ServiceNow reference not confirmed'}</small></span><Badge status={r.ticket.status} /></div>}<Sources sources={r.sources} />{!!r.warnings.length && <div className="inline-warning">{r.warnings.join(' ')}</div>}<div className="response-actions"><button className="text-button" onClick={() => { setSelectedId(r.request_id); navigate('analysis') }}>View AI analysis <Icon name="arrow" size={14} /></button>{!r.ticket && <button className="secondary small-button" disabled={sending} onClick={() => void submit(r.message, true)}>Escalate to helpdesk</button>}</div></div></div>)}
              {sending && <div className="pending"><div className="user-message"><span>You</span><p>{pendingMessage}</p></div><p className="thinking"><span /><span /><span />Searching knowledge and running the workflow…</p><small>Local inference can take a minute. Keep this window open.</small></div>}
              <div ref={endOfChat} />
            </div>
            {chatError && <div className="inline-warning" role="alert">{chatError} Retry uses the same request ID to avoid duplicate actions.</div>}
            <form className="composer" onSubmit={e => { e.preventDefault(); void submit() }}><label className="sr-only" htmlFor="message">Describe your IT issue</label><textarea id="message" ref={composer} value={draft} maxLength={2000} disabled={sending} onChange={e => setDraft(e.target.value)} placeholder="Describe your issue or ask an IT question…" rows={2} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void submit() } }} /><div className="composer-footer"><span><Icon name="shield" size={13} /> Don't include passwords or verification codes.</span><button className="send-button" disabled={sending || draft.trim().length < 3} type="submit" aria-label="Send message"><Icon name="send" size={18} /></button></div></form>
          </section><aside className="portal-aside"><section className="panel journey"><p className="eyebrow">FROM QUESTION TO RESOLUTION</p><h3>More than an answer.</h3>{[{ n: '01', title: 'Understand the request', text: 'Intent, impact and priority, with explicit business rules.' }, { n: '02', title: 'Find trusted guidance', text: 'Semantic search across approved support articles.' }, { n: '03', title: 'Take the right next step', text: 'A ticket, a service request or an allowlisted demo action.' }].map(item => <div className="journey-step" key={item.n}><span>{item.n}</span><div><strong>{item.title}</strong><p>{item.text}</p></div></div>)}<div className="journey-footer"><Icon name="shield" size={16} /><span>Low confidence? A human takes over.</span></div></section><section className="runtime-card"><span className="eyebrow">RUNNING LOCALLY</span><h3>Your data. Your models.</h3><dl><div><dt>Language model</dt><dd>Qwen 2.5 · 1.5B</dd></div><div><dt>Retrieval</dt><dd>MiniLM + Chroma</dd></div><div><dt>Approved articles</dt><dd>{knowledge?.articles.length ?? '—'} articles / {system?.ai.chunks ?? '—'} chunks</dd></div><div><dt>Model status</dt><dd>{readable(system?.ai.status || 'unavailable')}</dd></div></dl>{system?.ai.error && <p className="inline-warning">{system.ai.error}</p>}</section></aside></div>
        </>}

        {screen === 'dashboard' && <>
          <div className="metrics">{[{ label: 'Total tickets', value: stats?.total, icon: 'grid', note: 'Includes existing records' }, { label: 'Open tickets', value: stats?.open, icon: 'clock', note: 'Awaiting resolution' }, { label: 'AI resolved', value: stats?.ai_resolved, icon: 'spark', note: 'Validated demo recovery' }, { label: 'Escalated', value: stats?.escalated, icon: 'arrow', note: 'Human review required' }].map(m => <section className="panel metric" key={m.label}><span className="metric-icon"><Icon name={m.icon} /></span><p>{m.label}</p><strong>{m.value ?? '—'}</strong><small>{m.note}</small></section>)}</div>
          <section className="panel"><div className="panel-header"><div><h2>Ticket queue</h2><small>Latest 50 records from MongoDB Atlas</small></div><span className="live-label"><span className="status-dot online" />Live backend data</span></div><div className="table-tools"><div className="filter-tabs">{['all', 'open', 'resolved', 'escalated', 'failed'].map(f => <button key={f} className={ticketFilter === f ? 'chosen' : ''} onClick={() => setTicketFilter(f)}>{readable(f)}</button>)}</div><label className="search-small"><Icon name="search" size={16} /><input aria-label="Search tickets" value={ticketSearch} onChange={e => setTicketSearch(e.target.value)} placeholder="Search tickets…" /></label></div><div className="table-scroll"><table><thead><tr><th>Ticket / subject</th><th>Category</th><th>Priority</th><th>Status</th><th>ServiceNow</th><th>Created</th></tr></thead><tbody>{filteredTickets.map(t => <tr key={t.ticket_id}><td><button className="ticket-link" onClick={() => setSelectedTicket(t)}><span>{t.ticket_id}</span><strong>{t.title}</strong></button><small>{t.is_demo ? 'Demo workflow' : 'Existing / manual record'}</small></td><td>{t.analysis?.subcategory || 'Unclassified'}</td><td><span className={`priority ${t.analysis?.priority === 'P1' ? 'urgent' : ''}`}>{t.analysis?.priority || '—'}</span></td><td><Badge status={t.status} /></td><td>{t.servicenow ? <><span className="mono">{t.servicenow.number}</span><small>{t.servicenow.mode}</small></> : 'No linked record'}</td><td className="nowrap">{stamp(t.created_at)}</td></tr>)}</tbody></table></div>{!filteredTickets.length && <Empty>{loading ? 'Loading tickets…' : 'No tickets match this view. Submit an issue from the employee portal.'}</Empty>}</section>
          <div className="dashboard-bottom"><section className="panel"><div className="panel-header"><div><h2>Software requests</h2><small>Approved catalogue · mock provisioning</small></div><span className="count-tag">{stats?.software_requests ?? '—'}</span></div>{requests.length ? requests.map(r => <div className="software-row" key={r.request_id}><span className="action-icon code"><Icon name="code" /></span><div><strong>{r.software}</strong><small>{r.request_id} · {r.device_id}</small></div><Badge status={r.status} /></div>) : <Empty>No software requests yet. Try requesting Visual Studio Code.</Empty>}</section><section className="panel"><div className="panel-header"><h2>Automation activity</h2><Icon name="shield" /></div><div className="automation-summary"><div><strong>{stats?.validated_automations ?? '—'}</strong><span>validated state checks</span></div><div><strong>{stats?.failed ?? '—'}</strong><span>failed workflows</span></div></div><p className="card-footnote">Password reset, account unlock and VS Code provisioning operate on fictional records. Every attempted action is audited.</p><button className="text-button card-footer-button" onClick={() => navigate('analysis')}>Inspect the audit trail <Icon name="arrow" size={15} /></button></section></div>
        </>}

        {screen === 'analysis' && <>
          <section className="panel analysis-selector"><label htmlFor="analysis-select">Inspect a request</label><select id="analysis-select" value={selected?.request_id || ''} onChange={e => setSelectedId(e.target.value)}><option value="" disabled>Choose a submitted message</option>{results.slice().reverse().map(r => <option key={r.request_id} value={r.request_id}>{stamp(r.created_at)} · {r.message.slice(0, 100)}</option>)}</select></section>
          {!selected ? <section className="panel"><Empty>Submit a message in the employee portal to inspect its classification, sources and workflow.</Empty></section> : <>
            <section className="analysis-intro"><div><p className="eyebrow">EMPLOYEE MESSAGE</p><h2>“{selected.message}”</h2><small>{stamp(selected.created_at)} · {selected.request_id}</small></div><Badge status={selected.status} /></section>
            <div className="analysis-columns"><section className="panel"><div className="panel-header"><h2>Understanding & routing</h2><Icon name="spark" /></div>{selected.analysis ? <><dl className="analysis-fields">{[['Intent', readable(selected.analysis.intent)], ['Category / subcategory', `${selected.analysis.category} / ${selected.analysis.subcategory}`], ['Summary', selected.analysis.summary], ['Impact / urgency', `${selected.analysis.impact} / ${selected.analysis.urgency}`], ['Priority', selected.analysis.priority], ['Assignment group', selected.analysis.assignment_group], ['Classifier', selected.analysis.classifier]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><div className="confidence"><div><strong>Retrieval confidence</strong><span>{selected.analysis.confidence.toFixed(2)} / 1.00</span></div><meter min="0" max="1" value={selected.analysis.confidence} aria-label="Heuristic retrieval confidence" /><p>{selected.analysis.confidence_label}. Escalation threshold: {selected.analysis.escalation_threshold.toFixed(2)}. {selected.analysis.escalation_required ? 'Human review required.' : 'Relevant approved evidence found.'}</p></div><details className="policy-details"><summary>Business rules & model proposal</summary><p>{selected.analysis.policy}</p><pre>{JSON.stringify(selected.analysis.model_proposal, null, 2)}</pre></details></> : <Empty>Classification was not completed for this request.</Empty>}</section><section className="panel"><div className="panel-header"><h2>Workflow trace</h2><span className="demo-tag">{selected.integration_mode.toUpperCase()}</span></div><div className="trace">{selected.timeline.map((step, i) => <div className={`trace-step ${step.status}`} key={`${step.stage}-${i}`}><span>{step.status === 'passed' ? <Icon name="check" size={14} /> : i + 1}</span><div><strong>{step.stage}</strong><p>{step.detail}</p></div></div>)}</div>{selected.automation && <div className="state-change"><strong>Validated demo state change</strong><p>{selected.automation.target} · {selected.automation.action}</p><pre>{JSON.stringify({ before: selected.automation.before, after: selected.automation.after }, null, 2)}</pre><small>{selected.automation.message}</small></div>}{selected.ticket?.servicenow && <div className="integration-reference"><Icon name="link" /><div><strong>{selected.ticket.servicenow.number}</strong><small>ServiceNow {selected.ticket.servicenow.mode} · {selected.ticket.servicenow.status}</small></div></div>}</section></div>
            <section className="panel analysis-resolution"><div className="panel-header"><h2>Suggested resolution & evidence</h2><span className="answer-mode">{readable(selected.answer_mode)}</span></div><p className="answer-text">{selected.answer}</p><Sources sources={selected.sources} />{!!selected.warnings.length && <div className="inline-warning">{selected.warnings.join(' ')}</div>}</section>
            <section className="panel"><div className="panel-header"><div><h2>Action audit trail</h2><small>Persisted attempts, outcomes and post-action validations</small></div><span className="count-tag">{selectedAudit.length}</span></div>{selectedAudit.length ? <div className="table-scroll"><table><thead><tr><th>Time</th><th>Action / stage</th><th>Outcome</th><th>Details</th></tr></thead><tbody>{selectedAudit.map(e => <tr key={e.event_id}><td className="nowrap">{stamp(e.created_at)}</td><td>{readable(e.action)}<small>{readable(e.stage)}</small></td><td><Badge status={e.outcome} /></td><td>{e.details}</td></tr>)}</tbody></table></div> : <Empty>No action audit records for this response. Knowledge-only answers do not mutate accounts or devices.</Empty>}</section>
          </>}
        </>}

        {screen === 'knowledge' && <>
          <section className="knowledge-hero"><span className="assistant-icon large"><Icon name="book" size={27} /></span><div><h2>A small library. Answers with evidence.</h2><p>Eight approved support articles, indexed with MiniLM and stored in Chroma.</p></div><span className="knowledge-count">{system?.ai.chunks ?? '—'}<small>searchable chunks</small></span></section>
          <form className="knowledge-search panel" onSubmit={searchKnowledge}><label className="search-main"><Icon name="search" /><input aria-label="Search the knowledge base" value={kbQuery} onChange={e => setKbQuery(e.target.value)} placeholder="Try: email stopped updating or VPN authentication…" maxLength={500} /></label><select aria-label="Knowledge category" value={kbCategory} onChange={e => setKbCategory(e.target.value)}><option value="">All categories</option>{['Network', 'Identity', 'Messaging', 'Hardware', 'Software', 'Access'].map(c => <option key={c}>{c}</option>)}</select><button className="primary" disabled={searching}>{searching ? 'Searching…' : 'Search knowledge'}</button></form>
          {kbError && <div className="error-banner" role="alert">{kbError}</div>}
          {kbSearched && <section className="panel search-results"><div className="panel-header"><div><h2>Semantic retrieval results</h2><small>Cosine similarity · threshold {knowledge?.threshold.toFixed(2)} · scores are not probabilities</small></div><span className="count-tag">{knowledge?.results.length || 0}</span></div>{knowledge?.results.length ? knowledge.results.map(s => <div className="retrieval-result" key={s.chunk_id}><div><span className="article-id">{s.article_id}</span><strong>{s.title}</strong><Badge status={s.similarity >= knowledge.threshold ? 'passed' : 'needs_review'} /><span className="similarity">{s.similarity.toFixed(2)}</span></div><p>{s.passage}</p><small>{s.chunk_id}</small></div>) : <Empty>No matching passages were returned. Try another phrase or escalate to the helpdesk.</Empty>}<button className="text-button card-footer-button" disabled={!kbQuery.trim() || sending} onClick={() => { setDraft(kbQuery); navigate('portal'); setTimeout(() => composer.current?.focus(), 0) }}>Ask the assistant using this question <Icon name="arrow" size={15} /></button></section>}
          <div className="section-title"><h2>Approved support library</h2><span>{visibleArticles.length} articles · reviewed 2 Nov 2026</span></div><div className="article-grid">{visibleArticles.map(a => <button className="panel article-card" key={a.id} onClick={() => setOpenArticle(a)}><div><span className="article-category">{a.category}</span><Icon name="book" /></div><small className="article-id">{a.id}</small><h3>{a.title}</h3><p>{a.content.split('\n\n')[2]?.slice(0, 145)}…</p><div className="article-footer"><span><Icon name="shield" size={13} />Demo approved</span><Icon name="arrow" size={17} /></div></button>)}</div>
        </>}
        <footer className="page-footer"><span>Avinash · Sorim.AI technical assessment</span><span>Local models <span>·</span> MongoDB Atlas <span>·</span> Auditable demo workflows</span></footer>
      </main>
    </div>
    {(openArticle || selectedTicket) && <div className="modal-backdrop" onClick={() => { setOpenArticle(null); setSelectedTicket(null) }}><section className="modal panel" ref={modal} role="dialog" aria-modal="true" aria-label={openArticle?.title || selectedTicket?.title} onClick={e => e.stopPropagation()}><button className="icon-button modal-close" aria-label="Close details" onClick={() => { setOpenArticle(null); setSelectedTicket(null) }}><Icon name="close" /></button>{openArticle ? <><p className="eyebrow">{openArticle.id} / {openArticle.category}</p><h2>{openArticle.title}</h2><small>{openArticle.owner} · Reviewed {openArticle.reviewed_at}</small><div className="article-content">{openArticle.content.split('\n\n').filter(p => !p.startsWith('# ')).map((p, i) => <p key={i}>{p}</p>)}</div><p className="card-footnote">Allowlisted actions: {openArticle.approved_actions.join(', ') || 'Guidance only'}</p></> : selectedTicket && <><p className="eyebrow">{selectedTicket.ticket_id}</p><h2>{selectedTicket.title}</h2><Badge status={selectedTicket.status} /><p className="article-content">{selectedTicket.description}</p><p>{selectedTicket.servicenow ? `${selectedTicket.servicenow.number} · ServiceNow ${selectedTicket.servicenow.mode}` : 'This record has no ServiceNow link.'}</p>{selectedTicket.last_error && <p className="inline-warning">{selectedTicket.last_error}</p>}<Sources sources={selectedTicket.sources || []} />{selectedTicket.chat_id && <button className="primary" onClick={() => { setSelectedId(selectedTicket.chat_id!); setSelectedTicket(null); navigate('analysis') }}>Inspect AI analysis</button>}</>}</section></div>}
  </div>
}
export default App
