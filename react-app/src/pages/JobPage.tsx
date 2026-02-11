import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { fetchJobResult, fetchJobStatus, resetJob, setJobId } from '../store/slices/jobSlice'
import BacktestChart from '../components/BacktestChart'
import Layout from '../components/Layout'
import Card from '../components/Card'
import Button from '../components/Button'

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

  const [currentSymbol, setCurrentSymbol] = useState<string>('')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [chartMountId, setChartMountId] = useState(0)

  const chartPanelRef = useRef<HTMLDivElement | null>(null)

  const symbols = useMemo(() => Object.keys(result?.symbols || {}), [result])

  useEffect(() => {
    if (!jobIdParam) return
    dispatch(setJobId(jobIdParam))
    return () => {
      dispatch(resetJob())
    }
  }, [dispatch, jobIdParam])

  useEffect(() => {
    const onFs = () => {
      const fs = Boolean(document.fullscreenElement)
      setIsFullscreen(fs)
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

  const statsEntries = Object.entries(result?.stats || {})

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

  return (
    <Layout
      title="Backtest Results"
      subtitle={jobIdParam ? `Job id: ${jobIdParam}` : undefined}
      right={
        <Link
          className="pill"
          to="/"
          onClick={() => {
            dispatch(resetJob())
          }}
        >
          New backtest
        </Link>
      }
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
        </div>

        <div>
          <Card title={<span style={{ fontWeight: 800 }}>stdout</span>}>
            <div className="log">{status?.stdout_tail || ''}</div>
          </Card>
          <div style={{ height: 14 }} />
          <Card title={<span style={{ fontWeight: 800 }}>stderr</span>}>
            <div className="log">{status?.stderr_tail || ''}</div>
          </Card>
        </div>
      </div>
    </Layout>
  )
}
