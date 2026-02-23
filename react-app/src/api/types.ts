export type ParamFieldType = 'str' | 'int' | 'float' | 'bool' | 'datetime' | 'choice' | 'hidden'

export type JobStatus = 'queued' | 'running' | 'finished' | 'failed' | 'unknown'

export interface RunResponse {
  ok: boolean
  job_id: string
  job_url: string
  status_url: string
  result_url: string
}

export interface JobStatusResponse {
  job_id: string
  status: JobStatus
  created_at?: string
  updated_at?: string
  pid?: number | string | null
  python_executable?: string
  returncode?: number | null
  error?: string | null
  params?: {
    backtest_args?: Record<string, any>
    env_overrides?: Record<string, any>
    meta?: Record<string, any>
  } | null
  stdout?: string
  stderr?: string
  has_result?: boolean
  result_url?: string | null
}

export interface PresetsListResponse {
  presets: string[]
}

export interface PresetResponse {
  name: string
  values: Record<string, any>
}

export interface ResultJson {
  symbols?: Record<string, {
    candles?: Array<{ time: number | string; open: number; high: number; low: number; close: number }>
    ema?: Array<{ time: number | string; value: number }>
    zones?: {
      resistanceSegments?: Array<{ startTime: number | string; endTime: number | string; value: number }>
      supportSegments?: Array<{ startTime: number | string; endTime: number | string; value: number }>
    }
    chartData?: {
      zones?: {
        resistance?: Array<{ type: string; startTime: number; endTime: number; value: number; color: string }>
        support?: Array<{ type: string; startTime: number; endTime: number; value: number; color: string }>
      }
      indicators?: {
        ema?: Array<{ time: number; value: number }>
      }
      markers?: Array<{ time: number; value: number; type: string; color: string; size: number }>
    }
    chartOverlayData?: {
      data?: {
        [symbol: string]: {
          [timestamp: string]: {
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
    markers?: any[]
    orderBoxes?: Array<{ openTime: number | string; closeTime: number | string; entry: number; sl: number; tp: number; closeReason?: string }>
  }>
  stats?: Record<string, any>
}[]
