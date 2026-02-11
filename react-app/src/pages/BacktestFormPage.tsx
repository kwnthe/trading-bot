import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
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
}

const RECENT_KEY = 'recent_backtests'

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
      }))
  } catch {
    return []
  }
}

function saveRecent(items: RecentBacktest[]) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(items.slice(0, 10)))
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

  const [presetSelected, setPresetSelected] = useState('')
  const [presetName, setPresetName] = useState('')
  const [presetError, setPresetError] = useState<string | null>(null)
  const [restoredFromCookie, setRestoredFromCookie] = useState(false)
  const [search, setSearch] = useState('')
  const [recent, setRecent] = useState<RecentBacktest[]>(() => loadRecent())

  const groups = useMemo(() => groupDefs(schemaDefs), [schemaDefs])
  const defsByName = useMemo(() => {
    const m = new Map<string, ParamDef>()
    for (const d of schemaDefs) m.set(d.name, d)
    return m
  }, [schemaDefs])

  useEffect(() => {
    dispatch(fetchParamSchema())
    dispatch(fetchPresetNames())

    // Cookie restore (like the Django app)
    try {
      const raw = getCookie('bt_params')
      if (raw) {
        const values = JSON.parse(decodeURIComponent(raw))
        if (values && typeof values === 'object') {
          dispatch(setAllParams(values))
          setRestoredFromCookie(true)
        }
      }
    } catch {
      // ignore
    }
  }, [dispatch])

  useEffect(() => {
    if (schemaLoading) return
    if (schemaError) return
    if (restoredFromCookie) return
    if (!schemaDefs.length) return
    if (Object.keys(params || {}).length) return
    dispatch(setAllParams(schemaInitial || {}))
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

    const resp = await dispatch(runBacktest(payload)).unwrap()

    const entry: RecentBacktest = {
      jobId: resp.job_id,
      symbols: safeString(payload.symbols || ''),
      startDate: safeString(payload.start_date || ''),
      endDate: safeString(payload.end_date || ''),
      createdAt: Date.now(),
    }

    const next = [entry, ...loadRecent().filter((x) => x.jobId !== entry.jobId)].slice(0, 10)
    saveRecent(next)
    setRecent(next)
    navigate(`/jobs/${resp.job_id}`)
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
      title="Backtesting Dashboard"
      right={
        <div className="pill">
          <span className="muted">Tips</span>
          <span className="kbd">Search</span>
          <span className="muted">fields</span>
        </div>
      }
    >
      <div className="split">
        <div>
          <Card
            title={<span style={{ fontWeight: 850 }}>Run configuration</span>}
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
                  title={group}
                  defaultOpen={true}
                  right={<span className="muted">{items.length} fields</span>}
                >
                  {items.length ? <div className="grid">{items.map(renderField)}</div> : <div className="muted">No matches.</div>}
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
                <Button variant="primary" type="submit" disabled={jobLoading || schemaLoading || !!schemaError}>
                  Run backtest
                </Button>
                {jobError ? <span className="muted">{jobError}</span> : <span className="muted">Starts a new runner process.</span>}
              </div>
            </form>
          </Card>

          <div style={{ height: 14 }} />

          <Card title={<span style={{ fontWeight: 850 }}>Recent Backtests</span>}>
            {recent.length ? (
              <div style={{ display: 'grid', gap: 10 }}>
                {recent.map((r) => {
                  const sym = r.symbols.split(',').map((s) => s.trim()).filter(Boolean)
                  const symLabel = sym.length ? (sym.length === 1 ? sym[0] : `${sym[0]} +${sym.length - 1}`) : '(no symbols)'
                  const range = [fmtDate(r.startDate), fmtDate(r.endDate)].filter(Boolean).join(' → ')
                  return (
                    <Link key={r.jobId} className="pill" to={`/jobs/${r.jobId}`}>
                      <b>{symLabel}</b>
                      <span className="muted">{range || r.jobId}</span>
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
