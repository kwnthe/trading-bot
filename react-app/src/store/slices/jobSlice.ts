import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import { apiFetchJson } from '../../api/client'
import type { JobStatusResponse, ResultJson, RunResponse } from '../../api/types'

export type JobState = {
  jobId: string | null
  status: JobStatusResponse | null
  result: ResultJson | null
  loading: boolean
  error: string | null
}

const initialState: JobState = {
  jobId: null,
  status: null,
  result: null,
  loading: false,
  error: null,
}

export const runBacktest = createAsyncThunk('job/runBacktest', async (params: Record<string, any>) => {
  const data = (await apiFetchJson('/api/run/', {
    method: 'POST',
    body: JSON.stringify(params),
  })) as RunResponse
  return data
})

export const fetchJobStatus = createAsyncThunk('job/fetchStatus', async (jobId: string) => {
  const data = (await apiFetchJson(`/api/jobs/${encodeURIComponent(jobId)}/status/`)) as JobStatusResponse
  return data
})

export const fetchJobResult = createAsyncThunk('job/fetchResult', async (jobId: string) => {
  const data = (await apiFetchJson(`/api/jobs/${encodeURIComponent(jobId)}/result/`)) as ResultJson
  return data
})

const jobSlice = createSlice({
  name: 'job',
  initialState,
  reducers: {
    setJobId(state, action: PayloadAction<string | null>) {
      state.jobId = action.payload
    },
    clearJobError(state) {
      state.error = null
    },
    resetJob(state) {
      state.jobId = null
      state.status = null
      state.result = null
      state.loading = false
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(runBacktest.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(runBacktest.fulfilled, (state, action) => {
        state.loading = false
        state.jobId = action.payload.job_id
      })
      .addCase(runBacktest.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to start backtest'
      })
      .addCase(fetchJobStatus.fulfilled, (state, action) => {
        state.status = action.payload
      })
      .addCase(fetchJobStatus.rejected, (state, action) => {
        state.error = action.error.message || 'Failed to fetch status'
      })
      .addCase(fetchJobResult.fulfilled, (state, action) => {
        state.result = action.payload
      })
      .addCase(fetchJobResult.rejected, (state, action) => {
        state.error = action.error.message || 'Failed to fetch result'
      })
  },
})

export const { setJobId, clearJobError, resetJob } = jobSlice.actions
export default jobSlice.reducer
