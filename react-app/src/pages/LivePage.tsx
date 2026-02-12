import { useEffect, useMemo, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'

import Layout from '../components/Layout'
import Card from '../components/Card'
import Button from '../components/Button'
import ChartPanel from '../components/ChartPanel'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { fetchLiveSnapshot, fetchLiveStatus, setActiveSessionId, stopLive } from '../store/slices/liveSlice'

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

  const status = useAppSelector((s) => s.live.status)
  const snapshot = useAppSelector((s) => s.live.snapshot)
  const error = useAppSelector((s) => s.live.error)

  const stdoutRef = useRef<HTMLDivElement | null>(null)
  const stderrRef = useRef<HTMLDivElement | null>(null)

  const symbols = useMemo(() => Object.keys(snapshot?.symbols || {}), [snapshot])

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

  const statsEntries = Object.entries((snapshot as any)?.stats || {})

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
      <div className="split" style={{ gridTemplateColumns: '1fr 0.7fr' }}>
        <div>
          <Card title={<span style={{ fontWeight: 800 }}>Charts</span>}>
            {error ? (
              <div className="muted">
                <b>Error:</b> {error}
              </div>
            ) : null}

            {symbols.length ? (
              <div style={{ display: 'grid', gap: 14 }}>
                {symbols.map((sym) => (
                  <div key={sym}>
                    <ChartPanel
                      result={snapshot}
                      symbol={sym}
                      height={420}
                      headerRight={
                        <span className="muted">{(snapshot as any)?.meta?.timeframe || ''}</span>
                      }
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div className="muted">No data yet.</div>
            )}
          </Card>
        </div>

        <div>
          <Card title={<span style={{ fontWeight: 800 }}>Stats</span>}>
            {statsEntries.length ? (
              <div className="grid">
                {statsEntries.map(([k, v]) => (
                  <div key={k} className="pill">
                    <b>{k}</b>
                    <span className="muted">{String(v)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="muted">No stats yet.</div>
            )}
          </Card>

          <div style={{ height: 14 }} />

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
