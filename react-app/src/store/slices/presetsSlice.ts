import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import { apiFetchJson } from '../../api/client'
import type { PresetsListResponse, PresetResponse } from '../../api/types'

export type PresetsState = {
  names: string[]
  loading: boolean
  error: string | null
}

const initialState: PresetsState = {
  names: [],
  loading: false,
  error: null,
}

export const fetchPresetNames = createAsyncThunk('presets/fetchNames', async () => {
  const data = (await apiFetchJson('/api/presets/')) as PresetsListResponse
  return data.presets || []
})

export const fetchPreset = createAsyncThunk('presets/fetchPreset', async (name: string) => {
  const data = (await apiFetchJson(`/api/presets/${encodeURIComponent(name)}/`)) as PresetResponse
  return data
})

export const savePreset = createAsyncThunk('presets/savePreset', async (arg: { name: string; values: Record<string, any> }) => {
  const data = await apiFetchJson('/api/presets/', {
    method: 'POST',
    body: JSON.stringify({ name: arg.name, values: arg.values }),
  })
  return data
})

export const deletePreset = createAsyncThunk('presets/deletePreset', async (name: string) => {
  const data = await apiFetchJson(`/api/presets/${encodeURIComponent(name)}/`, {
    method: 'DELETE',
  })
  return { name, data }
})

const presetsSlice = createSlice({
  name: 'presets',
  initialState,
  reducers: {
    setPresetNames(state, action: PayloadAction<string[]>) {
      state.names = [...action.payload]
    },
    clearPresetsError(state) {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchPresetNames.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchPresetNames.fulfilled, (state, action) => {
        state.loading = false
        state.names = action.payload
      })
      .addCase(fetchPresetNames.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to load presets'
      })
  },
})

export const { setPresetNames, clearPresetsError } = presetsSlice.actions
export default presetsSlice.reducer
