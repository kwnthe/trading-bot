import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'

export type ParamsState = {
  values: Record<string, any>
}

const initialState: ParamsState = {
  values: {},
}

const paramsSlice = createSlice({
  name: 'params',
  initialState,
  reducers: {
    setAllParams(state, action: PayloadAction<Record<string, any>>) {
      state.values = { ...action.payload }
    },
    setParam(state, action: PayloadAction<{ name: string; value: any }>) {
      state.values[action.payload.name] = action.payload.value
    },
    resetParams(state) {
      state.values = {}
    },
  },
})

export const { setAllParams, setParam, resetParams } = paramsSlice.actions
export default paramsSlice.reducer
