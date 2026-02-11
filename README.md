# Trading Bot Dashboard (Django + React)

This repository contains a Django backend that runs backtests / live trading sessions and a modern React + Redux SPA dashboard for configuration, monitoring, and charting.

- **Backend**: `web-app/` (Django, Python, runner processes)
- **Frontend**: `react-app/` (Vite + React + TypeScript + Redux Toolkit)

If you only need frontend-specific notes, also see:

- `docs/REACT_APP_DASHBOARD.md`

---

## Repository layout

- `web-app/`
  - Django app that exposes JSON APIs under `/api/...`
  - Spawns runner processes for backtests and live sessions
  - Persists job/session artifacts under `web-app/var/...`
- `react-app/`
  - React SPA that calls the Django JSON APIs
  - Routes:
    - `/` dashboard + form (`BacktestFormPage`)
    - `/jobs/:jobId` backtest details (`JobPage`)
    - `/live/:sessionId` live session details (`LivePage`)
- `docs/`
  - Project docs (React dashboard architecture, notes)

---

## Run locally

### 1) Django backend

```bash
python3 -m venv web-app/.venv
source web-app/.venv/bin/activate
pip install -r web-app/requirements.txt
python web-app/manage.py runserver
```

Default: `http://127.0.0.1:8000`

### 2) React dev server

```bash
cd react-app
npm install
npm run dev
```

Default: `http://127.0.0.1:5173`

Notes:

- The React dev server uses same-origin API calls (`/api/...`) and proxies to Django (see `react-app/vite.config.ts`).

---

## Data transport

- The frontend calls Django APIs using `fetch()`.
- Requests/responses are JSON.
- Fetch helper: `react-app/src/api/client.ts` (`apiFetchJson`).

---

## Backend persistence (disk)

### Backtest jobs

Stored under:

- `web-app/var/jobs/<job_id>/`

Common files:

- `params.json`
- `status.json`
- `result.json` (final)
- `stdout.log`
- `stderr.log`

### Live sessions

Stored under:

- `web-app/var/live/<session_id>/`

Common files:

- `params.json`
- `status.json`
- `snapshot.json` (updated periodically)
- `stdout.log`
- `stderr.log`

There is also a single “active live session” pointer:

- `web-app/var/live/active.json`

---

## Backend APIs (what the UI expects)

### Backtests

- `POST /api/run/`
  - Start a backtest job.
- `GET /api/jobs/<job_id>/status/`
  - Poll status + log tails (`stdout_tail`, `stderr_tail`).
- `GET /api/jobs/<job_id>/result/`
  - Fetch `result.json` chart series + stats.

### Params schema (schema-driven UI)

- `GET /api/params/`
  - Returns param definitions used to render the dashboard form.

### Presets

- `GET /api/presets/`
- `POST /api/presets/`
- `GET /api/presets/<name>/`
- `DELETE /api/presets/<name>/`

### Strategies

- `GET /api/strategies/`
  - Returns strategy options (used by the dashboard selector).

### Live trading

- `POST /api/live/run/`
  - Starts a live session.
  - Enforces **single active live session**.
- `GET /api/live/active/`
  - Returns `{ active_session_id }` for hydration after refresh.
- `GET /api/live/<session_id>/status/`
  - Status + stdout/stderr tails.
  - Clears the active session marker when the session is stopped/errored.
- `GET /api/live/<session_id>/snapshot/`
  - Returns the latest `snapshot.json` (candles + stats).
- `POST /api/live/<session_id>/stop/`
  - Stops the live runner process.

---

## Live runner

- Entrypoint: `web-app/backtests/runner/run_live.py`
- Responsibilities:
  - Initialize MT5
  - Login
  - Fetch candles periodically (per symbol)
  - Write `snapshot.json` and update `status.json`

### Timeframe invariant

The live session MT5 timeframe is derived from the dashboard `timeframe` param.

- The backend overrides `MT5_TIMEFRAME` to match `timeframe` when starting live.
- There is no separate `MT5_TIMEFRAME` param in the schema.

---

## Frontend (React) architecture

### Routing

Defined in `react-app/src/App.tsx`:

- `/` → `BacktestFormPage`
- `/jobs/:jobId` → `JobPage`
- `/live/:sessionId` → `LivePage`

### Redux store

Configured in `react-app/src/store/store.ts`.

Slices (directory: `react-app/src/store/slices/`):

- `paramSchemaSlice`
  - Fetches `/api/params/`
- `paramsSlice`
  - Holds the in-progress form values
- `jobSlice`
  - Runs backtests and polls job status/results
- `presetsSlice`
  - CRUD for presets via Django
- `favoritesSlice`
  - Favorite backtests in Redux, persisted to localStorage
- `liveSlice`
  - Strategy list, live session lifecycle, status/snapshot polling

Hydration on app startup (see `react-app/src/main.tsx`):

- Favorites: `hydrateFavorites()`
- Active live session: `fetchActiveLiveSession()`

---

## Frontend persistence

### Cookie

- `bt_params`
  - Stores last-used form values (mimics Django UI behavior).

### localStorage

- `favorite_backtests`
  - Source of truth is Redux (`favoritesSlice`), persisted here.
- `recent_backtests`
  - Recent backtests list (currently trimmed to 4 entries in UI).
- `recent_live_runs`
  - Recent live sessions list (currently trimmed to 4 entries in UI).
- `mt5_params`
  - MT5 credentials persisted for autofill on refresh.
  - The UI merges these fields into cookie-restored params.

---

## Favorites

- Favorites are handled by Redux (`favoritesSlice`).
- The job page and the dashboard can toggle favorites.
- Favorites are persisted via `localStorage` key `favorite_backtests`.

---

## Extensibility / upgradeability

### Adding a new dashboard parameter

Primary flow:

- Add/modify a `ParamDef` in `web-app/backtests/params.py`.

The React UI is schema-driven:

- It renders inputs based on `field_type` and groups by `group`.
- Most new parameters appear without frontend changes.

### Adding a new strategy

- Add it to `api_strategies` (Django) and to the backend strategy registry logic.
- The dashboard will pick it up via `/api/strategies/`.

---

## Troubleshooting

- If charts look empty, verify `result.json`/`snapshot.json` includes `symbols` keyed by symbol name.
- If live session appears “stuck active”, check:
  - `web-app/var/live/active.json`
  - `web-app/var/live/<id>/status.json` for `state` and `pid`
- If MT5 credentials don’t persist, inspect browser localStorage key `mt5_params`.
