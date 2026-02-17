import { useEffect, type ChangeEvent } from 'react'

type Props = {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  cookieKey?: string
}

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const parts = document.cookie.split(/;\s*/g)
  for (const p of parts) {
    const idx = p.indexOf('=')
    if (idx <= 0) continue
    const k = decodeURIComponent(p.slice(0, idx))
    if (k !== name) continue
    return decodeURIComponent(p.slice(idx + 1))
  }
  return null
}

function setCookie(name: string, value: string, maxAgeSeconds: number) {
  if (typeof document === 'undefined') return
  const v = encodeURIComponent(value)
  document.cookie = `${encodeURIComponent(name)}=${v}; Max-Age=${maxAgeSeconds}; Path=/; SameSite=Lax`
}

function clampToStep(v: number, min: number, max: number, step: number): number {
  const clamped = Math.min(max, Math.max(min, v))
  const snapped = min + Math.round((clamped - min) / step) * step
  return Math.min(max, Math.max(min, snapped))
}

export default function ChartHeightAdjuster({
  value,
  onChange,
  min = 200,
  max = 1000,
  step = 1,
  cookieKey = 'chart_height',
}: Props) {
  useEffect(() => {
    const raw = getCookie(cookieKey)
    if (!raw) return
    const parsed = Number(raw)
    if (!Number.isFinite(parsed)) return
    const next = clampToStep(parsed, min, max, step)
    if (next !== value) onChange(next)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cookieKey, min, max, step])

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const next = clampToStep(Number(e.target.value), min, max, step)
    setCookie(cookieKey, String(next), 60 * 60 * 24 * 365)
    onChange(next)
  }

  return (
    <div className="row" style={{ gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
      <span className="muted" style={{ fontWeight: 700 }}>
        Charts height
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={handleChange} />
      <span className="pill" style={{ minWidth: 64, justifyContent: 'center' }}>
        {value}px
      </span>
    </div>
  )
}
