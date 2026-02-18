import { useEffect, useMemo, useRef } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'

import Layout from '../components/Layout'
import Card from '../components/Card'
import Button from '../components/Button'
import ChartsContainer from '../components/ChartsContainer'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { fetchLiveSnapshot, fetchLiveStatus, setActiveSessionId, stopLive } from '../store/slices/liveSlice'
import { fetchParamSchema } from '../store/slices/paramSchemaSlice'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'

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

export default function LivePage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  const status = useAppSelector((s) => s.live.status)
  const snapshot = useAppSelector((s) => s.live.snapshot)
  const error = useAppSelector((s) => s.live.error)

  const schemaDefs = useAppSelector((s) => s.paramSchema.defs)

  const stdoutRef = useRef<HTMLDivElement | null>(null)
  const stderrRef = useRef<HTMLDivElement | null>(null)

  const symbols = useMemo(() => Object.keys(snapshot?.symbols || {}), [snapshot])

  const statsEntries = useMemo(() => Object.entries((snapshot as any)?.stats || {}), [snapshot])

  const labelByName = useMemo(() => {
    const m = new Map<string, string>()
    for (const d of schemaDefs || []) m.set(d.name, d.label || d.name)
    return m
  }, [schemaDefs])

  useEffect(() => {
    if (schemaDefs.length) return
    dispatch(fetchParamSchema())
  }, [dispatch, schemaDefs.length])

  const paramsEntries = useMemo(() => {
    const p = (status as any)?.params
    if (!p) return null
    const sections: Array<{ title: string; entries: Array<[string, any]> }> = []
    if (p.backtest_args && Object.keys(p.backtest_args).length) sections.push({ title: 'Backtest', entries: Object.entries(p.backtest_args) })
    if (p.env_overrides && Object.keys(p.env_overrides).length) sections.push({ title: 'Env overrides', entries: Object.entries(p.env_overrides) })
    if (p.meta && Object.keys(p.meta).length) sections.push({ title: 'Meta', entries: Object.entries(p.meta) })
    return sections
  }, [status])

  const flatParams = useMemo(() => {
    const out: Array<[string, any]> = []
    for (const sec of paramsEntries || []) {
      for (const [k, v] of sec.entries) out.push([k, v])
    }
    return out
  }, [paramsEntries])

  const statCols = useMemo(() => {
    const cols = 3
    const out: Array<Array<[string, any]>> = Array.from({ length: cols }, () => [])
    for (let i = 0; i < statsEntries.length; i++) out[i % cols].push(statsEntries[i])
    return out
  }, [statsEntries])

  const paramCols = useMemo(() => {
    const cols = 3
    const out: Array<Array<[string, any]>> = Array.from({ length: cols }, () => [])
    for (let i = 0; i < flatParams.length; i++) out[i % cols].push(flatParams[i])
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

  useEffect(() => {
    if (!sessionId) return
    dispatch(setActiveSessionId(sessionId))
  }, [dispatch, sessionId])

  useEffect(() => {
    if (!sessionId) return
    dispatch(fetchLiveStatus(sessionId))
    dispatch(fetchLiveSnapshot(sessionId))
  }, [dispatch, sessionId])

  const polling = status?.state === 'running' || status?.state === 'queued'
  const canStop = Boolean(sessionId) && (status?.state === 'running' || status?.state === 'queued')
  useInterval(() => {
    if (!sessionId) return
    dispatch(fetchLiveStatus(sessionId))
    dispatch(fetchLiveSnapshot(sessionId))
  }, polling ? 1500 : null)

  function handleStop() {
    if (!sessionId) return
    if (window.confirm('Stop live trading session?')) {
      dispatch(stopLive(sessionId))
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).catch(() => {})
  }

  useEffect(() => {
    const el = stdoutRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [status?.stdout_tail])

  useEffect(() => {
    const el = stderrRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [status?.stderr_tail])

  // Use keyboard shortcuts hook
  useKeyboardShortcuts({
    shortcuts: [
      {
        key: 'b',
        action: () => navigate('/')
      }
    ]
  })

  return (
    <Layout
      title={
        <div className="row">
          <Link className="pill" to="/" style={{ textDecoration: 'none' }}>
            ← Home
          </Link>
          <span style={{ fontWeight: 850 }}>Live</span>
          <span className="muted">{sessionId}</span>
        </div>
      }
      subtitle={status?.state ? `Status: ${status.state}` : undefined}
      right={
        <Button type="button" onClick={handleStop} disabled={!canStop}>
          Stop
        </Button>
      }
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
          <div className="muted">No stats yet.</div>
        )}
      </Card>

      <div style={{ height: 14 }} />

      <Card title={<span style={{ fontWeight: 800 }}>Charts</span>}>
        {error ? (
          <div className="muted">
            <b>Error:</b> {error}
          </div>
        ) : null}

        {symbols.length ? (
          <ChartsContainer
            result={snapshot}
            symbols={symbols}
            headerRight={<span className="muted">{(snapshot as any)?.meta?.timeframe || ''}</span>}
          />
        ) : (
          <div className="muted">No data yet.</div>
        )}
      </Card>

      <div style={{ height: 14 }} />

      <div className="split" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <Card
          title={<span style={{ fontWeight: 800 }}>stdout</span>}
          right={
            <button
              type="button"
              className="iconButton"
              onClick={() => copyToClipboard(status?.stdout_tail || '')}
              title="Copy stdout"
              aria-label="Copy stdout"
            >
              ⎘
            </button>
          }
        >
          <div ref={stdoutRef} className="log">{status?.stdout_tail || ''}</div>
        </Card>
        <Card
          title={<span style={{ fontWeight: 800 }}>stderr</span>}
          right={
            <button
              type="button"
              className="iconButton"
              onClick={() => copyToClipboard(status?.stderr_tail || '')}
              title="Copy stderr"
              aria-label="Copy stderr"
            >
              ⎘
            </button>
          }
        >
          <div ref={stderrRef} className="log">{status?.stderr_tail || ''}</div>
        </Card>
      </div>

      <div style={{ height: 14 }} />

      <Card title={<span style={{ fontWeight: 800 }}>Parameters</span>}>
        {flatParams.length ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1px 1fr 1px 1fr', gap: 14, alignItems: 'stretch' }}>
            {paramCols.map((col, idx) => (
              <div key={idx} style={{ display: 'grid', gap: 10 }}>
                {col.map(([k, v]) => (
                  <div key={k} className="pill">
                    <b>{labelByName.get(k) || k}</b>
                    <span className="muted">{fmtValue(v)}</span>
                  </div>
                ))}
              </div>
            )).flatMap((node, idx) => idx === 0 ? [node] : [<div key={`psep-${idx}`} style={{ width: 1, background: 'rgba(255,255,255,0.12)' }} />, node])}
          </div>
        ) : (
          <div className="muted">No parameters.</div>
        )}
      </Card>
    </Layout>
  )
}
