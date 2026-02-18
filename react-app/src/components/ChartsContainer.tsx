import { useState, type ReactNode } from 'react'
import ChartPanel from './ChartPanel'
import ChartHeightAdjuster from './ChartHeightAdjuster'
import type { ResultJson } from '../api/types'

type Props = {
  result: ResultJson | null
  symbols: string[]
  initialHeight?: number
  min?: number
  max?: number
  step?: number
  headerLeft?: ReactNode
  headerRight?: ReactNode
  showHeightAdjuster?: boolean
}

export default function ChartsContainer({
  result,
  symbols,
  initialHeight = 550,
  min = 100,
  max = 1500,
  step = 1,
  headerLeft,
  headerRight,
  showHeightAdjuster = true,
}: Props) {
  const [chartHeight, setChartHeight] = useState(initialHeight)

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      {showHeightAdjuster && (
        <ChartHeightAdjuster
          value={chartHeight}
          onChange={setChartHeight}
          min={min}
          max={max}
          step={step}
        />
      )}
      {symbols.map((sym) => (
        <div key={sym}>
          <ChartPanel
            result={result}
            symbol={sym}
            height={chartHeight}
            headerLeft={headerLeft}
            headerRight={headerRight}
          />
        </div>
      ))}
    </div>
  )
}
