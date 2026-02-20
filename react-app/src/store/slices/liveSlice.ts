import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import { apiFetchJson } from '../../api/client'
import type { ResultJson } from '../../api/types'
import { liveChartWebSocket, type ChartUpdateMessage, type ConnectionMessage, type ErrorMessage } from '../../services/websocketService'

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
  websocketConnected: boolean
  websocketError: string | null
}

const initialState: LiveState = {
  activeSessionId: null,
  strategies: [],
  selectedStrategyId: 'break_retest',
  status: null,
  snapshot: null,
  loading: false,
  error: null,
  websocketConnected: false,
  websocketError: null,
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

export const connectWebSocket = createAsyncThunk(
  'live/connectWebSocket',
  async (sessionId: string, { dispatch, rejectWithValue }) => {
    try {
      await liveChartWebSocket.connect(sessionId)
      
      // Set up message handlers
      liveChartWebSocket.onMessage('chart_update', (message: ChartUpdateMessage) => {
        dispatch(updateSnapshotWithWebSocketData(message.data))
      })
      
      liveChartWebSocket.onMessage('connection_established', (message: ConnectionMessage) => {
        console.log('WebSocket connection established:', message.message)
      })
      
      liveChartWebSocket.onMessage('error', (message: ErrorMessage) => {
        dispatch(setWebSocketError(message.message))
      })
      
      // Set up connection status handler
      liveChartWebSocket.onConnectionStatus((connected: boolean) => {
        dispatch(setWebSocketConnectionStatus(connected))
      })
      
      return sessionId
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to connect WebSocket')
    }
  }
)

export const disconnectWebSocket = createAsyncThunk('live/disconnectWebSocket', async () => {
  liveChartWebSocket.disconnect()
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
      state.websocketConnected = false
      state.websocketError = null
    },
    setWebSocketConnectionStatus(state, action: PayloadAction<boolean>) {
      state.websocketConnected = action.payload
      if (action.payload) {
        state.websocketError = null
      }
    },
    setWebSocketError(state, action: PayloadAction<string | null>) {
      state.websocketError = action.payload
      state.websocketConnected = false
    },
    updateSnapshotWithWebSocketData(state, action: PayloadAction<any>) {
      // Update snapshot with WebSocket data
      if (!state.snapshot) {
        state.snapshot = {
          stats: {},
          symbols: {},
        }
      }
      
      const data = action.payload
      const symbol = data.symbol
      
      if (symbol && data.chartData && state.snapshot.symbols) {
        // Update or add symbol data
        state.snapshot.symbols[symbol] = {
          ...state.snapshot.symbols[symbol],
          candles: data.candles || [],
          chartData: data.chartData,
          chartOverlayData: data.chartOverlayData,
        }
      }
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
      .addCase(connectWebSocket.pending, (state) => {
        state.websocketError = null
      })
      .addCase(connectWebSocket.fulfilled, (state, action) => {
        // Connection status is handled by the connection status handler
        console.log('WebSocket connection initiated for session:', action.payload)
      })
      .addCase(connectWebSocket.rejected, (state, action) => {
        state.websocketError = action.payload as string
        state.websocketConnected = false
      })
      .addCase(disconnectWebSocket.fulfilled, (state) => {
        state.websocketConnected = false
        state.websocketError = null
      })
  },
})

export const { 
  setSelectedStrategyId, 
  setActiveSessionId, 
  clearLiveError, 
  resetLive,
  setWebSocketConnectionStatus,
  setWebSocketError,
  updateSnapshotWithWebSocketData
} = liveSlice.actions
export default liveSlice.reducer
