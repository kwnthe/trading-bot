import { useEffect, useMemo, useRef } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { fetchJobResult, fetchJobStatus, resetJob, setJobId } from '../store/slices/jobSlice'
import { fetchParamSchema } from '../store/slices/paramSchemaSlice'
import { addFavoriteAndPersist, removeFavoriteAndPersist } from '../store/slices/favoritesSlice'
import ChartsContainer from '../components/ChartsContainer'
import Layout from '../components/Layout'
import Card from '../components/Card'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'

function safeString(v: any): string {
  if (v === null || v === undefined) return ''
  return String(v)
}

const btnStyle = {
  background: 'rgba(255, 255, 255, 0.1)',
  border: '1px solid rgba(255, 255, 255, 0.2)',
  cursor: 'pointer',
  padding: '6px 10px',
  borderRadius: '6px',
  color: '#fff',
  display: 'flex',
  alignItems: 'center',
  gap: 4,
  transition: 'background 0.2s, border-color 0.2s',
} as const

function useInterval(callback: () => void, delayMs: number | null) {
  const saved = useRef(callback)
  useEffect(() => {
    saved.current = callback
  }, [callback])

  useEffect(() => {
    if (delayMs === null) return
    const id = window.setInterval(() => saved.current(), delayMs)
    return () => window.clearInterval(id)
  }, [delayMs])
}

export default function BacktestPage() {
  const { jobId: jobIdParam } = useParams<{ jobId: string }>()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  const status = useAppSelector((s) => s.job.status)
  const result = useAppSelector((s) => s.job.result)
  const error = useAppSelector((s) => s.job.error)
  const schemaDefs = useAppSelector((s) => s.paramSchema.defs)
  const favorites = useAppSelector((s) => s.favorites.items)
  const stdoutRef = useRef<HTMLDivElement | null>(null)
  const stderrRef = useRef<HTMLDivElement | null>(null)

  const symbols = useMemo(() => Object.keys(result?.symbols || {}), [result])

  const isFavorite = useMemo(() => {
    if (!jobIdParam) return false
    return favorites.some((f) => f.jobId === jobIdParam)
  }, [favorites, jobIdParam])

  const labelByName = useMemo(() => {
    const m = new Map<string, string>()
    for (const d of schemaDefs || []) m.set(d.name, d.label || d.name)
    return m
  }, [schemaDefs])

  useEffect(() => {
    if (!jobIdParam) return
    dispatch(setJobId(jobIdParam))
    return () => {
      dispatch(resetJob())
    }
  }, [dispatch, jobIdParam])

  useEffect(() => {
    if (schemaDefs.length) return
    dispatch(fetchParamSchema())
  }, [dispatch, schemaDefs.length])

  useEffect(() => {
    if (!jobIdParam) return
    dispatch(fetchJobStatus(jobIdParam))
  }, [dispatch, jobIdParam])

  const polling = (status?.status === 'running' || status?.status === 'queued')
  useInterval(() => {
    if (!jobIdParam) return
    dispatch(fetchJobStatus(jobIdParam))
  }, polling ? 1200 : null)

  useEffect(() => {
    if (!jobIdParam) return
    if (status?.has_result) {
      dispatch(fetchJobResult(jobIdParam))
    }
  }, [dispatch, jobIdParam, status?.has_result])

  useEffect(() => {
    // no-op (kept for possible future hydration work)
  }, [])

  // Use keyboard shortcuts hook
  useKeyboardShortcuts({
    shortcuts: [
      {
        key: 'b',
        action: () => {
          dispatch(resetJob())
          navigate('/')
        }
      }
    ]
  })

  useEffect(() => {
    const el = stdoutRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [status?.stdout])

  useEffect(() => {
    const el = stderrRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [status?.stderr])

  const statsEntries = Object.entries(result?.stats || {})

  const statCols = useMemo(() => {
    const cols = 3
    const out: Array<Array<[string, any]>> = Array.from({ length: cols }, () => [])
    for (let i = 0; i < statsEntries.length; i++) out[i % cols].push(statsEntries[i])
    return out
  }, [statsEntries])

  const paramsEntries = useMemo(() => {
    const p = status?.params
    if (!p) return null
    const sections: Array<{ title: string; entries: Array<[string, any]> }> = []
    if (p.backtest_args && Object.keys(p.backtest_args).length) sections.push({ title: 'Backtest', entries: Object.entries(p.backtest_args) })
    if (p.env_overrides && Object.keys(p.env_overrides).length) sections.push({ title: 'Env overrides', entries: Object.entries(p.env_overrides) })
    if (p.meta && Object.keys(p.meta).length) sections.push({ title: 'Meta', entries: Object.entries(p.meta) })
    return sections
  }, [status?.params])

  const flatParams = useMemo(() => {
    const out: Array<[string, any, string]> = []
    for (const sec of paramsEntries || []) {
      for (const [k, v] of sec.entries) out.push([k, v, sec.title])
    }
    return out
  }, [paramsEntries])

  const paramCols = useMemo(() => {
    const cols = 3
    const out: Array<Array<[string, any, string]>> = Array.from({ length: cols }, () => [])
    for (let i = 0; i < flatParams.length; i++) {
      const [k, v, sectionTitle] = flatParams[i]
      out[i % cols].push([k, v, `${sectionTitle}-${k}`])
    }
    return out
  }, [flatParams])

  function fmtValue(v: any): string {
    if (v === null || v === undefined) return ''
    if (typeof v === 'string') return v
    if (typeof v === 'number' || typeof v === 'boolean') return String(v)
    try {
      return JSON.stringify(v)
    } catch {
      return String(v)
    }
  }

  const st = status?.status || 'unknown'
  const dotClass = st === 'running' ? 'running' : st === 'failed' ? 'failed' : st === 'finished' ? 'finished' : ''
  const statusText = status?.error ? `${st} (${status.error})` : st

  function toggleFavorite() {
    if (!jobIdParam) return
    if (isFavorite) {
      if (!window.confirm('Remove this backtest from favorites?')) return
      dispatch(removeFavoriteAndPersist(jobIdParam))
      return
    }

    const name = window.prompt('Name this favorite:', '')
    if (name === null) return
    const backtestArgs = status?.params?.backtest_args || {}
    dispatch(addFavoriteAndPersist({
      jobId: jobIdParam,
      symbols: safeString(backtestArgs.symbols || ''),
      startDate: safeString(backtestArgs.start_date || ''),
      endDate: safeString(backtestArgs.end_date || ''),
      createdAt: Date.now(),
      name: (name ?? '').trim() || undefined,
    }))
  }

  return (
    <Layout
      title={
        <div className="row">
          <Link
            className="pill"
            to="/"
            onClick={() => {
              dispatch(resetJob())
            }}
          >
            ← Home
          </Link>
          <button
            type="button"
            className="pill"
            onClick={toggleFavorite}
            title={isFavorite ? 'Unfavorite' : 'Favorite'}
            style={{
              color: isFavorite ? '#facc15' : '#9ca3af',
              fontSize: '1.4rem',
              cursor: 'pointer',
              background: 'none',
              border: 'none',
              padding: 4,
            }}
          >
            {isFavorite ? '★' : '☆'}
          </button>
        </div>
      }
      subtitle={jobIdParam ? `Job id: ${jobIdParam}` : undefined}
    >
      <Card title={<span style={{ fontWeight: 800 }}>Stats</span>}>
        {statsEntries.length ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1px 1fr 1px 1fr', gap: 14, alignItems: 'stretch' }}>
            {statCols.map((col, idx) => (
              <div key={idx} style={{ display: 'grid', gap: 10 }}>
                {col.map(([k, v]) => (
                  <div key={k} className="pill">
                    <b>{k}</b>
                    <span className="muted">{String(v)}</span>
                  </div>
                ))}
              </div>
            )).flatMap((node, idx) => idx === 0 ? [node] : [<div key={`sep-${idx}`} style={{ width: 1, background: 'rgba(255,255,255,0.12)' }} />, node])}
          </div>
        ) : (
          <div className="muted">No stats.</div>
        )}
      </Card>

      <div style={{ height: 14 }} />

      <Card
        title={
          <div className="row">
            <span className={`statusDot ${dotClass}`} />
            <span style={{ fontWeight: 800 }}>Status</span>
            <span className="muted">{statusText}</span>
          </div>
        }
      >
        {error ? <div className="muted"><b>Error:</b> {error}</div> : null}
        {symbols.length ? (
          <ChartsContainer
            result={result}
            symbols={symbols}
          />
        ) : (
          <div className="muted">No chart data.</div>
        )}
      </Card>

      <div style={{ height: 14 }} />

      <div className="split" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <Card 
          title={<span style={{ fontWeight: 800 }}>stdout</span>}
          right={
            <button
              onClick={() => navigator.clipboard.writeText(status?.stdout || '')}
              style={btnStyle}
              title="Copy stdout"
              type="button"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            </button>
          }
        >
          <div ref={stdoutRef} className="log">{status?.stdout || ''}</div>
        </Card>
        <Card 
          title={<span style={{ fontWeight: 800 }}>stderr</span>}
          right={
            <button
              onClick={() => navigator.clipboard.writeText(status?.stderr || '')}
              style={btnStyle}
              title="Copy stderr"
              type="button"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            </button>
          }
        >
          <div ref={stderrRef} className="log">{status?.stderr || ''}</div>
        </Card>
      </div>

      <div style={{ height: 14 }} />

      <Card title={<span style={{ fontWeight: 800 }}>Parameters</span>}>
        {flatParams.length ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1px 1fr 1px 1fr', gap: 14, alignItems: 'stretch' }}>
            {paramCols.map((col, idx) => (
              <div key={idx} style={{ display: 'grid', gap: 10 }}>
                {col.map(([k, v, uniqueKey]) => (
                  <div key={uniqueKey} className="pill">
                    <b>{labelByName.get(k) || k}</b>
                    <span className="muted">{fmtValue(v)}</span>
                  </div>
                ))}
              </div>
            )).flatMap((node, idx) => idx === 0 ? [node] : [<div key={`psep-${idx}`} style={{ width: 1, background: 'rgba(255,255,255,0.12)' }} />, node])}
          </div>
        ) : (
          <div className="muted">No parameters found for this job.</div>
        )}
      </Card>
    </Layout>
  )
}
