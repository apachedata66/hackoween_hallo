
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ComponentType, FormEvent, MutableRefObject, SVGProps } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  CircleCheck,
  Clock3,
  ClipboardCheck,
  Database,
  Eye,
  EyeOff,
  FileText,
  Fingerprint,
  GitBranch,
  CircleHelp,
  LoaderCircle,
  LockKeyhole,
  Menu,
  Network,
  Search,
  ShieldCheck,
  Waypoints,
  X,
} from 'lucide-react'

type IconComponent = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string; strokeWidth?: number | string }>

type DeletionStatus = 'COMPLETE' | 'INCOMPLETE' | 'NOT_APPLICABLE'
type RunState = 'queued' | 'running' | 'complete' | 'failed' | 'review_required'
type FilterStatus = 'ALL' | DeletionStatus

type Health = {
  ready: boolean
  dataset_label: string
  files: Record<string, boolean>
  request_count: number
  sample_count: number
}

type RunCounts = Record<DeletionStatus, number>

type AuditRun = {
  run_id: string
  mode: 'full' | 'samples' | 'saved'
  state: RunState
  stage: string
  processed: number
  total: number
  elapsed_seconds: number
  eta_seconds: number | null
  warning_count: number
  warnings: string[]
  error: string
  counts: RunCounts
  export_ready: boolean
  validation_issues: string[]
  started_at: string
}

type CaseSummary = {
  case_id: string
  deletion_status: DeletionStatus
  requested_at: string
  audit_at: string
  reported_status: string
  step_count: number
  finding_count: number
  recreation_count: number
  email_masked: string
}

type AuditStep = {
  step_no: number
  phase: 'FINDING' | 'REMEDIATION' | 'VERIFICATION'
  system_id: string
  resource_id: string
  operation: string
  state: string
  evidence_id: string
}

type CaseDetail = {
  case_id: string
  deletion_status: DeletionStatus
  request: {
    case_id: string
    email: string
    requested_at: string
    reported_status: string
    reported_at: string
    audit_at: string
    request_text: string
  }
  steps: AuditStep[]
  warnings: string[]
  revealed: boolean
}

type Evidence = {
  evidence_id: string
  kind: string
  source: string
  captured_at: string
  available_at_cutoff: boolean
  excerpt: string
  preview_url?: string | null
}

type CasePage = { cases: CaseSummary[]; total: number }
type SearchPage = { cases: CaseSummary[] }

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

function apiPath(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  return `${API_BASE}${path}`
}

const STATUS: Record<DeletionStatus, { label: string; Icon: IconComponent; explanation: string }> = {
  COMPLETE: {
    label: 'Complete',
    Icon: CheckCircle2,
    explanation: 'The evidence supports the required deletion state at the audit cutoff.',
  },
  INCOMPLETE: {
    label: 'Incomplete',
    Icon: AlertTriangle,
    explanation: 'The audit found a remaining record, exposed identifier, or recreation risk.',
  },
  NOT_APPLICABLE: {
    label: 'Not applicable',
    Icon: CircleHelp,
    explanation: 'The request does not authorize deletion, so no deletion steps are proposed.',
  },
}

const OPERATION_LABELS: Record<string, string> = {
  REPORT_REMAINING_RECORD: 'Record still present',
  REPORT_EXPOSED_PII: 'Direct identifier still exposed',
  REPORT_ACTIVE_DATA_FLOW: 'Active process can recreate data',
  REPORT_RESTORE_RISK: 'Restore path can recreate data',
  DISABLE_DATA_FLOW: 'Disable data flow',
  BLOCK_RESTORE: 'Block restore path',
  DELETE_RECORD: 'Delete record',
  REDACT_RECORD: 'Redact direct identifiers',
  ANONYMIZE_RECORD: 'Anonymize record',
  VERIFY_RECORD_ABSENT: 'Verify record is absent',
  VERIFY_RECORD_PRESENT: 'Verify retained record remains',
  VERIFY_RECORD_REDACTED: 'Verify identifiers are redacted',
  VERIFY_RECORD_ANONYMIZED: 'Verify record is anonymized',
  VERIFY_DATA_FLOW_DISABLED: 'Verify data flow is disabled',
  VERIFY_RESTORE_BLOCKED: 'Verify restore is blocked',
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiPath(path), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = typeof payload?.detail === 'string' ? payload.detail : 'The local service returned an error.'
    throw new Error(detail)
  }
  return payload as T
}

function formatUtc(value: string): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toISOString().replace('T', ' ').replace(/:\d{2}\.\d{3}Z$/, 'Z')
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return 'Calculating'
  const rounded = Math.max(0, Math.round(seconds))
  if (rounded < 60) return `${rounded}s`
  return `${Math.floor(rounded / 60)}m ${String(rounded % 60).padStart(2, '0')}s`
}

function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function StatusChip({ status }: { status: DeletionStatus }) {
  const { label, Icon } = STATUS[status]
  return (
    <span className={`status-chip status-${status.toLowerCase()}`}>
      <Icon size={13} aria-hidden="true" />
      {label}
    </span>
  )
}

function App() {
  const [screen, setScreen] = useState<'landing' | 'workspace'>(() =>
    window.location.pathname === '/workspace' ? 'workspace' : 'landing',
  )
  const [workspaceView, setWorkspaceView] = useState<'overview' | 'cases'>('overview')
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState('')
  const [run, setRun] = useState<AuditRun | null>(null)
  const [runError, setRunError] = useState('')
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [casesLoading, setCasesLoading] = useState(false)
  const [filter, setFilter] = useState<FilterStatus>('ALL')
  const [query, setQuery] = useState('')
  const [searchCases, setSearchCases] = useState<CaseSummary[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [selectedCaseId, setSelectedCaseId] = useState('')
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null)
  const [caseLoading, setCaseLoading] = useState(false)
  const [caseReload, setCaseReload] = useState(0)
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('')
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const [evidenceError, setEvidenceError] = useState('')
  const [starting, setStarting] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [toast, setToast] = useState('')
  const drawerRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const handlePopState = () => {
      setScreen(window.location.pathname === '/workspace' ? 'workspace' : 'landing')
      setSelectedCaseId('')
      setSelectedEvidenceId('')
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    api<Health>('/api/health', { signal: controller.signal })
      .then(setHealth)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setHealthError(error instanceof Error ? error.message : 'Could not check the dataset.')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!run?.run_id || !['queued', 'running'].includes(run.state)) return
    let stopped = false
    let timer = 0
    let controller: AbortController | null = null

    const poll = async () => {
      controller = new AbortController()
      try {
        const latest = await api<AuditRun>(`/api/runs/${run.run_id}`, { signal: controller.signal })
        if (stopped) return
        setRun(latest)
        if (latest.state === 'complete') {
          setCasesLoading(true)
          try {
            const result = await api<CasePage>(`/api/runs/${run.run_id}/cases?offset=0&limit=1000`, {
              signal: controller.signal,
            })
            if (!stopped) {
              setCases(result.cases)
              setFilter('ALL')
              setWorkspaceView('cases')
              setRunError('')
            }
          } catch (error) {
            if (!stopped && !(error instanceof DOMException && error.name === 'AbortError')) {
              setRunError(error instanceof Error ? `Audit finished, but cases could not be loaded: ${error.message}` : 'Audit finished, but cases could not be loaded.')
            }
          } finally {
            if (!stopped) setCasesLoading(false)
          }
          return
        }
        if (latest.state === 'failed' || latest.state === 'review_required') return
      } catch (error) {
        if (!stopped && !(error instanceof DOMException && error.name === 'AbortError')) {
          setRunError(error instanceof Error ? error.message : 'Progress could not be refreshed.')
        }
      }
      if (!stopped) timer = window.setTimeout(poll, 800)
    }

    timer = window.setTimeout(poll, 250)
    return () => {
      stopped = true
      window.clearTimeout(timer)
      controller?.abort()
    }
  }, [run?.run_id])

  useEffect(() => {
    if (!run?.run_id || run.state !== 'complete' || !query.trim()) {
      setSearchCases(null)
      setSearching(false)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setSearching(true)
      api<SearchPage>(`/api/runs/${run.run_id}/search`, {
        method: 'POST',
        body: JSON.stringify({ query: query.trim() }),
        signal: controller.signal,
      })
        .then((result) => setSearchCases(result.cases))
        .catch((error: unknown) => {
          if (!(error instanceof DOMException && error.name === 'AbortError')) {
            setToast(error instanceof Error ? error.message : 'Search could not be completed.')
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearching(false)
        })
    }, 180)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query, run?.run_id, run?.state])

  useEffect(() => {
    if (!selectedCaseId || !run?.run_id) {
      setCaseDetail(null)
      return
    }
    const controller = new AbortController()
    setCaseLoading(true)
    api<CaseDetail>(`/api/runs/${run.run_id}/cases/${selectedCaseId}`, { signal: controller.signal })
      .then(setCaseDetail)
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setToast(error instanceof Error ? error.message : 'Case details could not be loaded.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setCaseLoading(false)
      })
    return () => controller.abort()
  }, [caseReload, selectedCaseId, run?.run_id])

  useEffect(() => {
    const dialog = drawerRef.current
    if (selectedEvidenceId && dialog && !dialog.open) dialog.show()
    if (!selectedEvidenceId && dialog?.open) dialog.close()
    if (!selectedEvidenceId || !selectedCaseId || !run?.run_id) {
      setEvidence(null)
      setEvidenceError('')
      return
    }
    const controller = new AbortController()
    setEvidence(null)
    setEvidenceError('')
    api<Evidence>(
      `/api/runs/${run.run_id}/cases/${selectedCaseId}/evidence/${selectedEvidenceId}`,
      { signal: controller.signal },
    )
      .then(setEvidence)
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setEvidenceError(error instanceof Error ? error.message : 'Evidence could not be loaded.')
        }
      })
    return () => controller.abort()
  }, [selectedEvidenceId, selectedCaseId, run?.run_id])

  useEffect(() => {
    if (!toast) return
    const timeout = window.setTimeout(() => setToast(''), 5000)
    return () => window.clearTimeout(timeout)
  }, [toast])

  const activeRun = run !== null && (run.state === 'queued' || run.state === 'running')
  const visibleCases = useMemo(() => {
    const base = query.trim() ? searchCases ?? [] : cases
    return base.filter((item) => filter === 'ALL' || item.deletion_status === filter)
  }, [cases, filter, query, searchCases])

  async function startRun(mode: 'full' | 'samples' | 'saved') {
    if (activeRun || starting) return
    setStarting(true)
    navigate('workspace')
    setWorkspaceView('overview')
    setRunError('')
    setCases([])
    setSearchCases(null)
    setQuery('')
    setSelectedCaseId('')
    setRun(null)
    setFilter('ALL')
    try {
      const result = await api<AuditRun>('/api/runs', {
        method: 'POST',
        body: JSON.stringify({ mode }),
      })
      setRun(result)
      if (result.state === 'complete') {
        setCasesLoading(true)
        const page = await api<CasePage>(`/api/runs/${result.run_id}/cases?offset=0&limit=1000`)
        setCases(page.cases)
        setWorkspaceView('cases')
      }
    } catch (error) {
      setRunError(error instanceof Error ? error.message : 'The audit could not be started.')
    } finally {
      setCasesLoading(false)
      setStarting(false)
    }
  }

  async function revealIdentifiers() {
    if (!caseDetail || !run) return
    const reveal = !caseDetail.revealed
    setCaseLoading(true)
    try {
      const result = await api<CaseDetail>(
        `/api/runs/${run.run_id}/cases/${caseDetail.case_id}?reveal=${reveal ? 'true' : 'false'}`,
      )
      setCaseDetail(result)
    } catch (error) {
      setToast(error instanceof Error ? error.message : 'The request could not be refreshed.')
    } finally {
      setCaseLoading(false)
    }
  }

  function openCase(caseId: string) {
    setCaseDetail(null)
    setSelectedCaseId(caseId)
    setSelectedEvidenceId('')
    setMenuOpen(false)
  }

  function returnToCases() {
    setSelectedCaseId('')
    setCaseDetail(null)
    setSelectedEvidenceId('')
  }

  function closeEvidence() {
    setSelectedEvidenceId('')
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
  }

  function navigate(next: 'landing' | 'workspace') {
    const path = next === 'workspace' ? '/workspace' : '/'
    if (window.location.pathname !== path) window.history.pushState({}, '', path)
    setScreen(next)
    if (next === 'landing') {
      setSelectedCaseId('')
      setSelectedEvidenceId('')
    }
  }

  const currentPage = selectedCaseId ? 'case' : workspaceView

  if (screen === 'landing') {
    return <LandingPage
      health={health}
      healthError={healthError}
      onOpenWorkspace={() => navigate('workspace')}
      onStartSample={() => { navigate('workspace'); void startRun('samples') }}
    />
  }

  return (
    <div className="app-shell">
      {menuOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
      <aside className={`sidebar${menuOpen ? ' sidebar-open' : ''}`} aria-label="Main navigation">
        <button className="brand brand-button" onClick={() => navigate('landing')} aria-label="Ghost Data home">
          <div className="brand-mark"><ShieldCheck size={19} strokeWidth={1.8} aria-hidden="true" /></div>
          <div><strong>Ghost Data</strong><span>Deletion audit</span></div>
        </button>
        <button className="nav-item home-nav" onClick={() => navigate('landing')}><ArrowLeft size={15} aria-hidden="true" /> Project overview</button>
        <div className="side-label">WORKSPACE</div>
        <button className={`nav-item${currentPage === 'overview' ? ' active' : ''}`} onClick={() => { returnToCases(); setWorkspaceView('overview'); setMenuOpen(false) }}>
          <Activity size={16} aria-hidden="true" /> Overview
        </button>
        <button className={`nav-item${currentPage === 'cases' || currentPage === 'case' ? ' active' : ''}`} onClick={() => { returnToCases(); setWorkspaceView('cases'); setMenuOpen(false) }}>
          <FileText size={16} aria-hidden="true" /> Case register
        </button>
        <div className="side-rule" />
        <div className="side-label">DATASET</div>
        <div className="dataset-card">
          <span className="dataset-dot" aria-hidden="true" />
          <div className="dataset-meta">
            <b title={health?.dataset_label}>{health?.dataset_label || 'Checking dataset'}</b>
            <span>{health?.ready ? `${health.request_count} requests · ${API_BASE ? 'connected' : 'local'}` : 'Readiness check'}</span>
          </div>
          <span className="local-tag"><LockKeyhole size={12} aria-hidden="true" /> {API_BASE ? 'API' : 'LOCAL'}</span>
        </div>
        <div className="side-foot">
          <LockKeyhole size={15} aria-hidden="true" />
          <span>{API_BASE ? 'The configured audit service handles evidence. Recommendations never change source records.' : 'Evidence stays on this machine. Recommendations never change source records.'}</span>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <button className="icon-button menu-button" aria-label="Open navigation" onClick={() => setMenuOpen(true)}>
            <Menu size={18} aria-hidden="true" />
          </button>
          <div className="breadcrumbs"><span>Ghost Data</span><ChevronRight size={13} aria-hidden="true" /><strong>{currentPage === 'case' ? selectedCaseId : currentPage === 'cases' ? 'Case register' : 'Overview'}</strong></div>
          <div className="top-right">
            <span className="local-indicator"><span aria-hidden="true" />{API_BASE ? 'Audit service' : 'Local audit'}</span>
            <button className="help-button" aria-label="How the audit works" aria-expanded={helpOpen} onClick={() => setHelpOpen((value) => !value)}>
              <CircleHelp size={17} aria-hidden="true" />
            </button>
          </div>
        </header>

        <main className="workspace">
          {selectedCaseId ? (
            <CaseWorkspace
              detail={caseDetail}
              loading={caseLoading}
              onBack={returnToCases}
              onReveal={revealIdentifiers}
              onOpenEvidence={setSelectedEvidenceId}
              onRetry={() => setCaseReload((value) => value + 1)}
            />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">PRIVACY OPERATIONS <span className="eyebrow-dot">·</span> LOCAL REVIEW</div>
                  <h1>{currentPage === 'cases' ? 'Case register' : 'Deletion audit workspace'}</h1>
                  <p className="muted">Check what remains at each request’s audit time, and review the evidence behind every step.</p>
                </div>
                {run?.export_ready && <a className="quiet-button" href={apiPath(`/api/runs/${run.run_id}/output`)}><ArrowDownToLine size={14} aria-hidden="true" /> Download CSV</a>}
              </div>

              {helpOpen && <div className="panel help-panel" role="region" aria-label="How the audit works">
                <div className="help-panel-title"><CircleHelp size={16} aria-hidden="true" /><strong>How to review a run</strong><button className="icon-button" aria-label="Close help" onClick={() => setHelpOpen(false)}><X size={16} /></button></div>
                <ol><li>Start with the public sample to see the workflow.</li><li>Open a case and inspect the evidence available by its cutoff.</li><li>Download a CSV only after every case passes validation.</li></ol>
                <p>Reported workflow status is treated as a claim. The audit does not execute the proposed remediation.</p>
              </div>}

              {healthError && <div className="run-error" role="alert"><AlertTriangle size={16} />{healthError}</div>}
              {health && !health.ready && <div className="run-error" role="alert"><AlertTriangle size={16} />The participant dataset is incomplete. Check the required files under dataset/ before starting a run.</div>}

              <section className="panel run-card" aria-labelledby="run-title">
                <div className="run-card-icon"><ShieldCheck size={20} aria-hidden="true" /></div>
                <div className="run-card-content">
                  <div className="panel-headline"><h2 id="run-title">Run an evidence-backed audit</h2><span className="safe-pill"><LockKeyhole size={12} aria-hidden="true" /> Data stays local</span></div>
                  <p>Resolve current and historical identifiers, check records and recreation risks at each cutoff, then validate the ordered findings and next steps.</p>
                  <div className="run-facts">
                    <span><Database size={14} aria-hidden="true" />{health?.request_count ?? '—'} requests</span>
                    <span><FileText size={14} aria-hidden="true" />{health?.sample_count ?? '—'} public examples</span>
                    <span><LockKeyhole size={14} aria-hidden="true" />No external model calls</span>
                  </div>
                  <div className="run-actions">
                    <button className="primary-button" disabled={!health?.ready || activeRun || starting} onClick={() => startRun('full')}>
                      {starting ? <LoaderCircle className="spin" size={15} /> : <Activity size={15} />}
                      {activeRun ? 'Audit running' : 'Audit all requests'}
                    </button>
                    <button className="secondary-button" disabled={!health?.ready || activeRun || starting} onClick={() => startRun('samples')}>
                      Run public sample
                    </button>
                    <button className="secondary-button" disabled={!health?.ready || activeRun || starting} onClick={() => startRun('saved')}>
                      Open validated output
                    </button>
                  </div>
                  {runError && <div className="inline-warning" role="alert"><AlertTriangle size={14} />{runError}</div>}
                </div>
              </section>

              <RunProgress run={run} loadingCases={casesLoading} />

              {run?.state === 'complete' && <RunSummary run={run} onDownload={() => window.location.assign(apiPath(`/api/runs/${run.run_id}/output`))} />}

              {run?.state === 'review_required' && <div className="panel review-required-panel">
                <div className="review-required-heading"><AlertTriangle size={17} /><strong>Evidence review needed</strong></div>
                <p>The audit withheld the result because at least one case could not be supported with cutoff-eligible resource evidence. Review the listed cases and source files before using an output.</p>
                {run.warnings.length > 0 && <details className="warning-details" open>
                  <summary><AlertTriangle size={13} />{run.warning_count} review messages</summary>
                  <ul>{run.warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul>
                </details>}
              </div>}

              {run?.state === 'failed' && run.error && <div className="run-error" role="alert"><AlertTriangle size={16} />{run.error}</div>}

              {workspaceView === 'cases' && run?.state === 'complete' && <CaseRegister
                cases={visibleCases}
                allCases={cases}
                filter={filter}
                query={query}
                searching={searching}
                onFilter={setFilter}
                onQuery={setQuery}
                onSubmit={handleSearchSubmit}
                onOpenCase={openCase}
              />}
              {workspaceView === 'cases' && run?.state !== 'complete' && <section className="panel cases-unavailable" role="status">
                <strong>Case register is waiting for a validated run</strong>
                <p>{run?.state === 'review_required' ? 'This run needs evidence review before its results can be opened. Load the saved validated output for the presentation, or rerun with OCR configured.' : 'Load the saved validated output or start an audit to enable the status filters and evidence review.'}</p>
                <button className="primary-button" disabled={!health?.ready || activeRun || starting} onClick={() => startRun('saved')}><FileText size={14} aria-hidden="true" /> Open validated output</button>
              </section>}
            </>
          )}
        </main>

        <footer className="footer"><span>Ghost Data · Local deletion audit</span><span>Evidence cutoff is shown in UTC <i>·</i> Recommendations require human review</span></footer>
      </div>

      <EvidenceDrawer
        dialogRef={drawerRef}
        evidence={evidence}
        error={evidenceError}
        evidenceId={selectedEvidenceId}
        onClose={closeEvidence}
      />
      {toast && <div className="toast" role="status" aria-live="polite"><CircleHelp size={15} aria-hidden="true" />{toast}<button aria-label="Dismiss message" onClick={() => setToast('')}><X size={14} /></button></div>}
    </div>
  )
}

function LandingPage({
  health,
  healthError,
  onOpenWorkspace,
  onStartSample,
}: {
  health: Health | null
  healthError: string
  onOpenWorkspace: () => void
  onStartSample: () => void
}) {
  const localService = !API_BASE

  return <div className="landing-shell">
    <header className="landing-nav">
      <a className="landing-brand" href="/" aria-label="Ghost Data home">
        <span className="landing-brand-mark"><ShieldCheck size={19} strokeWidth={1.8} aria-hidden="true" /></span>
        <span><strong>Ghost Data</strong><small>Deletion audit</small></span>
      </a>
      <nav aria-label="Project navigation">
        <a href="#method">Method</a>
        <a href="#deliverable">What it produces</a>
      </nav>
      <button className="landing-nav-action" onClick={onOpenWorkspace}>Open workspace <ArrowUpRight size={14} aria-hidden="true" /></button>
    </header>

    <main>
      <section className="landing-hero">
        <div className="hero-copy">
          <div className="landing-eyebrow"><span className="eyebrow-rule" /> PRIVACY OPERATIONS <span>·</span> EVIDENCE REVIEW</div>
          <h1>A deletion request is a claim.<br /><em>The record is the evidence.</em></h1>
          <p className="hero-intro">Ghost Data traces current and historical identifiers across systems, rebuilds their state at the audit cutoff, and turns the evidence into a reviewable answer.</p>
          <div className="hero-actions">
            <button className="primary-button hero-primary" onClick={onOpenWorkspace}>Open audit workspace <ArrowRight size={15} aria-hidden="true" /></button>
            <button className="hero-text-action" onClick={onStartSample}>Run the 32 public examples <ArrowRight size={14} aria-hidden="true" /></button>
          </div>
          <div className="service-note" role="status">
            <span className={`service-indicator ${health?.ready ? 'is-ready' : ''}`} />
            <span>{health?.ready ? `${health.request_count} requests connected` : healthError ? (localService ? 'Start the local audit service to connect the dataset' : 'The configured audit service is not reachable') : 'Checking the audit service'}</span>
            <span className="service-divider">·</span>
            <span>{localService ? 'Local-first run' : 'Connected audit service'}</span>
          </div>
        </div>

        <div className="hero-visual" aria-label="Audit workflow diagram">
          <div className="visual-caption"><span>THE AUDIT RECORD</span><span>01 — 04</span></div>
          <div className="record-sheet">
            <div className="record-sheet-head">
              <div><span className="field-label">SUBJECT LINKAGE</span><strong>One identity, many traces</strong></div>
              <Fingerprint size={20} strokeWidth={1.5} aria-hidden="true" />
            </div>
            <div className="identity-chain">
              <div className="identity-node"><span className="node-kicker">CURRENT</span><span className="mono">user_id · email · phone</span></div>
              <div className="chain-connector"><GitBranch size={13} aria-hidden="true" /></div>
              <div className="identity-node muted-node"><span className="node-kicker">HISTORICAL</span><span className="mono">prior identifiers</span></div>
            </div>
            <div className="record-rule" />
            <div className="evidence-lanes">
              <div className="evidence-lane"><span className="lane-index">01</span><Database size={15} aria-hidden="true" /><span>Primary & replica stores</span><span className="lane-mark" /></div>
              <div className="evidence-lane"><span className="lane-index">02</span><FileText size={15} aria-hidden="true" /><span>Logs, support & exports</span><span className="lane-mark" /></div>
              <div className="evidence-lane"><span className="lane-index">03</span><Network size={15} aria-hidden="true" /><span>Sync & restore paths</span><span className="lane-mark" /></div>
            </div>
            <div className="cutoff-stamp"><Clock3 size={14} aria-hidden="true" /><span>RECONSTRUCTED AT <b className="mono">audit_at</b></span><span className="stamp-line" /></div>
            <div className="record-sheet-foot"><span>FINDINGS</span><ChevronRight size={12} /><span>REMEDIATION</span><ChevronRight size={12} /><span>VERIFICATION</span></div>
          </div>
          <div className="visual-footnote"><span className="footnote-mark" /> Every conclusion points back to a participant-visible source.</div>
        </div>

        <div className="hero-baseline"><span>GHOST DATA STILL EXISTS</span><span>DELETION AUDIT / 2026</span></div>
      </section>

      <section className="landing-method" id="method">
        <div className="method-heading"><div><div className="landing-eyebrow"><span className="eyebrow-rule" /> A CAREFUL REVIEW, END TO END</div><h2>What happened is more useful<br />than what the workflow said.</h2></div><p>Statuses can say “complete” while replicas, search indexes, backups, or active sync jobs tell a different story.</p></div>
        <div className="method-grid">
          <article className="method-item"><span className="method-number">01</span><div className="method-icon"><Fingerprint size={17} aria-hidden="true" /></div><h3>Resolve the person</h3><p>Follow current and historical identifiers before searching across the evidence set.</p><span className="method-foot">IDENTITY · HISTORY · ALIASES</span></article>
          <article className="method-item"><span className="method-number">02</span><div className="method-icon"><Waypoints size={17} aria-hidden="true" /></div><h3>Rebuild the state</h3><p>Compare records, replicas, activity and evidence using only what existed by the audit cutoff.</p><span className="method-foot">STORES · FLOWS · RESTORES</span></article>
          <article className="method-item"><span className="method-number">03</span><div className="method-icon"><ClipboardCheck size={17} aria-hidden="true" /></div><h3>Show the next step</h3><p>Return ordered findings, policy-aware remediation and checks a reviewer can verify.</p><span className="method-foot">EVIDENCE · POLICY · OUTPUT</span></article>
        </div>
      </section>

      <section className="landing-output" id="deliverable">
        <div className="output-copy"><div className="landing-eyebrow"><span className="eyebrow-rule" /> BUILT FOR AUDITABILITY</div><h2>A clear answer.<br /><em>And the trail behind it.</em></h2><p>Each case is reviewed against the supplied deletion policy. Retention requirements and account tombstones remain in scope, and proposed actions never run against source systems.</p><button className="output-link" onClick={onOpenWorkspace}>Review the workspace <ArrowRight size={14} aria-hidden="true" /></button></div>
        <div className="output-sheet">
          <div className="output-sheet-top"><span>OUTPUT / CSV</span><span className="mono">case_id → result → steps</span></div>
          <div className="output-row"><span className="output-step">01</span><div><strong>Finding</strong><small>What remains, with its evidence source</small></div><BookOpen size={15} aria-hidden="true" /></div>
          <div className="output-row"><span className="output-step">02</span><div><strong>Remediation</strong><small>The complete, ordered policy treatment</small></div><GitBranch size={15} aria-hidden="true" /></div>
          <div className="output-row"><span className="output-step">03</span><div><strong>Verification</strong><small>What must pass after the change</small></div><CircleCheck size={15} aria-hidden="true" /></div>
          <div className="output-sheet-bottom"><span>DETERMINISTIC RUN</span><span>{health?.sample_count ?? 32} PUBLIC EXAMPLES</span></div>
        </div>
      </section>
    </main>

    <footer className="landing-footer"><a className="landing-footer-brand" href="/"><ShieldCheck size={15} aria-hidden="true" /> Ghost Data</a><span>Evidence first. Human review always.</span><button onClick={onOpenWorkspace}>Open workspace <ArrowRight size={13} aria-hidden="true" /></button></footer>
  </div>
}

function RunProgress({ run, loadingCases }: { run: AuditRun | null; loadingCases: boolean }) {
  const state = run?.state ?? 'queued'
  const runTitle = run?.mode === 'saved' ? 'Saved validated output' : run?.mode === 'full' ? 'Full audit run' : 'Public sample run'
  const progress = run && run.total > 0 ? Math.min(100, Math.round((run.processed / run.total) * 100)) : 0
  const active = run?.state === 'queued' || run?.state === 'running'
  const stage = run?.stage || 'Ready when you are'
  const stages = ['Read participant-facing evidence', 'Check evidence and policy', 'Validate output']
  const currentStage = stage.toLowerCase().includes('read')
    ? 0
    : stage.toLowerCase().includes('check')
      ? 1
      : stage.toLowerCase().includes('validat') || stage.toLowerCase().includes('complete')
        ? 2
        : -1

  return (
    <section className={`panel run-progress${active ? ' is-running' : ''}`} aria-labelledby="progress-title">
      <div className="progress-header">
        <div className="progress-icon">{active ? <LoaderCircle className="spin" size={17} aria-hidden="true" /> : run?.state === 'complete' ? <CheckCircle2 size={17} aria-hidden="true" /> : <Clock3 size={17} aria-hidden="true" />}</div>
        <div className="progress-title"><h2 id="progress-title">{run ? runTitle : 'Run activity'}</h2><span>{run ? stage : 'Live case counts, active stage, elapsed time, and evidence warnings will appear here.'}</span></div>
        <span className={`run-state state-${state}`}>{run ? state.replace('_', ' ').toUpperCase() : 'READY'}</span>
      </div>
      <div
        className={`progress-track${active && run?.processed === 0 ? ' is-indeterminate' : ''}`}
        role="progressbar"
        aria-label="Audit request progress"
        aria-valuemin={0}
        aria-valuemax={run?.total || 100}
        aria-valuenow={run?.processed || 0}
        aria-valuetext={run ? `${run.processed} of ${run.total} requests processed` : 'No audit is running'}
      >
        <span style={{ width: `${run && run.total > 0 ? progress : 0}%` }} />
      </div>
      <div className="progress-stats">
        <b>{run ? `${run.processed.toLocaleString()} / ${run.total.toLocaleString()}` : '— / —'} <small>requests</small></b>
        {run && <span><Clock3 size={13} aria-hidden="true" /> {formatDuration(run.elapsed_seconds)} elapsed</span>}
        {active && run && <span><Activity size={13} aria-hidden="true" /> {run.eta_seconds === null ? 'Estimating time' : `About ${formatDuration(run.eta_seconds)} left`}</span>}
        {run && <span><AlertTriangle size={13} aria-hidden="true" /> {run.warning_count} warnings</span>}
        {loadingCases && <span><LoaderCircle className="spin" size={13} aria-hidden="true" /> Loading validated cases</span>}
      </div>
      {run && <ol className="run-stages" aria-label="Audit stages">
        {stages.map((label, index) => {
          const completed = run.state === 'complete' || currentStage > index
          const inProgress = active && currentStage === index
          return <li className={completed ? 'stage-done' : inProgress ? 'stage-active' : ''} key={label}>
            <span className="stage-marker">{completed ? <CheckCircle2 size={13} /> : inProgress ? <LoaderCircle className="spin" size={13} /> : index + 1}</span>{label}
          </li>
        })}
      </ol>}
      {run?.warnings.length ? <details className="warning-details">
        <summary><AlertTriangle size={13} />{run.warning_count} warnings from this run</summary>
        <ul>{run.warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul>
      </details> : null}
      {run?.validation_issues.length ? <details className="warning-details" open>
        <summary><AlertTriangle size={13} />Output validation issues</summary>
        <ul>{run.validation_issues.map((issue, index) => <li key={`${issue}-${index}`}>{issue}</li>)}</ul>
      </details> : null}
    </section>
  )
}

function RunSummary({ run, onDownload }: { run: AuditRun; onDownload: () => void }) {
  return <section className="run-summary panel" aria-label="Validated run summary">
    <div className="run-summary-heading"><div><span className="eyebrow">VALIDATED OUTPUT</span><h2>Audit results are ready</h2></div><button className="primary-button download-button" onClick={onDownload}><ArrowDownToLine size={15} aria-hidden="true" /> Download CSV</button></div>
    <div className="run-totals">
      {(['COMPLETE', 'INCOMPLETE', 'NOT_APPLICABLE'] as DeletionStatus[]).map((status) => <span key={status}><StatusChip status={status} /><b>{run.counts?.[status] ?? 0}</b></span>)}
    </div>
  </section>
}

function CaseRegister({
  cases,
  allCases,
  filter,
  query,
  searching,
  onFilter,
  onQuery,
  onSubmit,
  onOpenCase,
}: {
  cases: CaseSummary[]
  allCases: CaseSummary[]
  filter: FilterStatus
  query: string
  searching: boolean
  onFilter: (value: FilterStatus) => void
  onQuery: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onOpenCase: (caseId: string) => void
}) {
  const tabs: { value: FilterStatus; label: string }[] = [
    { value: 'ALL', label: 'All' },
    { value: 'INCOMPLETE', label: 'Incomplete' },
    { value: 'COMPLETE', label: 'Complete' },
    { value: 'NOT_APPLICABLE', label: 'Not applicable' },
  ]
  const countFor = (status: FilterStatus) => status === 'ALL' ? allCases.length : allCases.filter((item) => item.deletion_status === status).length

  return <section className="cases-section" aria-labelledby="cases-title">
    <div className="cases-heading"><div><div className="eyebrow">AUDIT REGISTER</div><h2 id="cases-title">Cases <span className="count-label">{allCases.length.toLocaleString()}</span></h2></div><span className="subtle">Choose a row to inspect its evidence and steps</span></div>
    <div className="case-toolbar">
      <form className="searchbox" role="search" onSubmit={onSubmit}>
        {searching ? <LoaderCircle className="spin" size={14} aria-hidden="true" /> : <Search size={14} aria-hidden="true" />}
        <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Search case ID or email" aria-label="Search by case ID or email" />
        {query && <button className="clear-search" type="button" aria-label="Clear search" onClick={() => onQuery('')}><X size={13} /></button>}
      </form>
      <div className="filter-group" role="group" aria-label="Filter cases by audit status">
        {tabs.map((tab) => <button key={tab.value} className={filter === tab.value ? 'filter-active' : ''} aria-pressed={filter === tab.value} onClick={() => onFilter(tab.value)}>
          {tab.label}<span className="filter-count">{countFor(tab.value)}</span>
        </button>)}
      </div>
    </div>
    <div className="table-wrap">
      <table>
        <thead><tr><th scope="col">CASE</th><th scope="col">REQUESTED (UTC)</th><th scope="col">AUDIT CUTOFF (UTC)</th><th scope="col">AUDIT STATUS</th><th scope="col" className="number-cell">FINDINGS</th><th scope="col" className="number-cell">RECREATION RISKS</th><th scope="col"><span className="sr-only">Open case</span></th></tr></thead>
        <tbody>
          {cases.map((item) => <tr key={item.case_id} tabIndex={0} aria-label={`Open ${item.case_id}, ${STATUS[item.deletion_status].label}`} onClick={() => onOpenCase(item.case_id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onOpenCase(item.case_id) } }}>
            <td><b>{item.case_id}</b><span className="case-email">{item.email_masked || 'Identity masked'}</span></td>
            <td>{formatUtc(item.requested_at)}</td>
            <td>{formatUtc(item.audit_at)}</td>
            <td><StatusChip status={item.deletion_status} /></td>
            <td className="number-cell">{item.finding_count}</td>
            <td className="number-cell">{item.recreation_count}</td>
            <td><ChevronRight className="row-chevron" size={15} aria-hidden="true" /></td>
          </tr>)}
          {cases.length === 0 && <tr><td className="table-empty" colSpan={7}>{searching ? 'Searching…' : query ? 'No cases match this search.' : 'No cases match this filter.'}</td></tr>}
        </tbody>
      </table>
    </div>
    <div className="table-foot">Showing {cases.length.toLocaleString()} of {allCases.length.toLocaleString()} cases</div>
  </section>
}

function CaseWorkspace({
  detail,
  loading,
  onBack,
  onReveal,
  onOpenEvidence,
  onRetry,
}: {
  detail: CaseDetail | null
  loading: boolean
  onBack: () => void
  onReveal: () => void
  onOpenEvidence: (evidenceId: string) => void
  onRetry: () => void
}) {
  if (loading && !detail) return <div className="case-loading panel" role="status"><LoaderCircle className="spin" size={18} />Loading case evidence…</div>
  if (!detail) return <div className="panel case-load-error" role="alert"><AlertTriangle size={18} /><div><strong>Case details are unavailable</strong><p>Try loading the case again.</p><button className="secondary-button" onClick={onRetry}>Retry</button></div></div>

  const request = detail.request
  const findingCount = detail.steps.filter((step) => step.phase === 'FINDING').length
  const verificationCount = detail.steps.filter((step) => step.phase === 'VERIFICATION').length

  return <>
    <button className="back-link" onClick={onBack}><ArrowLeft size={14} aria-hidden="true" /> Back to case register</button>
    <div className="case-title-row"><div><div className="eyebrow">CASE REVIEW <span className="eyebrow-dot">·</span> AUDITED AT {formatUtc(request.audit_at)}</div><h1>{detail.case_id}</h1></div><StatusChip status={detail.deletion_status} /></div>
    <div className="case-meta-grid">
      <MetaItem label="Requested" value={formatUtc(request.requested_at)} />
      <MetaItem label="Previous workflow claim" value={titleCase(request.reported_status)} />
      <MetaItem label="Audit cutoff" value={formatUtc(request.audit_at)} mono />
      <MetaItem label="Steps" value={`${detail.steps.length} total · ${findingCount} findings · ${verificationCount} checks`} />
    </div>
    <div className="review-grid">
      <div className="review-main">
        <section className="panel request-panel" aria-labelledby="request-heading">
          <div className="panel-head"><div><FileText size={15} aria-hidden="true" /><h2 id="request-heading">Deletion request</h2></div><button className="text-button" onClick={onReveal}>{detail.revealed ? <><EyeOff size={13} aria-hidden="true" /> Mask identifiers</> : <><Eye size={13} aria-hidden="true" /> Reveal identifiers</>}</button></div>
          <div className="request-email"><span className="field-label">Email supplied</span><span className="mono">{request.email || 'Not provided'}</span></div>
          <p className="request-copy">{request.request_text || 'No request text supplied.'}</p>
        </section>

        <section className="panel steps-panel" aria-labelledby="steps-heading">
          <div className="panel-head"><div><Activity size={15} aria-hidden="true" /><h2 id="steps-heading">Evidence-backed action plan</h2></div><span className="subtle">Ordered by phase and operation</span></div>
          {detail.steps.length === 0 ? <div className="empty-steps"><CircleHelp size={15} aria-hidden="true" />No deletion steps are authorized for this request.</div> : <div className="steps-list">
            {detail.steps.map((step) => <article className="step-row" key={`${step.step_no}-${step.phase}-${step.system_id}-${step.resource_id}`}>
              <span className={`step-mark step-${step.phase.toLowerCase()}`}>{String(step.step_no).padStart(2, '0')}</span>
              <div className="step-content">
                <div className="step-top"><span className="step-phase">{step.phase}</span><span className="step-state">{titleCase(step.state)}</span></div>
                <b>{OPERATION_LABELS[step.operation] || titleCase(step.operation)}</b>
                <div className="step-resource"><span className="mono">{step.system_id}</span><span aria-hidden="true">/</span><span className="mono">{step.resource_id}</span></div>
              </div>
              {step.evidence_id ? <button className="evidence-button" onClick={() => onOpenEvidence(step.evidence_id)} aria-label={`Inspect evidence ${step.evidence_id}`}><FileText size={13} aria-hidden="true" /><span className="mono">{step.evidence_id}</span></button> : <span className="future-label">Planned</span>}
            </article>)}
          </div>}
        </section>
      </div>
      <aside className="review-aside" aria-label="Case summary">
        <section className="panel verdict-panel"><span className="field-label">AUDIT VERDICT</span><StatusChip status={detail.deletion_status} /><p>{STATUS[detail.deletion_status].explanation}</p><div className="verdict-facts"><span><AlertTriangle size={13} />{findingCount} findings</span><span><CheckCircle2 size={13} />{verificationCount} verification checks</span></div></section>
        <section className="panel note-panel"><div className="panel-head"><div><CalendarClock size={15} aria-hidden="true" /><h2>Cutoff rule</h2></div></div><p>Only evidence available at or before this case’s cutoff can support its verdict. Activity results and reported workflow statuses remain claims.</p><p className="small-note">The steps describe proposed remediation. They do not change source systems.</p></section>
        {detail.warnings.length > 0 && <section className="panel note-panel"><div className="panel-head"><div><AlertTriangle size={15} /><h2>Review notes</h2></div></div><ul className="case-warnings">{detail.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></section>}
      </aside>
    </div>
  </>
}

function MetaItem({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="meta-item"><span className="field-label">{label}</span><b className={mono ? 'mono' : ''}>{value}</b></div>
}

function EvidenceDrawer({
  dialogRef,
  evidence,
  error,
  evidenceId,
  onClose,
}: {
  dialogRef: MutableRefObject<HTMLDialogElement | null>
  evidence: Evidence | null
  error: string
  evidenceId: string
  onClose: () => void
}) {
  return <dialog className="evidence-drawer" ref={dialogRef} aria-labelledby="evidence-title" onCancel={(event) => { event.preventDefault(); onClose() }} onClose={onClose}>
    <div className="drawer-head"><div><span className="eyebrow">EVIDENCE SOURCE</span><h2 id="evidence-title" className="mono">{evidenceId}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close evidence"><X size={17} /></button></div>
    {!evidence && !error && <div className="drawer-body" role="status"><LoaderCircle className="spin" size={17} /> Loading evidence…</div>}
    {error && <div className="drawer-body" role="alert"><div className="run-error"><AlertTriangle size={15} />{error}</div></div>}
    {evidence && <>
      <div className="drawer-meta">
        <MetaItem label="Source" value={evidence.source || 'Participant evidence'} />
        <MetaItem label="Evidence type" value={evidence.kind || 'Evidence'} />
        <MetaItem label="Captured / event time (UTC)" value={formatUtc(evidence.captured_at)} mono />
        <div className={`cutoff-check ${evidence.available_at_cutoff ? 'cutoff-available' : 'cutoff-unavailable'}`}>
          {evidence.available_at_cutoff ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
          {evidence.available_at_cutoff ? 'Available by this case’s audit cutoff' : 'Captured after the audit cutoff; excluded from the verdict'}
        </div>
      </div>
      <div className="drawer-body"><span className="field-label">Relevant excerpt</span>
        {evidence.excerpt ? <pre>{evidence.excerpt}</pre> : <p>{evidence.available_at_cutoff ? evidence.preview_url ? 'This image has no extracted text. Open the original below to inspect its contents.' : 'No text excerpt is available for this source.' : 'The source is hidden because it was captured after the cutoff.'}</p>}
        {evidence.preview_url && evidence.available_at_cutoff && <details className="evidence-preview-disclosure">
          <summary>Open original image <span>May show direct identifiers</span></summary>
          <img className="evidence-preview" src={apiPath(evidence.preview_url)} alt={`Original source image ${evidence.evidence_id}`} />
        </details>}
        <p>Operational logs and workflow results are labeled as claims. The audit uses direct record observations to establish resource state.</p>
      </div>
    </>}
  </dialog>
}

export default App
