import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'

export type FavoriteBacktest = {
  jobId: string
  symbols: string
  startDate?: string
  endDate?: string
  createdAt: number
  name?: string
}

export type FavoritesState = {
  items: FavoriteBacktest[]
  hydrated: boolean
}

const FAVORITES_KEY = 'favorite_backtests'

function safeString(v: any): string {
  if (v === null || v === undefined) return ''
  return String(v)
}

function loadFromStorage(): FavoriteBacktest[] {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((x) => x && typeof x === 'object' && typeof x.jobId === 'string')
      .map((x) => ({
        jobId: String(x.jobId),
        symbols: safeString(x.symbols),
        startDate: x.startDate ? String(x.startDate) : undefined,
        endDate: x.endDate ? String(x.endDate) : undefined,
        createdAt: typeof x.createdAt === 'number' ? x.createdAt : Date.now(),
        name: x.name ? String(x.name) : undefined,
      }))
  } catch {
    return []
  }
}

function saveToStorage(items: FavoriteBacktest[]) {
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(items))
  } catch {
    // ignore
  }
}

export const hydrateFavorites = createAsyncThunk('favorites/hydrate', async () => {
  return loadFromStorage()
})

export const addFavoriteAndPersist = createAsyncThunk(
  'favorites/addAndPersist',
  async (entry: FavoriteBacktest, { getState }) => {
    const state = getState() as any
    const existing: FavoriteBacktest[] = state.favorites?.items || []
    const next = [entry, ...existing.filter((f) => f.jobId !== entry.jobId)]
    saveToStorage(next)
    return next
  },
)

export const removeFavoriteAndPersist = createAsyncThunk(
  'favorites/removeAndPersist',
  async (jobId: string, { getState }) => {
    const state = getState() as any
    const existing: FavoriteBacktest[] = state.favorites?.items || []
    const next = existing.filter((f) => f.jobId !== jobId)
    saveToStorage(next)
    return next
  },
)

const initialState: FavoritesState = {
  items: [],
  hydrated: false,
}

const favoritesSlice = createSlice({
  name: 'favorites',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(hydrateFavorites.fulfilled, (state, action) => {
        state.items = action.payload || []
        state.hydrated = true
      })
      .addCase(addFavoriteAndPersist.fulfilled, (state, action) => {
        state.items = action.payload || []
        state.hydrated = true
      })
      .addCase(removeFavoriteAndPersist.fulfilled, (state, action) => {
        state.items = action.payload || []
        state.hydrated = true
      })
  },
})

export default favoritesSlice.reducer
