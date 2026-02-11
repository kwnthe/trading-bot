import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { fetchJobResult, fetchJobStatus, resetJob, setJobId } from '../store/slices/jobSlice'
import { fetchParamSchema } from '../store/slices/paramSchemaSlice'
import { addFavoriteAndPersist, removeFavoriteAndPersist } from '../store/slices/favoritesSlice'
import BacktestChart from '../components/BacktestChart'
import Layout from '../components/Layout'
import Card from '../components/Card'
import Button from '../components/Button'

function safeString(v: any): string {
  if (v === null || v === undefined) return ''
  return String(v)
}

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

export default function JobPage() {
  const { jobId: jobIdParam } = useParams<{ jobId: string }>()
  const dispatch = useAppDispatch()

  const status = useAppSelector((s) => s.job.status)
  const result = useAppSelector((s) => s.job.result)
  const error = useAppSelector((s) => s.job.error)
  const schemaDefs = useAppSelector((s) => s.paramSchema.defs)
  const favorites = useAppSelector((s) => s.favorites.items)

  const [currentSymbol, setCurrentSymbol] = useState<string>('')
  const [chartMountId, setChartMountId] = useState(0)

  const chartPanelRef = useRef<HTMLDivElement | null>(null)
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
    const onFs = () => {
      const fs = Boolean(document.fullscreenElement)
      if (!fs) {
        // Re-mount chart after exiting fullscreen to avoid stale canvas sizing
        // that can persist until navigation.
        setChartMountId((v) => v + 1)
      }
    }
    document.addEventListener('fullscreenchange', onFs)
    onFs()
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

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
    if (!symbols.length) return
    if (!currentSymbol || !symbols.includes(currentSymbol)) setCurrentSymbol(symbols[0])
  }, [symbols, currentSymbol])

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

  const statsEntries = Object.entries(result?.stats || {})

  const paramsEntries = useMemo(() => {
    const p = status?.params
    if (!p) return null
    const sections: Array<{ title: string; entries: Array<[string, any]> }> = []
    if (p.backtest_args && Object.keys(p.backtest_args).length) sections.push({ title: 'Backtest', entries: Object.entries(p.backtest_args) })
    if (p.env_overrides && Object.keys(p.env_overrides).length) sections.push({ title: 'Env overrides', entries: Object.entries(p.env_overrides) })
    if (p.meta && Object.keys(p.meta).length) sections.push({ title: 'Meta', entries: Object.entries(p.meta) })
    return sections
  }, [status?.params])

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

  async function toggleFullscreen() {
    const el = chartPanelRef.current
    try {
      if (!document.fullscreenElement) {
        if (el && el.requestFullscreen) await el.requestFullscreen()
      } else {
        if (document.exitFullscreen) await document.exitFullscreen()
      }
    } catch {
      // ignore
    }
  }

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
      <Card
        title={
          <div className="row">
            <span className={`statusDot ${dotClass}`} />
            <span style={{ fontWeight: 800 }}>Status</span>
            <span className="muted">{statusText}</span>
          </div>
        }
        right={
          <div className="row" style={{ minWidth: 360 }}>
            <select className="select" value={currentSymbol} onChange={(e) => setCurrentSymbol(e.target.value)}>
              {symbols.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <Button
              type="button"
              onClick={toggleFullscreen}
              disabled={!currentSymbol}
              style={{ marginLeft: 'auto' }}
            >
              {'⛶'}
            </Button>
          </div>
        }
      >
        {error ? <div className="muted"><b>Error:</b> {error}</div> : null}
        <div ref={chartPanelRef} className="chartPanel" style={{ height: 520 }}>
          <BacktestChart key={`${currentSymbol}:${chartMountId}`} result={result} symbol={currentSymbol} />
        </div>
      </Card>

      <div style={{ height: 14 }} />

      <div className="split">
        <div>
          {statsEntries.length ? (
            <Card title={<span style={{ fontWeight: 800 }}>Stats</span>}>
              <div className="grid">
                {statsEntries.map(([k, v]) => (
                  <div key={k} className="pill">
                    <b>{k}</b>
                    <span className="muted">{String(v)}</span>
                  </div>
                ))}
              </div>
            </Card>
          ) : (
            <Card title={<span style={{ fontWeight: 800 }}>Stats</span>}>
              <div className="muted">No stats.</div>
            </Card>
          )}

          <div style={{ height: 14 }} />

          <Card title={<span style={{ fontWeight: 800 }}>Parameters</span>}>
            {paramsEntries?.length ? (
              <div style={{ display: 'grid', gap: 12 }}>
                {paramsEntries.map((sec) => (
                  <div key={sec.title}>
                    <div className="muted" style={{ marginBottom: 8 }}>{sec.title}</div>
                    <div className="grid">
                      {sec.entries.map(([k, v]) => (
                        <div key={k} className="pill">
                          <b>{labelByName.get(k) || k}</b>
                          <span className="muted">{fmtValue(v)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="muted">No parameters found for this job.</div>
            )}
          </Card>
        </div>

        <div>
          <Card title={<span style={{ fontWeight: 800 }}>stdout</span>}>
            <div ref={stdoutRef} className="log">{status?.stdout_tail || ''}</div>
          </Card>
          <div style={{ height: 14 }} />
          <Card title={<span style={{ fontWeight: 800 }}>stderr</span>}>
            <div ref={stderrRef} className="log">{status?.stderr_tail || ''}</div>
          </Card>
        </div>
      </div>
    </Layout>
  )
}
