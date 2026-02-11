import type { ParamFieldType } from './types'

export type Destination = 'backtest' | 'env' | 'meta'

export type ParamDef = {
  name: string
  label: string
  field_type: ParamFieldType
  destination: Destination
  required: boolean
  group: string
  help_text?: string
  choices?: Array<[string, string]>
}

export type ParamsApiResponse = {
  param_defs: ParamDef[]
  initial: Record<string, any>
}
