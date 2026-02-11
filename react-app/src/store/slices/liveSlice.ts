import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import { apiFetchJson } from '../../api/client'
import type { ResultJson } from '../../api/types'

export type StrategyInfo = {
  id: string
  label: string
  description?: string
}

export type LiveRunResponse = {
  ok: boolean
  session_id: string
  status_url: string
  snapshot_url: string
  stop_url: string
}

export type LiveStatusState = 'queued' | 'running' | 'stopped' | 'error' | 'unknown'

export type LiveStatusResponse = {
  session_id: string
  state: LiveStatusState
  created_at?: string
  updated_at?: string
  pid?: number | string | null
  python_executable?: string | null
  returncode?: number | null
  error?: string | null
  latest_seq?: number
  params?: any
  stdout_tail?: string
  stderr_tail?: string
  has_snapshot?: boolean
  snapshot_url?: string | null
}

export type LiveState = {
  activeSessionId: string | null
  strategies: StrategyInfo[]
  selectedStrategyId: string
  status: LiveStatusResponse | null
  snapshot: ResultJson | null
  loading: boolean
  error: string | null
}

const initialState: LiveState = {
  activeSessionId: null,
  strategies: [],
  selectedStrategyId: 'break_retest',
  status: null,
  snapshot: null,
  loading: false,
  error: null,
}

export const fetchStrategies = createAsyncThunk('live/fetchStrategies', async () => {
  const data = (await apiFetchJson('/api/strategies/')) as { strategies: StrategyInfo[] }
  return data.strategies || []
})

export const fetchActiveLiveSession = createAsyncThunk('live/fetchActive', async () => {
  const data = (await apiFetchJson('/api/live/active/')) as { active_session_id: string | null }
  return data.active_session_id || null
})

export const startLive = createAsyncThunk('live/start', async (payload: Record<string, any>) => {
  const data = (await apiFetchJson('/api/live/run/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })) as LiveRunResponse
  return data
})

export const fetchLiveStatus = createAsyncThunk('live/fetchStatus', async (sessionId: string) => {
  const data = (await apiFetchJson(`/api/live/${encodeURIComponent(sessionId)}/status/`)) as LiveStatusResponse
  return data
})

export const fetchLiveSnapshot = createAsyncThunk('live/fetchSnapshot', async (sessionId: string) => {
  const data = (await apiFetchJson(`/api/live/${encodeURIComponent(sessionId)}/snapshot/`)) as ResultJson
  return data
})

export const stopLive = createAsyncThunk('live/stop', async (sessionId: string) => {
  const data = (await apiFetchJson(`/api/live/${encodeURIComponent(sessionId)}/stop/`, {
    method: 'POST',
  })) as { ok: boolean; killed: boolean }
  return { sessionId, ...data }
})

const liveSlice = createSlice({
  name: 'live',
  initialState,
  reducers: {
    setSelectedStrategyId(state, action: PayloadAction<string>) {
      state.selectedStrategyId = action.payload
    },
    setActiveSessionId(state, action: PayloadAction<string | null>) {
      state.activeSessionId = action.payload
    },
    clearLiveError(state) {
      state.error = null
    },
    resetLive(state) {
      state.activeSessionId = null
      state.status = null
      state.snapshot = null
      state.loading = false
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchStrategies.fulfilled, (state, action) => {
        state.strategies = action.payload || []
        if (!state.selectedStrategyId && state.strategies.length) {
          state.selectedStrategyId = state.strategies[0].id
        }
      })
      .addCase(fetchActiveLiveSession.fulfilled, (state, action) => {
        state.activeSessionId = action.payload
      })
      .addCase(fetchActiveLiveSession.rejected, () => {
        // ignore - active session is optional
      })
      .addCase(startLive.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(startLive.fulfilled, (state, action) => {
        state.loading = false
        state.activeSessionId = action.payload.session_id
      })
      .addCase(startLive.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to start live run'
      })
      .addCase(fetchLiveStatus.fulfilled, (state, action) => {
        state.status = action.payload
        const st = action.payload?.state
        if ((st === 'stopped' || st === 'error') && state.activeSessionId === action.payload.session_id) {
          state.activeSessionId = null
        }
      })
      .addCase(fetchLiveStatus.rejected, (state, action) => {
        state.error = action.error.message || 'Failed to fetch live status'
      })
      .addCase(fetchLiveSnapshot.fulfilled, (state, action) => {
        state.snapshot = action.payload
      })
      .addCase(fetchLiveSnapshot.rejected, (state, action) => {
        state.error = action.error.message || 'Failed to fetch live snapshot'
      })
      .addCase(stopLive.fulfilled, (state) => {
        state.activeSessionId = null
        if (state.status) state.status = { ...state.status, state: 'stopped' }
      })
      .addCase(stopLive.rejected, (state, action) => {
        state.error = action.error.message || 'Failed to stop live session'
      })
  },
})

export const { setSelectedStrategyId, setActiveSessionId, clearLiveError, resetLive } = liveSlice.actions
export default liveSlice.reducer
