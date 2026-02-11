import { useEffect, useMemo, useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAppDispatch, useAppSelector } from '../store/hooks'
import { setAllParams, setParam } from '../store/slices/paramsSlice'
import { fetchParamSchema } from '../store/slices/paramSchemaSlice'
import { fetchPreset, fetchPresetNames, savePreset } from '../store/slices/presetsSlice'
import { runBacktest } from '../store/slices/jobSlice'
import { getCookie, setCookie } from '../utils/cookies'
import type { ParamDef } from '../api/paramsTypes'
import Layout from '../components/Layout'
import Card from '../components/Card'
import Accordion from '../components/Accordion'
import Button from '../components/Button'
import { deletePreset } from '../store/slices/presetsSlice'
import { hydrateFavorites, removeFavoriteAndPersist } from '../store/slices/favoritesSlice'
import { fetchStrategies, setSelectedStrategyId, startLive, stopLive } from '../store/slices/liveSlice'

function groupDefs(defs: ParamDef[]) {
  const groups = new Map<string, ParamDef[]>()
  for (const d of defs) {
    if (!groups.has(d.group)) groups.set(d.group, [])
    groups.get(d.group)!.push(d)
  }
  return groups
}

function inputForFieldType(fieldType: string): 'text' | 'number' | 'datetime-local' {
  if (fieldType === 'int' || fieldType === 'float') return 'number'
  if (fieldType === 'datetime') return 'datetime-local'
  return 'text'
}

function castValue(def: ParamDef, raw: any): any {
  if (def.field_type === 'bool') return Boolean(raw)
  if (def.field_type === 'int') {
    if (raw === '' || raw === null || raw === undefined) return ''
    const n = Number.parseInt(String(raw), 10)
    return Number.isFinite(n) ? n : raw
  }
  if (def.field_type === 'float') {
    if (raw === '' || raw === null || raw === undefined) return ''
    const n = Number.parseFloat(String(raw))
    return Number.isFinite(n) ? n : raw
  }
  // datetime, choice, str, hidden -> keep as string
  return raw
}

type RecentBacktest = {
  jobId: string
  symbols: string
  startDate?: string
  endDate?: string
  createdAt: number
  name?: string
  strategy?: string
}

type RecentLiveRun = {
  sessionId: string
  symbols: string
  timeframe?: string
  createdAt: number
  strategy?: string
}

const RECENT_KEY = 'recent_backtests'
const RECENT_LIVE_KEY = 'recent_live_runs'
const MT5_LOCAL_KEY = 'mt5_params'

const MT5_FIELDS = ['MT5_LOGIN', 'MT5_PASSWORD', 'MT5_SERVER', 'MT5_PATH']

function loadMt5Local(): Record<string, any> {
  try {
    const raw = localStorage.getItem(MT5_LOCAL_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return {}
    const out: Record<string, any> = {}
    for (const k of MT5_FIELDS) {
      if (k in parsed) out[k] = (parsed as any)[k]
    }
    return out
  } catch {
    return {}
  }
}

function saveMt5Local(values: Record<string, any>) {
  try {
    const existing = loadMt5Local()
    const out: Record<string, any> = { ...existing }
    for (const k of MT5_FIELDS) {
      const v = values[k]
      if (v === undefined || v === null || v === '') continue
      out[k] = v
    }
    localStorage.setItem(MT5_LOCAL_KEY, JSON.stringify(out))
  } catch {
    // ignore
  }
}

function safeString(v: any): string {
  if (v === null || v === undefined) return ''
  return String(v)
}

function fmtDate(v: string | undefined): string {
  if (!v) return ''
  // Handles ISO strings and datetime-local values.
  return v.replace('T', ' ').slice(0, 16)
}

function loadRecent(): RecentBacktest[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((x) => x && typeof x === 'object' && typeof x.jobId === 'string')
      .map((x) => ({
        jobId: String(x.jobId),
        symbols: safeString(x.symbols),
        startDate: x.startDate ? String(x.startDate) : undefined,
        endDate: x.endDate ? String(x.endDate) : undefined,
        createdAt: typeof x.createdAt === 'number' ? x.createdAt : Date.now(),
        strategy: (x as { strategy?: string }).strategy ? String((x as { strategy?: string }).strategy) : undefined,
      }))
  } catch {
    return []
  }
}

function saveRecent(items: RecentBacktest[]) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(items.slice(0, 4)))
  } catch {
    // ignore
  }
}

function loadRecentLive(): RecentLiveRun[] {
  try {
    const raw = localStorage.getItem(RECENT_LIVE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((x) => x && typeof x === 'object' && typeof x.sessionId === 'string')
      .map((x) => ({
        sessionId: String(x.sessionId),
        symbols: safeString(x.symbols),
        timeframe: x.timeframe ? String(x.timeframe) : undefined,
        createdAt: typeof x.createdAt === 'number' ? x.createdAt : Date.now(),
        strategy: x.strategy ? String(x.strategy) : undefined,
      }))
  } catch {
    return []
  }
}

function saveRecentLive(items: RecentLiveRun[]) {
  try {
    localStorage.setItem(RECENT_LIVE_KEY, JSON.stringify(items.slice(0, 4)))
  } catch {
    // ignore
  }
}

export default function BacktestFormPage() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  const params = useAppSelector((s) => s.params.values)
  const schemaDefs = useAppSelector((s) => s.paramSchema.defs)
  const schemaInitial = useAppSelector((s) => s.paramSchema.initial)
  const schemaLoading = useAppSelector((s) => s.paramSchema.loading)
  const schemaError = useAppSelector((s) => s.paramSchema.error)
  const presetNames = useAppSelector((s) => s.presets.names)
  const presetsLoading = useAppSelector((s) => s.presets.loading)
  const jobLoading = useAppSelector((s) => s.job.loading)
  const jobError = useAppSelector((s) => s.job.error)
  const favorites = useAppSelector((s) => s.favorites.items)
  const liveLoading = useAppSelector((s) => s.live.loading)
  const liveError = useAppSelector((s) => s.live.error)
  const liveStrategies = useAppSelector((s) => s.live.strategies)
  const selectedStrategyId = useAppSelector((s) => s.live.selectedStrategyId)
  const activeLiveSessionId = useAppSelector((s) => s.live.activeSessionId)

  const [presetSelected, setPresetSelected] = useState('')
  const [presetName, setPresetName] = useState('')
  const [presetError, setPresetError] = useState<string | null>(null)
  const [restoredFromCookie, setRestoredFromCookie] = useState(false)
  const [search, setSearch] = useState('')
  const [recent, setRecent] = useState<RecentBacktest[]>(() => loadRecent())
  const [recentLive, setRecentLive] = useState<RecentLiveRun[]>(() => loadRecentLive())

  const groups = useMemo(() => groupDefs(schemaDefs), [schemaDefs])
  const favoriteIds = useMemo(() => new Set(favorites.map((f) => f.jobId)), [favorites])
  const defsByName = useMemo(() => {
    const m = new Map<string, ParamDef>()
    for (const d of schemaDefs) m.set(d.name, d)
    return m
  }, [schemaDefs])

  useEffect(() => {
    dispatch(fetchParamSchema())
    dispatch(fetchPresetNames())
    dispatch(hydrateFavorites())
    dispatch(fetchStrategies())

    // Cookie restore (like the Django app)
    try {
      const raw = getCookie('bt_params')
      if (raw) {
        const values = JSON.parse(decodeURIComponent(raw))
        if (values && typeof values === 'object') {
          const mt5Local = loadMt5Local()
          dispatch(setAllParams({ ...values, ...mt5Local }))
          setRestoredFromCookie(true)
        }
      }
    } catch {
      // ignore
    }
  }, [dispatch])

  useEffect(() => {
    // Persist MT5 fields so Live credentials autofill across sessions.
    // Intentionally localStorage (not cookie) per requirement.
    if (!params || typeof params !== 'object') return
    saveMt5Local(params)
  }, [params])

  useEffect(() => {
    const refresh = () => dispatch(hydrateFavorites())
    const onVis = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    window.addEventListener('focus', refresh)
    window.addEventListener('storage', refresh)
    document.addEventListener('visibilitychange', onVis)
    return () => {
      window.removeEventListener('focus', refresh)
      window.removeEventListener('storage', refresh)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [])

  useEffect(() => {
    const refresh = () => setRecentLive(loadRecentLive())
    window.addEventListener('focus', refresh)
    window.addEventListener('storage', refresh)
    return () => {
      window.removeEventListener('focus', refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])

  useEffect(() => {
    if (schemaLoading) return
    if (schemaError) return
    if (restoredFromCookie) return
    if (!schemaDefs.length) return
    if (Object.keys(params || {}).length) return
    const mt5Local = loadMt5Local()
    dispatch(setAllParams({ ...(schemaInitial || {}), ...mt5Local }))
  }, [dispatch, schemaDefs.length, schemaError, schemaInitial, schemaLoading, restoredFromCookie, params])

  async function onLoadPreset() {
    setPresetError(null)
    const name = presetSelected.trim()
    if (!name) return
    try {
      const data = await dispatch(fetchPreset(name)).unwrap()
      dispatch(setAllParams(data.values || {}))
    } catch (e: any) {
      setPresetError(String(e?.message || e))
    }
  }
  

  async function onDeletePreset() {
    if(!window.confirm("Are you sure you want to delete this preset?")) {
      return;
    }
    setPresetError(null)
    const name = presetSelected.trim()
    if (!name) return
    try {
      await dispatch(deletePreset(name)).unwrap()
      setPresetSelected('')
      await dispatch(fetchPresetNames())
    } catch (e: any) {
      setPresetError(String(e?.message || e))
    }
  }

  async function onSavePreset() {
    setPresetError(null)
    const name = presetName.trim()
    if (!name) return
    try {
      await dispatch(savePreset({ name, values: params })).unwrap()
      setPresetName('')
      await dispatch(fetchPresetNames())
      setPresetSelected(name)
    } catch (e: any) {
      setPresetError(String(e?.message || e))
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()

    // Cookie persistence (same idea as Django)
    try {
      setCookie('bt_params', JSON.stringify(params), 30)
    } catch {
      // ignore
    }

    // Cast numeric fields based on backend schema before submitting.
    const payload: Record<string, any> = {}
    for (const [k, v] of Object.entries(params || {})) {
      const def = defsByName.get(k)
      payload[k] = def ? castValue(def, v) : v
    }
    payload.strategy = selectedStrategyId || 'break_retest'

    const resp = await dispatch(runBacktest(payload)).unwrap()

    const entry: RecentBacktest = {
      jobId: resp.job_id,
      symbols: safeString(payload.symbols || ''),
      startDate: safeString(payload.start_date || ''),
      endDate: safeString(payload.end_date || ''),
      createdAt: Date.now(),
      strategy: selectedStrategyId || undefined,
    }

    const next = [entry, ...loadRecent().filter((x) => x.jobId !== entry.jobId)].slice(0, 4)
    saveRecent(next)
    setRecent(next)
    navigate(`/jobs/${resp.job_id}`)
  }

  async function onRunLive(e: MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (activeLiveSessionId) return

    const sym = safeString(params.symbols || '')
    const tf = safeString(params.timeframe || '')
    if (!sym.trim() || !tf.trim()) {
      window.alert('Please set Symbols and Timeframe before starting Live.')
      return
    }

    const payload: Record<string, any> = {
      ...params,
      strategy: selectedStrategyId || 'break_retest',
    }

    const resp = await dispatch(startLive(payload)).unwrap()
    const entry: RecentLiveRun = {
      sessionId: resp.session_id,
      symbols: sym,
      timeframe: tf,
      createdAt: Date.now(),
      strategy: selectedStrategyId || undefined,
    }
    const next = [entry, ...loadRecentLive().filter((x) => x.sessionId !== entry.sessionId)].slice(0, 4)
    saveRecentLive(next)
    setRecentLive(next)
    navigate(`/live/${resp.session_id}`)
  }

  const filteredGroups = useMemo(() => {
    const q = search.trim().toLowerCase()
    const out: Array<[string, ParamDef[]]> = []
    for (const [group, defs] of groups.entries()) {
      if (group === 'Meta') continue
      const filtered = q
        ? defs.filter((d) => (d.label + ' ' + d.name + ' ' + (d.help_text || '')).toLowerCase().includes(q))
        : defs
      out.push([group, filtered])
    }
    return out
  }, [groups, search])

  function renderField(p: ParamDef) {
    if (p.field_type === 'hidden') return null

    if (p.field_type === 'bool') {
      return (
        <label key={p.name} className="row" style={{ padding: '10px 8px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.18)' }}>
          <input
            type="checkbox"
            checked={Boolean(params[p.name])}
            onChange={(e) => dispatch(setParam({ name: p.name, value: e.target.checked }))}
          />
          <div>
            <div style={{ fontWeight: 750 }}>{p.label}</div>
            {p.help_text ? <div className="help">{p.help_text}</div> : null}
          </div>
        </label>
      )
    }

    if (p.field_type === 'choice') {
      const value = params[p.name] ?? ''
      const choices = p.choices || []
      return (
        <div key={p.name}>
          <div className="fieldLabel">{p.label}</div>
          <select
            className="select"
            value={value}
            onChange={(e) => dispatch(setParam({ name: p.name, value: e.target.value }))}
          >
            {choices.map(([val, lbl]) => (
              <option key={String(val)} value={val}>{lbl}</option>
            ))}
          </select>
          {p.help_text ? <div className="help">{p.help_text}</div> : null}
        </div>
      )
    }

    const t = inputForFieldType(p.field_type)
    const value = params[p.name] ?? ''
    return (
      <div key={p.name}>
        <div className="fieldLabel">{p.label}</div>
        <input
          className="input"
          type={t}
          value={value}
          onChange={(e) => dispatch(setParam({ name: p.name, value: e.target.value }))}
        />
        {p.help_text ? <div className="help">{p.help_text}</div> : null}
      </div>
    )
  }

  return (
    <Layout
      title="Dashboard"
    >
      <div className="split">
        <div>
          <Card
            title={<span style={{ fontWeight: 850 }}>General</span>}
            right={
              <div className="row" style={{ minWidth: 340 }}>
                <input
                  className="input"
                  placeholder="Search parameters…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <span className="pill">{schemaDefs.length} fields</span>
              </div>
            }
          >
            {schemaError ? <div className="muted"><b>Schema error:</b> {schemaError}</div> : null}
            {schemaLoading ? <div className="muted">Loading schema…</div> : null}

            <div style={{ display: 'grid', gap: 12 }}>
              {filteredGroups.map(([group, items]) => (
                <Accordion
                  key={group}
                  title={group === 'Backtest' ? 'General' : group}
                  defaultOpen={true}
                  right={<span className="muted">{items.length} fields</span>}
                >
                  {items.length ? <div className="grid">{items.map(renderField)}</div> : <div className="muted">No matches.</div>}
                  {group === 'Backtest' ? (
                    <div style={{ marginTop: 12 }}>
                      <div className="fieldLabel" style={{ marginBottom: 8 }}>Strategy</div>
                      <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
                        <select
                          className="select"
                          value={selectedStrategyId}
                          onChange={(e) => dispatch(setSelectedStrategyId(e.target.value))}
                          style={{ minWidth: 240 }}
                        >
                          {(liveStrategies || []).map((s) => (
                            <option key={s.id} value={s.id}>{s.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ) : null}
                </Accordion>
              ))}
            </div>
          </Card>
        </div>

        <div>
          <Card title={<span style={{ fontWeight: 850 }}>Presets</span>}>
            <div className="row">
              <div className="grow" style={{ minWidth: 220 }}>
                <div className="fieldLabel">Saved presets</div>
                <select className="select" value={presetSelected} onChange={(e) => setPresetSelected(e.target.value)}>
                  <option value="">(select preset)</option>
                  {presetNames.map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
              <Button onClick={onLoadPreset} disabled={!presetSelected || presetsLoading}>Load</Button>
              <Button onClick={onDeletePreset} disabled={!presetSelected || presetsLoading}>🗑️</Button>
            </div>

            <div style={{ height: 12 }} />

            <div className="row">
              <div className="grow" style={{ minWidth: 220 }}>
                <div className="fieldLabel">New preset name</div>
                <input className="input" value={presetName} onChange={(e) => setPresetName(e.target.value)} placeholder="e.g. XAG_H1_rr2" />
              </div>
              <Button onClick={onSavePreset} disabled={!presetName || presetsLoading}>Save</Button>
            </div>

            {presetError ? <div className="help">{presetError}</div> : null}
          </Card>

          <div style={{ height: 14 }} />

          <Card title={<span style={{ fontWeight: 850 }}>Run</span>}>
            <form onSubmit={onSubmit}>
              <div className="row">
                <Button type="submit" disabled={jobLoading}>
                  {jobLoading ? 'Running…' : 'Run Backtest'}
                </Button>
                <Button type="button" disabled={Boolean(activeLiveSessionId) || liveLoading} onClick={onRunLive}>
                  {activeLiveSessionId ? 'Live Running…' : liveLoading ? 'Starting Live…' : 'Run Live'}
                </Button>
              </div>
              {jobError && <span className="muted">{jobError}</span>}
              {liveError ? <div className="muted"><b>Live error:</b> {liveError}</div> : null}
            </form>
          </Card>

          <div style={{ height: 14 }} />

          <Card title={<span style={{ fontWeight: 850 }}>Live Session</span>}>
            {activeLiveSessionId ? (
              <div style={{ display: 'grid', gap: 10 }}>
                <Link className="pill" to={`/live/${activeLiveSessionId}`} style={{ textDecoration: 'none' }}>
                  <b>Active:</b> <span className="muted">{activeLiveSessionId}</span>
                </Link>
                <Button type="button" onClick={() => dispatch(stopLive(activeLiveSessionId))}>
                  Stop Live
                </Button>
                <div className="muted">Run Live is disabled while a session is active.</div>
              </div>
            ) : (
              <div className="muted">No live session running.</div>
            )}
          </Card>

          <Card title={<span style={{ fontWeight: 850 }}>Recent Live Runs</span>}>
            {recentLive.length ? (
              <div style={{ display: 'grid', gap: 10 }}>
                {recentLive.slice(0, 4).map((r) => {
                  const sym = r.symbols.split(',').map((s) => s.trim()).filter(Boolean)
                  const symLabel = sym.length ? (sym.length === 1 ? sym[0] : `${sym[0]} +${sym.length - 1}`) : '(no symbols)'
                  const isRunning = r.sessionId === activeLiveSessionId
                  return (
                    <Link
                      key={r.sessionId}
                      className="pill row"
                      to={`/live/${r.sessionId}`}
                      style={{
                        alignItems: 'center',
                        gap: 10,
                        textDecoration: 'none',
                        ...(isRunning ? { background: 'rgba(34, 197, 94, 0.22)', borderColor: 'rgba(34, 197, 94, 0.5)' } : {}),
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <b>{symLabel}</b>&nbsp;
                        <span className="muted">{r.timeframe || ''}</span>
                      </div>
                      {r.strategy ? (
                        <span className="muted" style={{ flex: '0 0 auto' }}>{r.strategy}</span>
                      ) : null}
                    </Link>
                  )
                })}
              </div>
            ) : (
              <div className="muted">No live runs yet.</div>
            )}
          </Card>

          <div style={{ height: 14 }} />

          <Card title={<span style={{ fontWeight: 850 }}>Favorite Backtests</span>}>
            {favorites.length ? (
              <div style={{ display: 'grid', gap: 10 }}>
                {favorites
                  .slice()
                  .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
                  .map((r) => {
                    const sym = r.symbols.split(',').map((s) => s.trim()).filter(Boolean)
                    const symLabel = sym.length ? (sym.length === 1 ? sym[0] : `${sym[0]} +${sym.length - 1}`) : '(no symbols)'
                    const range = [fmtDate(r.startDate), fmtDate(r.endDate)].filter(Boolean).join(' → ')
                    function handleUnfavorite(e: MouseEvent) {
                      e.preventDefault()
                      e.stopPropagation()
                      if (window.confirm('Remove this backtest from favorites?')) {
                        dispatch(removeFavoriteAndPersist(r.jobId))
                      }
                    }
                    return (
                      <Link
                        key={r.jobId}
                        className="pill row"
                        to={`/jobs/${r.jobId}`}
                        style={{ alignItems: 'center', gap: 10, textDecoration: 'none' }}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                          {r.name ? (
                            <>
                              <b>{r.name}</b>&nbsp;
                              <em>{symLabel} · {range || r.jobId}</em>
                            </>
                          ) : (
                            <>
                              <b>{symLabel}</b>
                              <span className="muted">{range || r.jobId}</span>
                            </>
                          )}
                        </div>
                        <span
                          role="button"
                          tabIndex={0}
                          onClick={handleUnfavorite}
                          title="Remove from favorites"
                          style={{
                            color: '#facc15',
                            fontSize: '1.4rem',
                            cursor: 'pointer',
                            padding: 4,
                            flex: '0 0 auto',
                          }}
                        >
                          ★
                        </span>
                      </Link>
                    )
                  })}
              </div>
            ) : (
              <div className="muted">No favorites yet. Open a result and star it.</div>
            )}
          </Card>

          <div style={{ height: 14 }} />

          <Card title={<span style={{ fontWeight: 850 }}>Recent Backtests</span>}>
            {recent.length ? (
              <div style={{ display: 'grid', gap: 10 }}>
                {recent.slice(0, 4).map((r) => {
                  const sym = r.symbols.split(',').map((s) => s.trim()).filter(Boolean)
                  const symLabel = sym.length ? (sym.length === 1 ? sym[0] : `${sym[0]} +${sym.length - 1}`) : '(no symbols)'
                  const range = [fmtDate(r.startDate), fmtDate(r.endDate)].filter(Boolean).join(' → ')
                  return (
                    <Link
                      key={r.jobId}
                      className="pill row"
                      to={`/jobs/${r.jobId}`}
                      style={{ alignItems: 'center', gap: 10, textDecoration: 'none' }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <b>{symLabel}</b>&nbsp;
                        <span className="muted">{range || r.jobId}</span>
                      </div>
                      {r.strategy ? (
                        <span className="muted" style={{ flex: '0 0 auto' }}>{r.strategy}</span>
                      ) : null}
                      {favoriteIds.has(r.jobId) ? (
                        <span title="Favorite" style={{ color: '#facc15', fontSize: '1.2rem', padding: 4, flex: '0 0 auto' }}>
                          ★
                        </span>
                      ) : null}
                    </Link>
                  )
                })}
              </div>
            ) : (
              <div className="muted">No recent backtests yet.</div>
            )}
          </Card>
        </div>
      </div>
    </Layout>
  )
}
