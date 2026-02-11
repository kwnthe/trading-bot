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
  stdout_tail?: string
  stderr_tail?: string
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
    markers?: any[]
    orderBoxes?: Array<{ openTime: number | string; closeTime: number | string; entry: number; sl: number; tp: number; closeReason?: string }>
  }>
  stats?: Record<string, any>
}
