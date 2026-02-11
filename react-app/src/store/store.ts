import { configureStore } from '@reduxjs/toolkit'

import paramsReducer from './slices/paramsSlice'
import paramSchemaReducer from './slices/paramSchemaSlice'
import presetsReducer from './slices/presetsSlice'
import jobReducer from './slices/jobSlice'
import favoritesReducer from './slices/favoritesSlice'

export const store = configureStore({
  reducer: {
    params: paramsReducer,
    paramSchema: paramSchemaReducer,
    presets: presetsReducer,
    job: jobReducer,
    favorites: favoritesReducer,
  },
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
