import { useEffect, useMemo, useRef } from 'react'
import {
  CandlestickSeries,
  LineSeries,
  createChart,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'

import { sortAndDedupByTime, toTime } from '../utils/timeSeries'
import type { ResultJson } from '../api/types'

type Line = ISeriesApi<'Line'>

type Props = {
  result: ResultJson | null
  symbol: string
}

export default function BacktestChart({ result, symbol }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candlesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const emaRef = useRef<Line | null>(null)
  const zoneSeriesRef = useRef<Line[]>([])
  const didFitRef = useRef(false)

  const sym = useMemo(() => result?.symbols?.[symbol] || null, [result, symbol])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const chart = createChart(el, {
      layout: { background: { color: '#0b1220' }, textColor: '#e5e7eb' },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.06)' },
        horzLines: { color: 'rgba(255,255,255,0.06)' },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.12)' },
      crosshair: { mode: CrosshairMode.Normal },
    })

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    chartRef.current = chart
    candlesRef.current = candles

    const resizeToEl = () => {
      const rect = el.getBoundingClientRect()
      const w = Math.floor(rect.width)
      const h = Math.floor(rect.height)
      if (w > 0 && h > 0) chart.resize(w, h)
    }

    const ro = new ResizeObserver(() => resizeToEl())
    ro.observe(el)

    const onFs = () => {
      // Give the browser a tick to apply fullscreen layout.
      setTimeout(resizeToEl, 50)
    }
    document.addEventListener('fullscreenchange', onFs)

    resizeToEl()

    return () => {
      ro.disconnect()
      document.removeEventListener('fullscreenchange', onFs)
      chart.remove()
      chartRef.current = null
      candlesRef.current = null
      emaRef.current = null
      zoneSeriesRef.current = []
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    const candles = candlesRef.current
    if (!chart || !candles) return

    const removeZones = () => {
      for (const s of zoneSeriesRef.current) chart.removeSeries(s)
      zoneSeriesRef.current = []
    }

    if (!sym) {
      candles.setData([])
      if (emaRef.current) {
        chart.removeSeries(emaRef.current)
        emaRef.current = null
      }
      removeZones()
      didFitRef.current = false
      return
    }

    const nextCandles = sortAndDedupByTime((sym.candles || []).map((c: any) => ({
      time: toTime(c.time) as Time,
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
    })))
    candles.setData(nextCandles)

    if (emaRef.current) {
      chart.removeSeries(emaRef.current)
      emaRef.current = null
    }
    if (sym.ema && sym.ema.length) {
      const emaSeries = chart.addSeries(LineSeries, { color: '#0000FF', lineWidth: 2 })
      const nextEma = sortAndDedupByTime(sym.ema.map((p: any) => ({ time: toTime(p.time) as Time, value: Number(p.value) })))
      emaSeries.setData(nextEma)
      emaRef.current = emaSeries
    }

    removeZones()
    const zones = sym.zones || {}
    for (const seg of zones.resistanceSegments || []) {
      if (String(seg.startTime) === String(seg.endTime)) continue
      const s = chart.addSeries(LineSeries, { color: 'rgba(242, 54, 69, 0.9)', lineWidth: 2, priceLineVisible: false, lastValueVisible: false })
      s.setData([
        { time: toTime(seg.startTime) as Time, value: Number(seg.value) },
        { time: toTime(seg.endTime) as Time, value: Number(seg.value) },
      ])
      zoneSeriesRef.current.push(s)
    }
    for (const seg of zones.supportSegments || []) {
      if (String(seg.startTime) === String(seg.endTime)) continue
      const s = chart.addSeries(LineSeries, { color: 'rgba(8, 153, 129, 0.9)', lineWidth: 2, priceLineVisible: false, lastValueVisible: false })
      s.setData([
        { time: toTime(seg.startTime) as Time, value: Number(seg.value) },
        { time: toTime(seg.endTime) as Time, value: Number(seg.value) },
      ])
      zoneSeriesRef.current.push(s)
    }

    // Avoid resetting user's zoom/scroll on every live polling update.
    // Auto-fit only once per mount / after clearing.
    if (!didFitRef.current && nextCandles.length) {
      chart.timeScale().fitContent()
      didFitRef.current = true
    }
  }, [sym])

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
}
