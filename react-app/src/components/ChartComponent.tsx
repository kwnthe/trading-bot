import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CandlestickSeries,
  BaselineSeries,
  LineSeries,
  createChart,
  CrosshairMode,
  createSeriesMarkers,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'

import { sortAndDedupByTime, toTime } from '../utils/timeSeries'
import type { ResultJson } from '../api/types'
import type { ChartMarker } from '../types/chart'

type Props = {
  result: ResultJson | null
  symbol: string
}

type Line = ISeriesApi<'Line'>

const dedupPointsByTime = (pts: { time: Time; value: number }[]) => {
  const m = new Map<number, { time: Time; value: number }>()
  for (const p of pts) m.set(p.time as number, p)
  return Array.from(m.values()).sort((a, b) => (a.time as number) - (b.time as number))
}

// Convert new marker format to lightweight-charts SeriesMarker format
const convertMarkerToSeriesMarker = (marker: ChartMarker): SeriesMarker<Time> => {
  const time = toTime(marker.time) as Time
  
  switch (marker.type) {
    case 'entry':
      return {
        time,
        position: marker.direction === 'buy' ? 'belowBar' : 'aboveBar',
        color: marker.direction === 'buy' ? '#2196F3' : '#F23645',
        shape: marker.direction === 'buy' ? 'arrowUp' : 'arrowDown',
        text: '',
        size: 10
      }
    
    case 'exit':
      if (marker.reason === 'tp') {
        return {
          time,
          position: 'aboveBar',
          color: '#089981',
          shape: 'circle',
          text: '✓',
          size: 8
        }
      } else if (marker.reason === 'sl') {
        return {
          time,
          position: 'belowBar',
          color: '#F23645',
          shape: 'circle',
          text: '✗',
          size: 8
        }
      }
      break
    
    case 'retest':
      return {
        time,
        position: 'aboveBar',
        color: '#FF9800',
        shape: 'circle',
        text: marker.text || '',
        size: marker.size || 8
      }
    
    case 'signal':
      return {
        time,
        position: 'aboveBar',
        color: '#9C27B0',
        shape: 'arrowUp',
        text: marker.text || '',
        size: marker.size || 8
      }
    
    case 'breakout':
      return {
        time,
        position: 'aboveBar',
        color: '#FF5722',
        shape: 'arrowUp',
        text: marker.text || '',
        size: marker.size || 8
      }
    
    case 'retest_order_placed':
      const directionStr = String(marker.direction || '').toLowerCase()
      const isUptrend = directionStr === 'uptrend'
      return {
        time,
        position: isUptrend ? 'aboveBar' : 'belowBar',
        color: isUptrend ? '#00BCD4' : '#FF9800',
        shape: isUptrend ? 'arrowDown' : 'arrowUp',
        text: '',
        size: 1
      }
    
    default:
      return {
        time,
        position: 'aboveBar',
        color: '#666666',
        shape: 'circle',
        text: marker.text || '',
        size: marker.size || 8
      }
  }
  
  // Fallback for unknown types
  return {
    time,
    position: 'aboveBar',
    color: '#666666',
    shape: 'circle',
    text: '',
    size: 8
  }
}


// ---------------- COOKIE HELPERS ----------------
const setCookie = (name: string, value: string, days = 365) => {
  const expires = new Date(Date.now() + days * 864e5).toUTCString()
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/`
}

const getCookie = (name: string) => {
  return document.cookie.split('; ').reduce((r, v) => {
    const parts = v.split('=')
    return parts[0] === name ? decodeURIComponent(parts[1]) : r
  }, '')
}

export default function ChartComponent({ result, symbol }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const wrapperRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)

  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const emaSeriesRef = useRef<Line | null>(null)
  const tpPointsSeriesRef = useRef<Line | null>(null)
  const slPointsSeriesRef = useRef<Line | null>(null)
  const tpLabelSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const slLabelSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const zoneSeriesRef = useRef<Line[]>([])
  const orderBoxSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([])
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const tpMarkersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const slMarkersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)

  const didFitRef = useRef(false)
  const [chartMountId, setChartMountId] = useState(0)
  const exitFsTimerRef = useRef<number | null>(null)

  const [showTpSlMarkers, setShowTpSlMarkers] = useState(() => {
    return getCookie('showTpSlMarkers') === '' ? true : getCookie('showTpSlMarkers') === 'true'
  })
  const [showRetestOrders, setShowRetestOrders] = useState(() => {
    return getCookie('showRetestOrders') === '' ? true : getCookie('showRetestOrders') === 'true'
  })
  // ---------- TOGGLE STATES ----------
  const [isDark, setIsDark] = useState(() => {
    const cookie = getCookie('chartTheme')
    return cookie === '' ? true : cookie === 'dark'
  })


  const [showIndexes, setShowIndexes] = useState(() => {
    return getCookie('candleIndexes') === 'true'
  })

  const [showTrades, setShowTrades] = useState(() => {
    return getCookie('showTrades') === '' ? true : getCookie('showTrades') === 'true'
  })

  const theme = useMemo(() => isDark
    ? {
        background: '#0B0E11',
        textColor: '#d1d4dc',
        gridColor: '#1E222D',
        borderColor: '#2A2E39',
        crosshairColor: '#758696',
        upColor: '#26a69a',
        downColor: '#ef5350',
      }
    : {
        background: '#ffffff',
        textColor: '#191919',
        gridColor: '#e1e3e6',
        borderColor: '#d1d4dc',
        crosshairColor: '#758696',
        upColor: '#26a69a',
        downColor: '#ef5350',
      }, [isDark])

  const sym = useMemo(() => result?.symbols?.[symbol] || null, [result, symbol])

  const precision = useMemo(() => {
    const s = symbol.toLowerCase()
    if (s.includes('eur') || s.includes('usd') || s.includes('gbp') || s.includes('jpy')) {
      return s.includes('jpy') ? 3 : 5
    }
    return 2
  }, [symbol])

  const minMove = useMemo(() => 1 / Math.pow(10, precision), [precision])

  useEffect(() => {
    const onFs = () => {
      const fs = Boolean(document.fullscreenElement)
      if (!fs) {
        if (exitFsTimerRef.current) window.clearTimeout(exitFsTimerRef.current)
        exitFsTimerRef.current = window.setTimeout(() => setChartMountId((v) => v + 1), 120)
      }
    }
    document.addEventListener('fullscreenchange', onFs)
    return () => {
      document.removeEventListener('fullscreenchange', onFs)
      if (exitFsTimerRef.current) window.clearTimeout(exitFsTimerRef.current)
    }
  }, [])

  async function toggleFullscreen() {
    const el = wrapperRef.current
    try {
      if (!document.fullscreenElement) {
        if (el?.requestFullscreen) await el.requestFullscreen()
      } else {
        if (document.exitFullscreen) await document.exitFullscreen()
      }
    } catch {}
  }

  // ---------------- CREATE CHART ----------------
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    didFitRef.current = false

    const chart = createChart(el, {
      layout: {
        background: { color: theme.background },
        textColor: theme.textColor,
        fontSize: 12,
        fontFamily: 'Inter, Roboto, Arial',
      },
      grid: {
        vertLines: { color: theme.gridColor },
        horzLines: { color: theme.gridColor },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: theme.borderColor,
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: theme.borderColor,
      },
    })

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: theme.upColor,
      downColor: theme.downColor,
      borderUpColor: theme.upColor,
      borderDownColor: theme.downColor,
      wickUpColor: theme.upColor,
      wickDownColor: theme.downColor,
      borderVisible: true,
      priceLineVisible: true,
      lastValueVisible: true,
      priceFormat: { type: 'price', precision, minMove },
    })

    const ema = chart.addSeries(LineSeries, {
      color: '#2962FF',
      lineWidth: 0.8,
      priceFormat: { type: 'price', precision, minMove },
    })

    const tpPoints = chart.addSeries(LineSeries, {
      color: '#089981',
      lineWidth: 1,
      lineVisible: false,
      pointMarkersVisible: true,
      pointMarkersRadius: 4,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision, minMove },
    })

    const slPoints = chart.addSeries(LineSeries, {
      color: '#f23645',
      lineWidth: 1,
      lineVisible: false,
      pointMarkersVisible: true,
      pointMarkersRadius: 4,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision, minMove },
    })

    const tpLabels = chart.addSeries(CandlestickSeries, {
      upColor: 'rgba(0,0,0,0)',
      downColor: 'rgba(0,0,0,0)',
      borderUpColor: 'rgba(0,0,0,0)',
      borderDownColor: 'rgba(0,0,0,0)',
      wickUpColor: 'rgba(0,0,0,0)',
      wickDownColor: 'rgba(0,0,0,0)',
      borderVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision, minMove },
    })

    const slLabels = chart.addSeries(CandlestickSeries, {
      upColor: 'rgba(0,0,0,0)',
      downColor: 'rgba(0,0,0,0)',
      borderUpColor: 'rgba(0,0,0,0)',
      borderDownColor: 'rgba(0,0,0,0)',
      wickUpColor: 'rgba(0,0,0,0)',
      wickDownColor: 'rgba(0,0,0,0)',
      borderVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision, minMove },
    })

    chartRef.current = chart
    candleSeriesRef.current = candles
    emaSeriesRef.current = ema
    tpPointsSeriesRef.current = tpPoints
    slPointsSeriesRef.current = slPoints
    tpLabelSeriesRef.current = tpLabels
    slLabelSeriesRef.current = slLabels
    markersRef.current = createSeriesMarkers(candles, [])
    tpMarkersRef.current = createSeriesMarkers(tpLabels, [])
    slMarkersRef.current = createSeriesMarkers(slLabels, [])

    const resize = () => {
      const rect = el.getBoundingClientRect()
      if (rect.width && rect.height) chart.resize(rect.width, rect.height)
    }

    const ro = new ResizeObserver(resize)
    ro.observe(el)
    resize()

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [chartMountId, precision, minMove])

  // ---------------- DATA UPDATE ----------------
  useEffect(() => {
    const chart = chartRef.current
    const candles = candleSeriesRef.current
    const ema = emaSeriesRef.current
    const markers = markersRef.current
    const tpMarkers = tpMarkersRef.current
    const slMarkers = slMarkersRef.current

    if (!chart || !candles || !ema || !markers || !tpMarkers || !slMarkers) return

    zoneSeriesRef.current.forEach(s => { try { chart.removeSeries(s) } catch {} })
    zoneSeriesRef.current = []
    orderBoxSeriesRef.current.forEach(s => { try { chart.removeSeries(s) } catch {} })
    orderBoxSeriesRef.current = []

    if (!sym) {
      candles.setData([])
      ema.setData([])
      tpPointsSeriesRef.current?.setData([])
      slPointsSeriesRef.current?.setData([])
      tpLabelSeriesRef.current?.setData([])
      slLabelSeriesRef.current?.setData([])
      markers.setMarkers([])
      tpMarkers.setMarkers([])
      slMarkers.setMarkers([])
      didFitRef.current = false
      return
    }

    const candleData = sortAndDedupByTime(
      (sym.candles || [])
        .map((c: any) => {
          const time = toTime(c.time)
          if (!time) return null
          return { time: time as Time, open: Number(c.open), high: Number(c.high), low: Number(c.low), close: Number(c.close) }
        })
        .filter(Boolean) as any
    )
    candles.setData(candleData)

    // API may send chart_data (snake_case) or chartOverlayData (camelCase); support both and nested vs .points
    const cd = sym.chartOverlayData ?? (sym as any).chart_overlay_data ?? sym.chartData ?? (sym as any).chart_data
    const emaSource = cd?.indicators?.ema ?? cd?.ema?.points ?? sym.ema ?? []
    const emaData = (emaSource as any[])
      .map((p: any) => {
        const time = toTime(p.time)
        const value = Number(p.value)
        if (!time || !Number.isFinite(value)) return null
        return { time: time as Time, value }
      })
      .filter(Boolean) as any
    ema.setData(emaData)

    // Merge overlapping zones at the same price level to prevent rendering conflicts
const mergeOverlappingZones = (segments: any[]) => {
  const priceGroups = new Map<number, any[]>()
  
  // Group segments by price value
  segments.forEach(seg => {
    const price = Number(seg.value)
    if (!priceGroups.has(price)) {
      priceGroups.set(price, [])
    }
    priceGroups.get(price)!.push(seg)
  })
  
  const mergedSegments: any[] = []
  
  // Merge overlapping segments within each price group
  for (const [, group] of priceGroups.entries()) {
    if (group.length === 1) {
      // No overlap, keep as is (but create a copy to avoid read-only issues)
      const seg = group[0]
      mergedSegments.push({
        startTime: seg.startTime,
        endTime: seg.endTime,
        value: seg.value
      })
    } else {
      // Sort by start time
      group.sort((a, b) => a.startTime - b.startTime)
      
      // Merge overlapping segments
      let current = {
        startTime: group[0].startTime,
        endTime: group[0].endTime,
        value: group[0].value
      }
      
      for (let i = 1; i < group.length; i++) {
        const next = group[i]
        
        // Check if segments overlap or are adjacent
        if (next.startTime <= current.endTime) {
          // Merge them - extend the end time if needed (create new object)
          current = {
            startTime: current.startTime,
            endTime: Math.max(current.endTime, next.endTime),
            value: current.value
          }
        } else {
          // No overlap, push current and start new one
          mergedSegments.push(current)
          current = {
            startTime: next.startTime,
            endTime: next.endTime,
            value: next.value
          }
        }
      }
      
      // Push the last merged segment
      mergedSegments.push(current)
    }
  }
  
  return mergedSegments
}

// Resistance/Support - chartOverlayData.*.points or legacy sym.zones
    const resistanceSegments = (cd?.resistance?.points ?? cd?.zones?.resistance ?? sym.zones?.resistanceSegments ?? []) as any[]
    const supportSegments = (cd?.support?.points ?? cd?.zones?.support ?? sym.zones?.supportSegments ?? []) as any[]
    
    console.log('=== ZONE PROCESSING DEBUG ===')
    console.log('Data structure check:')
    console.log('  cd exists:', !!cd)
    console.log('  cd?.resistance exists:', !!cd?.resistance)
    console.log('  cd?.resistance?.points exists:', !!cd?.resistance?.points)
    console.log('  cd?.zones exists:', !!cd?.zones)
    console.log('  sym.zones exists:', !!sym?.zones)
    console.log(`Processing ${resistanceSegments.length} resistance and ${supportSegments.length} support segments`)
    
    // Debug: Log actual sample data
    if (resistanceSegments.length > 0) {
      console.log('Sample resistance segment (raw):', resistanceSegments[0])
      console.log('Keys:', Object.keys(resistanceSegments[0]))
    }
    if (supportSegments.length > 0) {
      console.log('Sample support segment (raw):', supportSegments[0])
      console.log('Keys:', Object.keys(supportSegments[0]))
    }
    
    // Merge overlapping zones to prevent rendering conflicts
    const mergedResistanceSegments = mergeOverlappingZones(resistanceSegments)
    const mergedSupportSegments = mergeOverlappingZones(supportSegments)
    
    console.log(`After merging: ${mergedResistanceSegments.length} resistance and ${mergedSupportSegments.length} support segments`)
    
    // Debug: Show first few merged segments
    if (mergedResistanceSegments.length > 0) {
      console.log('First merged resistance segment:', mergedResistanceSegments[0])
      const seg = mergedResistanceSegments[0]
      console.log('Duration:', seg.endTime - seg.startTime, 'seconds')
    }
    if (mergedSupportSegments.length > 0) {
      console.log('First merged support segment:', mergedSupportSegments[0])
      const seg = mergedSupportSegments[0]
      console.log('Duration:', seg.endTime - seg.startTime, 'seconds')
    }
    
    let zonesRendered = 0
    let zonesSkipped = 0
    
    for (const seg of mergedResistanceSegments) {
      const val = Number(seg.value); const s = toTime(seg.startTime); const e = toTime(seg.endTime)
      
      if (s && e && Number.isFinite(val) && s !== e) {
        // Check for weekend gap (Saturday zones)
        const startDate = new Date((s as number) * 1000)
        const endDate = new Date((e as number) * 1000)
        const isWeekendGap = (startDate.getDay() === 5 && startDate.getHours() >= 21) || (startDate.getDay() === 6) || (startDate.getDay() === 0 && endDate.getDay() === 1)
        
        if (isWeekendGap) {
          console.log('Skipping weekend gap zone:', { startDate: startDate.toISOString(), endDate: endDate.toISOString() })
          zonesSkipped++
          continue
        }
        
        const zone = chart.addSeries(LineSeries, { color: 'rgba(239, 83, 80, 0.95)', lineWidth: 3, priceLineVisible: false, lastValueVisible: false })
        const zoneData = [{ time: s as Time, value: val }, { time: e as Time, value: val }]
        
        zone.setData(zoneData)
        zoneSeriesRef.current.push(zone)
        zonesRendered++
      } else {
        zonesSkipped++
      }
    }
    for (const seg of mergedSupportSegments) {
      const val = Number(seg.value); const s = toTime(seg.startTime); const e = toTime(seg.endTime)
      
      if (s && e && Number.isFinite(val) && s !== e) {
        // Check for weekend gap (Saturday zones)
        const startDate = new Date((s as number) * 1000)
        const endDate = new Date((e as number) * 1000)
        const isWeekendGap = (startDate.getDay() === 5 && startDate.getHours() >= 21) || (startDate.getDay() === 6) || (startDate.getDay() === 0 && endDate.getDay() === 1)
        
        if (isWeekendGap) {
          console.log('Skipping weekend gap zone:', { startDate: startDate.toISOString(), endDate: endDate.toISOString() })
          zonesSkipped++
          continue
        }
        
        const zone = chart.addSeries(LineSeries, { color: 'rgba(33, 150, 243, 0.95)', lineWidth: 3, priceLineVisible: false, lastValueVisible: false })
        const zoneData = [{ time: s as Time, value: val }, { time: e as Time, value: val }]
        
        zone.setData(zoneData)
        zoneSeriesRef.current.push(zone)
        zonesRendered++
      } else {
        zonesSkipped++
      }
    }
    
    console.log(`Zone rendering complete: ${zonesRendered} rendered, ${zonesSkipped} skipped`)
    console.log(`Total zone series created: ${zoneSeriesRef.current.length}`)
    
    // Debug: Check for overlapping zones at same price level (after merging)
    const allMergedSegments = [...mergedResistanceSegments, ...mergedSupportSegments]
    const priceGroups = new Map()
    
    allMergedSegments.forEach(seg => {
      const price = Number(seg.value)
      if (!priceGroups.has(price)) {
        priceGroups.set(price, [])
      }
      priceGroups.get(price).push(seg)
    })
    
    console.log('=== OVERLAPPING ZONES ANALYSIS (AFTER MERGING) ===')
    let overlappingZonesFound = 0
    
    for (const [price, segments] of priceGroups.entries()) {
      if (segments.length > 1) {
        console.log(`⚠️  Found ${segments.length} zones at price ${price}:`)
        segments.forEach((seg: any, i: number) => {
          const start = toTime(seg.startTime)
          const end = toTime(seg.endTime)
          const duration = (end as number) - (start as number)
          console.log(`   ${i+1}. ${start} - ${end} (duration: ${duration}s)`)
        })
        overlappingZonesFound += segments.length - 1
      }
    }
    
    if (overlappingZonesFound > 0) {
      console.log(`⚠️  Total overlapping zones: ${overlappingZonesFound} (may still cause rendering issues)`)
    } else {
      console.log('✅ No overlapping zones found after merging')
    }
    
    // Debug: check if zones are actually in the chart
    if (zoneSeriesRef.current.length > 0) {
      console.log('✅ Zones successfully added to chart')
    } else {
      console.log('❌ No zones were added to chart')
    }

    // --- Order Boxes & Markers (Toggleable) ---
    const allMarkers: SeriesMarker<Time>[] = []
    const tpPointData: { time: Time; value: number }[] = []
    const slPointData: { time: Time; value: number }[] = []

    // Process markers - support both new format (direct keys) and legacy format
    const rawMarkers = cd?.markers
    const markerData = Array.isArray(rawMarkers) ? rawMarkers : (rawMarkers?.points ?? [])
    
    for (const marker of markerData) {
      // Check if this is the new format (has 'type' field)
      if (marker.type && typeof marker.type === 'string') {
        // New format - use the converter function
        try {
          const seriesMarker = convertMarkerToSeriesMarker(marker as ChartMarker)
          allMarkers.push(seriesMarker)
        } catch (error) {
          console.warn('Failed to convert marker:', marker, error)
        }
      } else if (marker.marker && typeof marker.marker === 'string') {
        // Legacy format with 'marker' field instead of 'type'
        const convertedMarker = {
          time: marker.time,
          type: marker.marker,  // Use 'marker' field as 'type'
          value: marker.price,
          direction: marker.direction  // Add direction info
        }
        // Only add retest order markers if toggle is on
        if (marker.marker !== 'retest_order_placed' || showRetestOrders) {
          try {
            const seriesMarker = convertMarkerToSeriesMarker(convertedMarker as ChartMarker)
            allMarkers.push(seriesMarker)
          } catch (error) {
            console.warn('Failed to convert legacy marker:', marker, error)
          }
        }
      } else {
        // Legacy format - handle as before
        const time = toTime(marker.time)
        const value = Number(marker.value)
        if (time && Number.isFinite(value)) {
          allMarkers.push({
            time,
            position: 'aboveBar',
            color: marker.color || '#FF0000',
            shape: marker.type === 'circle' ? 'circle' : 'arrowUp',
            text: '',
            size: marker.size || 8
          })
        }
      }
    }

    if (showTrades) {
      for (const b of sym.orderBoxes || []) {
        const openTime = toTime(b.openTime); const closeTime = toTime(b.closeTime)
        if (!openTime || !closeTime) continue

        const entry = Number(b.entry); const sl = Number(b.sl); const tp = Number(b.tp)
        const reason = String(b.closeReason || '')

        // Markers
        if (showTpSlMarkers) {
          if (reason === 'TP') {
            if (Number.isFinite(tp)) tpPointData.push({ time: closeTime as Time, value: tp })
          } else if (reason === 'SL') {
            if (Number.isFinite(sl)) slPointData.push({ time: closeTime as Time, value: sl })
          }
        }

        // Boxes
        const { sl: slC, tp: tpC } = colorsForCloseReason(reason)
        const slS = chart.addSeries(BaselineSeries, { baseValue: { type: 'price', price: entry }, topFillColor1: slC, topFillColor2: slC, bottomFillColor1: slC, bottomFillColor2: slC, topLineColor: 'rgba(0,0,0,0)', bottomLineColor: 'rgba(0,0,0,0)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
        slS.setData([{ time: openTime as Time, value: sl }, { time: closeTime as Time, value: sl }])
        orderBoxSeriesRef.current.push(slS)

        const tpS = chart.addSeries(BaselineSeries, { baseValue: { type: 'price', price: entry }, topFillColor1: tpC, topFillColor2: tpC, bottomFillColor1: tpC, bottomFillColor2: tpC, topLineColor: 'rgba(0,0,0,0)', bottomLineColor: 'rgba(0,0,0,0)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
        tpS.setData([{ time: openTime as Time, value: tp }, { time: closeTime as Time, value: tp }])
        orderBoxSeriesRef.current.push(tpS)
      }
    }

    // Recreate TP/SL point series AFTER baseline boxes so points render on top
    if (tpPointsSeriesRef.current) {
      try { chart.removeSeries(tpPointsSeriesRef.current) } catch {}
      tpPointsSeriesRef.current = null
    }
    if (slPointsSeriesRef.current) {
      try { chart.removeSeries(slPointsSeriesRef.current) } catch {}
      slPointsSeriesRef.current = null
    }

    if (tpLabelSeriesRef.current) {
      try { chart.removeSeries(tpLabelSeriesRef.current) } catch {}
      tpLabelSeriesRef.current = null
    }
    if (slLabelSeriesRef.current) {
      try { chart.removeSeries(slLabelSeriesRef.current) } catch {}
      slLabelSeriesRef.current = null
    }

    const tpPoints = chart.addSeries(LineSeries, {
      color: '#089981',
      lineWidth: 1,
      lineVisible: false,
      pointMarkersVisible: true,
      pointMarkersRadius: 4,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision, minMove },
    })

    const slPoints = chart.addSeries(LineSeries, {
      color: '#f23645',
      lineWidth: 1,
      lineVisible: false,
      pointMarkersVisible: true,
      pointMarkersRadius: 4,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision, minMove },
    })

    const tpLabels = chart.addSeries(CandlestickSeries, {
      upColor: 'rgba(0,0,0,0)',
      downColor: 'rgba(0,0,0,0)',
      borderUpColor: 'rgba(0,0,0,0)',
      borderDownColor: 'rgba(0,0,0,0)',
      wickUpColor: 'rgba(0,0,0,0)',
      wickDownColor: 'rgba(0,0,0,0)',
      borderVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision, minMove },
    })

    const slLabels = chart.addSeries(CandlestickSeries, {
      upColor: 'rgba(0,0,0,0)',
      downColor: 'rgba(0,0,0,0)',
      borderUpColor: 'rgba(0,0,0,0)',
      borderDownColor: 'rgba(0,0,0,0)',
      wickUpColor: 'rgba(0,0,0,0)',
      wickDownColor: 'rgba(0,0,0,0)',
      borderVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision, minMove },
    })

    tpPointsSeriesRef.current = tpPoints
    slPointsSeriesRef.current = slPoints
    tpLabelSeriesRef.current = tpLabels
    slLabelSeriesRef.current = slLabels

    // Rebind TP/SL marker plugins to the recreated label series
    tpMarkersRef.current = createSeriesMarkers(tpLabels, [])
    slMarkersRef.current = createSeriesMarkers(slLabels, [])

    if (showIndexes && candleData.length) {
      const STEP = candleData.length > 2000 ? 50 : 10
      for (let i = 0; i < candleData.length; i += STEP) {
        allMarkers.push({ time: candleData[i].time, position: 'belowBar', color: '#2962FF', shape: 'arrowUp', text: `${i}` })
      }
    }

    const tpDedup = showTpSlMarkers ? dedupPointsByTime(tpPointData) : []
    const slDedup = showTpSlMarkers ? dedupPointsByTime(slPointData) : []

    tpPoints.setData(tpDedup)
    slPoints.setData(slDedup)

    tpLabels.setData(
      tpDedup.map((p) => ({ time: p.time, open: p.value, high: p.value, low: p.value, close: p.value }))
    )
    slLabels.setData(
      slDedup.map((p) => ({ time: p.time, open: p.value, high: p.value, low: p.value, close: p.value }))
    )

    // Labels anchored to TP/SL series points
    tpMarkersRef.current?.setMarkers(
      tpDedup.map((p) => ({
        time: p.time,
        position: 'inBar',
        color: '#089981',
        shape: 'circle',
        text: '✅',
      }))
    )
    slMarkersRef.current?.setMarkers(
      slDedup.map((p) => ({
        time: p.time,
        position: 'inBar',
        color: '#f23645',
        shape: 'circle',
        text: '❌',
      }))
    )

    allMarkers.sort((a, b) => (a.time as number) - (b.time as number))
    markers.setMarkers(allMarkers)

    if (!didFitRef.current && candleData.length) {
      chart.timeScale().fitContent()
      didFitRef.current = true
    }
  }, [sym, chartMountId, showIndexes, showTrades, showTpSlMarkers, showRetestOrders, precision, minMove])

  // ---------------- THEME & TOGGLES ----------------
  useEffect(() => {
    const chart = chartRef.current; const candles = candleSeriesRef.current
    if (!chart || !candles) return
    chart.applyOptions({
      layout: { background: { color: theme.background }, textColor: theme.textColor },
      grid: { vertLines: { color: theme.gridColor }, horzLines: { color: theme.gridColor } },
      rightPriceScale: { borderColor: theme.borderColor },
      timeScale: { borderColor: theme.borderColor },
    })
    candles.applyOptions({ upColor: theme.upColor, downColor: theme.downColor, borderUpColor: theme.upColor, borderDownColor: theme.downColor, wickUpColor: theme.upColor, wickDownColor: theme.downColor })
  }, [theme])

  const toggleTheme = () => setIsDark(v => { const n = !v; setCookie('chartTheme', n ? 'dark' : 'light'); return n })
  const toggleIndexes = () => setShowIndexes(v => { const n = !v; setCookie('candleIndexes', String(n)); return n })
  const toggleTrades = () => setShowTrades(v => { const n = !v; setCookie('showTrades', String(n)); return n })
  const toggleTpSlMarkers = () => setShowTpSlMarkers(v => { const n = !v; setCookie('showTpSlMarkers', String(n)); return n })
  const toggleRetestOrders = () => setShowRetestOrders(v => { const n = !v; setCookie('showRetestOrders', String(n)); return n })

  const colorsForCloseReason = (reason: string) => {
    if (reason === 'TP') return { sl: 'rgba(242,54,69,0.05)', tp: 'rgba(8,153,129,0.25)' }
    if (reason === 'SL') return { sl: 'rgba(242,54,69,0.25)', tp: 'rgba(8,153,129,0.05)' }
    return { sl: 'rgba(242,54,69,0.1)', tp: 'rgba(8,153,129,0.1)' }
  }

  const btnStyle = {
    padding: '6px 12px', borderRadius: 6, border: '1px solid #333', cursor: 'pointer',
    background: isDark ? '#1f2937' : 'white', color: isDark ? '#fff' : '#000',
    display: 'flex', alignItems: 'center', gap: 6,
  } as const

  const activeBtn = (isActive: boolean) => ({
    ...btnStyle,
    background: isActive ? '#2962FF' : btnStyle.background,
    color: isActive ? '#fff' : btnStyle.color
  })

  return (
    <div ref={wrapperRef} style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, display: 'flex', gap: 8 }}>
        <button onClick={toggleFullscreen} style={btnStyle} title="Fullscreen" type="button"><span>⛶</span></button>
        <button onClick={toggleTheme} style={btnStyle} type="button"><span>{isDark ? '☀️' : '🌙'}</span></button>
        <button onClick={toggleTrades} style={activeBtn(showTrades)} title="Toggle trades" type="button"><span>📦</span></button>
        <button onClick={toggleTpSlMarkers} style={activeBtn(showTpSlMarkers)} title="Toggle TP/SL markers" type="button"><span>✅</span></button>
        <button onClick={toggleRetestOrders} style={activeBtn(showRetestOrders)} title="Toggle retest orders" type="button"><span>📌</span></button>
        <button onClick={toggleIndexes} style={activeBtn(showIndexes)} title="Toggle Candle Index" type="button"><span>🔢</span></button>
      </div>
      <div key={chartMountId} ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  )
}