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
import { ChartZoneManager } from '../utils/ChartZoneManager'
import type { ChartManager } from '../utils/ChartManager'
import type { ResultJson } from '../api/types'
import type { ChartMarker } from '../types/chart'

type Props = {
  result: ResultJson | null
  symbol: string
}
type Line = ISeriesApi<'Line'>


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

  // Manager array for all chart managers
  const chartManagers: ChartManager[] = []

  const didFitRef = useRef(false)
  const [chartMountId, setChartMountId] = useState(0)
  const exitFsTimerRef = useRef<number | null>(null)

  const [showTrades, setShowTrades] = useState(() => {
    return getCookie('showTrades') === '' ? true : getCookie('showTrades') === 'true'
  })
  // ---------- TOGGLE STATES ----------
  const [isDark, setIsDark] = useState(() => {
    const cookie = getCookie('chartTheme')
    return cookie === '' ? true : cookie === 'dark'
  })


  const [showIndexes, setShowIndexes] = useState(() => {
    return getCookie('candleIndexes') === 'true'
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

  // ---------------- OPACITY SETTINGS ----------------
  // const RESULT_BOX_OPACITY = 0.3    // Opacity for the "winning" side (TP for profitable, SL for losing)
  const RESULT_BOX_OPACITY = 0.07
  const NON_RESULT_BOX_OPACITY = 0.07 // Opacity for the "losing" side (very faint)
  const DEFAULT_BOX_OPACITY = 0.1    // Opacity for other states (PENDING, RUNNING, CANCELED)

  // ---------------- STATE & REFS ----------------
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

    // Clear all managers
    chartManagers.forEach(manager => manager.clear())
    zoneSeriesRef.current = []
    orderBoxSeriesRef.current = []
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
    
    // Handle new data format (timestamp-keyed) or legacy format
    let emaData: any[] = []
    let markerData: any[] = []
    let zoneManager: ChartZoneManager | null = null
    
    if (cd?.data && typeof cd.data === 'object') {
      // New format: symbol-keyed data
      const symbolData = cd.data[symbol]
      if (symbolData && typeof symbolData === 'object') {
        // Convert timestamp-keyed data to arrays for this specific symbol
        emaData = Object.entries(symbolData)
          .filter(([_, data]: [string, any]) => data.ema !== undefined && data.ema !== null)
          .map(([timestamp, data]: [string, any]) => {
            const time = toTime(parseInt(timestamp))
            const value = Number(data.ema)
            return time && Number.isFinite(value) ? { time: time as Time, value } : null
          })
          .filter(Boolean)
        
        // Initialize managers and add to managers array
        chartManagers.push(new ChartZoneManager(chart, zoneSeriesRef, {debugMode: false}))
        
        // Automatically process data for all managers
        chartManagers.forEach(manager => {
          // Filter symbolData to only include keys the manager needs
          const managerDataKeys = manager.getDataKeys()
          const filteredData: Record<string, any> = {}
          
          Object.entries(symbolData).forEach(([timestamp, data]: [string, any]) => {
            const filteredEntry: Record<string, any> = {}
            managerDataKeys.forEach(key => {
              if (data[key] !== undefined) {
                filteredEntry[key] = data[key]
              }
            })
            
            // Only include timestamp if manager has relevant data
            if (Object.keys(filteredEntry).length > 0) {
              filteredData[timestamp] = filteredEntry
            }
          })
          
          manager.processData(filteredData)
        })
        
        // Extract markers from the new data format
        markerData = []
        Object.entries(symbolData).forEach(([timestamp, data]: [string, any]) => {
          Object.entries(data).forEach(([key, value]: [string, any]) => {
            if (key !== 'ema' && key !== 'support' && key !== 'resistance' && typeof value === 'object' && value !== null) {
              // This looks like a marker object
              markerData.push({
                time: parseInt(timestamp),
                type: key,
                ...value
              })
            }
          })
        })
      }
    }
    
    ema.setData(emaData)

    // Render all managers
    chartManagers.forEach(manager => {
      const stats = manager.render()
      console.log(`📊 ${manager.getName()}: Rendered ${stats.totalCount} elements`)
    })

    // --- Order Boxes & Markers (Toggleable) ---
    const allMarkers: SeriesMarker<Time>[] = []
    
    // Convert trades to order boxes format
    const orderBoxes = (() => {
      const chartData = sym.chartOverlayData
      if (!chartData?.trades || typeof chartData.trades !== 'object') return []
      
      // Determine data feed index for this symbol
      // For now, assume symbol order corresponds to data feed index
      // This could be enhanced with proper symbol mapping if needed
      const symbols = Object.keys(result?.symbols || {})
      const dataFeedIndex = symbols.indexOf(symbol)
      
      const trades = chartData.trades[dataFeedIndex] || []
      
      return trades
        .filter((trade: any) => 
          trade.placed_on && 
          trade.executed_on && 
          trade.closed_on
        )
        .map((trade: any) => ({
          openTime: trade.executed_on,
          closeTime: trade.closed_on,
          entry: trade.entry_executed_price || trade.entry_price,
          sl: trade.sl,
          tp: trade.tp,
          closeReason: trade.state // TP_HIT, SL_HIT, CANCELED
        }))
    })()

    // Process markers - use the markerData we already processed above
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
        // Only add retest order markers if toggle is on (default: show all)
        if (marker.marker !== 'retest_order_placed' || true) {
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
      for (const b of orderBoxes) {
        const openTime = toTime(b.openTime); const closeTime = toTime(b.closeTime)
        if (!openTime || !closeTime) continue

        const entry = Number(b.entry); const sl = Number(b.sl); const tp = Number(b.tp)
        const reason = String(b.closeReason || '')
        
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

    tpPoints.setData([])
    slPoints.setData([])

    tpLabels.setData([])
    slLabels.setData([])

    tpMarkersRef.current?.setMarkers([])
    slMarkersRef.current?.setMarkers([])

    allMarkers.sort((a, b) => (a.time as number) - (b.time as number))
    markers.setMarkers(allMarkers)

    if (!didFitRef.current && candleData.length) {
      chart.timeScale().fitContent()
      didFitRef.current = true
    }
  }, [sym, chartMountId, showIndexes, showTrades, precision, minMove])

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

  const colorsForCloseReason = (reason: string) => {
    console.log('DEBUG: closeReason:', reason)
    if (reason === 'TP_HIT') return { 
      sl: `rgba(242,54,69,${NON_RESULT_BOX_OPACITY})`, 
      tp: `rgba(8,153,129,${RESULT_BOX_OPACITY})`  
    }  // TP wins, SL loses
    if (reason === 'SL_HIT') return { 
      sl: `rgba(242,54,69,${RESULT_BOX_OPACITY})`, 
      tp: `rgba(8,153,129,${NON_RESULT_BOX_OPACITY})`  
    }  // SL wins, TP loses
    if (reason === 'TP') return { 
      sl: `rgba(242,54,69,${NON_RESULT_BOX_OPACITY})`, 
      tp: `rgba(8,153,129,${RESULT_BOX_OPACITY})`  
    }  // Fallback for 'TP'
    if (reason === 'SL') return { 
      sl: `rgba(242,54,69,${RESULT_BOX_OPACITY})`, 
      tp: `rgba(8,153,129,${NON_RESULT_BOX_OPACITY})`  
    }  // Fallback for 'SL'
    console.log('DEBUG: Using default colors for reason:', reason)
    return { 
      sl: `rgba(242,54,69,${DEFAULT_BOX_OPACITY})`, 
      tp: `rgba(8,153,129,${DEFAULT_BOX_OPACITY})` 
    }
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
        <button onClick={toggleIndexes} style={activeBtn(showIndexes)} title="Toggle Candle Index" type="button"><span>🔢</span></button>
      </div>
      <div key={chartMountId} ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  )
}