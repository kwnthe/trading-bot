/**
 * Chart overlay types for backtest visualization
 */

export type ChartMarkerType = 
  | 'entry'      // Trade entry marker
  | 'exit'       // Trade exit marker (TP/SL)
  | 'retest'     // Retest marker
  | 'retest_order_placed'  // Retest order placed marker
  | 'signal'     // General signal marker
  | 'breakout'   // Breakout marker
  | 'custom'     // Custom marker type

export type ChartMarkerDirection = 
  | 'buy'        // Buy direction
  | 'sell'       // Sell direction

export type ChartMarkerReason = 
  | 'tp'         // Take profit
  | 'sl'         // Stop loss
  | 'manual'     // Manual close
  | 'margin'     // Margin call
  | 'expiry'     // Expiration

export interface ChartMarker {
  time: number
  type: ChartMarkerType
  direction?: ChartMarkerDirection
  reason?: ChartMarkerReason
  text?: string
  size?: number
}

export interface ChartZoneSegment {
  startTime: number
  endTime: number
  value: number
}

export interface ChartZones {
  supportSegments: ChartZoneSegment[]
  resistanceSegments: ChartZoneSegment[]
}

export interface ChartOrderBox {
  openTime: number
  closeTime: number
  entry: number
  sl: number
  tp: number
  closeReason: string
}

export interface ChartEMAPoint {
  time: number
  value: number
}

export interface ChartOverlayData {
  ema: ChartEMAPoint[]
  zones: ChartZones
  markers: ChartMarker[]
  orderBoxes: ChartOrderBox[]
  trades: any[]  // Keep existing trade format for now
}
