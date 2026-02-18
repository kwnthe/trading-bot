import { type ReactNode } from 'react'

import ChartComponent from './ChartComponent'
import type { ResultJson } from '../api/types'

type Props = {
  result: ResultJson | null
  symbol: string
  height?: number
  headerLeft?: ReactNode
  headerRight?: ReactNode
}

export default function ChartPanel({ result, symbol, height = 520, headerLeft, headerRight }: Props) {
  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <div style={{ minWidth: 0, display: 'flex', gap: 10, alignItems: 'center' }}>
          {headerLeft ?? <span style={{ fontWeight: 850 }}>{symbol}</span>}
        </div>
        <div className="row" style={{ marginLeft: 'auto' }}>
          {headerRight}
        </div>
      </div>

      <div className="chartPanel" style={{ height }}>
        <ChartComponent result={result} symbol={symbol} />
      </div>
    </div>
  )
}
