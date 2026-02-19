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
  data?: {
    [symbol: string]: {
      [unix_timestamp: string]: {
        ema?: number
        support?: number
        resistance?: number
        [other_marker_name: string]: any
      }
    }
  }
  trades?: {
    [data_index: number]: Array<{
      placed_on: number
      executed_on?: number
      closed_on?: number
      closed_on_price?: number
      state: string
      symbol?: string
      entry_price?: number
      entry_executed_price?: number
      sl?: number
      tp?: number
      trade_id?: string
      order_side?: string
      size?: number
      exit_type?: string
      close_reason?: string
    }>
  }
}
