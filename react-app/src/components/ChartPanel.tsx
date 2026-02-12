import { type ReactNode, useEffect, useRef, useState } from 'react'

import Button from './Button'
import BacktestChart from './BacktestChart'
import type { ResultJson } from '../api/types'

type Props = {
  result: ResultJson | null
  symbol: string
  height?: number
  headerLeft?: ReactNode
  headerRight?: ReactNode
}

export default function ChartPanel({ result, symbol, height = 520, headerLeft, headerRight }: Props) {
  const panelRef = useRef<HTMLDivElement | null>(null)
  const [chartMountId, setChartMountId] = useState(0)
  const exitFsTimerRef = useRef<number | null>(null)

  useEffect(() => {
    const onFs = () => {
      const fs = Boolean(document.fullscreenElement)
      if (!fs) {
        if (exitFsTimerRef.current) window.clearTimeout(exitFsTimerRef.current)
        exitFsTimerRef.current = window.setTimeout(() => {
          setChartMountId((v) => v + 1)
        }, 120)
      }
    }
    document.addEventListener('fullscreenchange', onFs)
    onFs()
    return () => {
      document.removeEventListener('fullscreenchange', onFs)
      if (exitFsTimerRef.current) window.clearTimeout(exitFsTimerRef.current)
    }
  }, [])

  async function toggleFullscreen() {
    const el = panelRef.current
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
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <div style={{ minWidth: 0, display: 'flex', gap: 10, alignItems: 'center' }}>
          {headerLeft ?? <span style={{ fontWeight: 850 }}>{symbol}</span>}
        </div>
        <div className="row" style={{ marginLeft: 'auto' }}>
          {headerRight}
          <Button type="button" onClick={toggleFullscreen} disabled={!symbol}>
            {'⛶'}
          </Button>
        </div>
      </div>

      <div ref={panelRef} className="chartPanel" style={{ height }}>
        <BacktestChart key={`${symbol}:${chartMountId}`} result={result} symbol={symbol} />
      </div>
    </div>
  )
}
