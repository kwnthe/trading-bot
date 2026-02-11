import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'

import { apiFetchJson } from '../../api/client'
import type { ParamDef, ParamsApiResponse } from '../../api/paramsTypes'

export type ParamSchemaState = {
  defs: ParamDef[]
  initial: Record<string, any>
  loading: boolean
  error: string | null
}

const initialState: ParamSchemaState = {
  defs: [],
  initial: {},
  loading: false,
  error: null,
}

export const fetchParamSchema = createAsyncThunk('paramSchema/fetch', async () => {
  const data = (await apiFetchJson('/api/params/')) as ParamsApiResponse
  return data
})

const paramSchemaSlice = createSlice({
  name: 'paramSchema',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchParamSchema.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchParamSchema.fulfilled, (state, action) => {
        state.loading = false
        state.defs = action.payload.param_defs || []
        state.initial = action.payload.initial || {}
      })
      .addCase(fetchParamSchema.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to load params schema'
      })
  },
})

export default paramSchemaSlice.reducer
