import type { Time } from 'lightweight-charts'

export function toTime(t: any): Time {
  return t as Time
}

function timeToNumber(t: any): number {
  if (typeof t === 'number' && Number.isFinite(t)) return t
  if (typeof t === 'string') {
    const s = t.trim()
    if (/^\d+$/.test(s)) return Number(s)
    const ms = Date.parse(s)
    if (Number.isFinite(ms)) return Math.floor(ms / 1000)
  }
  return 0
}

export function sortAndDedupByTime<T extends { time: any }>(items: T[]): T[] {
  const sorted = [...items].sort((a, b) => timeToNumber(a.time) - timeToNumber(b.time))
  const out: T[] = []
  let prevKey: string | null = null
  for (const it of sorted) {
    const key = String(it.time)
    if (prevKey === key) {
      out[out.length - 1] = it
      continue
    }
    out.push(it)
    prevKey = key
  }
  return out
}
