# React Web Dashboard (Trading Bot)

This document describes the React SPA that lives under `react-app/`. It is a replacement UI for the older Django-rendered dashboard under `web-app/`, while **keeping Django/Python as the backend**.

The React app:

- Calls the existing Django API endpoints (JSON over HTTP)
- Uses Redux Toolkit for state management
- Renders the backtest form dynamically from the backend parameter schema (`/api/params/`)
- Displays job status, charts, parameters, and live logs for each backtest job
- Supports presets, recent backtests, and favorite backtests

---

## High-level architecture

- **Backend**: Django app in `web-app/`
  - Runs jobs (backtests) and stores outputs on disk
  - Exposes JSON APIs under `/api/...`

- **Frontend**: Vite + React + TypeScript in `react-app/`
  - SPA routes handled by React Router
  - Centralized state via Redux Toolkit slices
  - Fetch layer via `src/api/client.ts` (`apiFetchJson`) which wraps `fetch()`

### Routing

Defined in `react-app/src/App.tsx`:

- `/`
  - `BacktestFormPage`
- `/jobs/:jobId`
  - `JobPage`

---

## Data transport and formats

### Transport

- The frontend uses `fetch()` to call Django endpoints.
- Requests and responses are JSON.

### Frontend fetch helper

File: `react-app/src/api/client.ts`

- `apiFetchJson(path, init?)`
  - Adds `Accept: application/json`
  - Adds `Content-Type: application/json` if there is a request body
  - Parses JSON (or returns `{ raw: text }` if server returns non-JSON)
  - Throws `Error` when `res.ok` is false

### Core API response types

File: `react-app/src/api/types.ts`

- `RunResponse`
- `JobStatusResponse` (includes `stdout_tail` / `stderr_tail`)
- `ResultJson` (chart series + stats)
- `PresetResponse`, `PresetsListResponse`

---

## Key backend endpoints (what the UI expects)

### Run a backtest

- `POST /api/run/`
- Body: JSON object of params (combined backtest args / env overrides / etc)
- Response: `RunResponse`
  - `job_id`
  - `job_url`, `status_url`, `result_url`

### Poll job status

- `GET /api/jobs/<job_id>/status/`
- Response: `JobStatusResponse`
  - `status`: `queued | running | finished | failed | unknown`
  - `has_result`: boolean
  - `params`: echo of parameters used (nested sections)
  - `stdout_tail`, `stderr_tail`: strings with tail output for live logs

### Fetch job result

- `GET /api/jobs/<job_id>/result/`
- Response: `ResultJson`
  - `symbols`: per-symbol series (candles, EMA, zones, markers, order boxes)
  - `stats`: dictionary of computed stats

### Parameter schema (form generation)

- `GET /api/params/`
- Response: schema describing all available fields

This is the heart of extensibility: adding a new parameter on the backend should appear automatically in the React form.

### Presets

- `GET /api/presets/` (list)
- `POST /api/presets/` (save)
- `GET /api/presets/<name>/` (load)
- `DELETE /api/presets/<name>/` (delete)

---

## Where job data is stored on disk (backend)

The backend stores per-job artifacts under:

- `web-app/var/jobs/<job_id>/`

Common files:

- `params.json`
  - Parameters used to run the job
- `status.json`
  - Status snapshots / metadata
- `result.json`
  - Final result payload served by `/result/`
- `stdout.log`
  - Full stdout
- `stderr.log`
  - Full stderr

The React frontend does **not** read these files directly; it reads them via the Django APIs.

---

## Redux state management

Redux is configured in:

- `react-app/src/store/store.ts`

The app uses Redux Toolkit slices under:

- `react-app/src/store/slices/`

### `paramSchemaSlice`

- Responsibility:
  - Fetch `/api/params/`
  - Store parameter definitions used to render the form

### `paramsSlice`

- Responsibility:
  - Store the current in-progress form values (the user’s selected parameters)
  - Supports `setParam()` / `setAllParams()`

### `jobSlice`

- Responsibility:
  - Store current job id, job status payload, and job result payload
  - Thunks:
    - `runBacktest()` -> `POST /api/run/`
    - `fetchJobStatus()` -> `GET .../status/`
    - `fetchJobResult()` -> `GET .../result/`

### `presetsSlice`

- Responsibility:
  - List presets, load preset values, save preset values, delete presets

### `favoritesSlice`

File: `react-app/src/store/slices/favoritesSlice.ts`

- Responsibility:
  - Store favorite backtests in Redux
  - Persist favorites to `localStorage`

- Local persistence key:
  - `favorite_backtests`

- Thunks:
  - `hydrateFavorites()`
    - Loads persisted favorites from `localStorage` into Redux
  - `addFavoriteAndPersist(entry)`
  - `removeFavoriteAndPersist(jobId)`

Hydration happens on app startup:

- `react-app/src/main.tsx` dispatches `hydrateFavorites()`

---

## Pages and user flows

## 1) Home page: `BacktestFormPage`

File: `react-app/src/pages/BacktestFormPage.tsx`

Responsibilities:

- Fetch parameter schema + preset names on mount
- Render a schema-driven backtest form
- Run a backtest and navigate to the job page
- Show:
  - Favorite Backtests (Redux-backed)
  - Recent Backtests (localStorage-backed)

### Recent backtests persistence

- Key: `recent_backtests`
- Stored in `localStorage`
- Written when a backtest is started (so it shows immediately)
- Displayed as the last 10 entries

### Favorite backtests

- Stored in Redux (`state.favorites.items`)
- Persisted to `localStorage` via the slice
- Displayed above Recent Backtests
- Recent Backtests show a star inside the pill if the job is favorited

### Cookie restore for parameters

- The form values are restored from a cookie named:
  - `bt_params`

This mimics the Django UI behavior (remember last used parameters).

---

## 2) Job details page: `JobPage`

File: `react-app/src/pages/JobPage.tsx`

Responsibilities:

- Read `jobId` from route
- Set current job id in Redux
- Poll `/status/` while the job is running/queued
- Fetch `/result/` once available
- Render:
  - Chart panel (per symbol)
  - Status
  - Stats
  - Parameters used
  - stdout/stderr log views
  - Favorite star toggle

### Polling strategy

- When `status.status` is `queued` or `running`, the page polls `fetchJobStatus(jobId)` on an interval.

### Chart

- Component: `react-app/src/components/BacktestChart.tsx`
- Uses TradingView `lightweight-charts`
- Supports fullscreen toggle (via the Fullscreen API)

### Parameters widget

- The job status payload includes `params` grouped as:
  - `backtest_args`
  - `env_overrides`
  - `meta`

The page renders these using labels from the parameter schema when available.

### stdout/stderr auto-scroll

The stdout/stderr log containers auto-scroll to bottom when the log tail updates.

---

## UI components

Located in `react-app/src/components/`:

- `Layout`
  - Shared page shell
- `Card`
  - Reusable container with title/right slots
- `Button`
  - Basic button
- `Accordion`
  - Collapsible groups for form sections
- `BacktestChart`
  - Charts and overlays

---

## Local persistence summary

- `cookie: bt_params`
  - Stores last used form values

- `localStorage: recent_backtests`
  - Stores last 10 started backtests

- `localStorage: favorite_backtests`
  - Persisted favorites list
  - Source of truth in app runtime is Redux (`favoritesSlice`)

---

## Extending the backtest parameters (backend-driven UI)

The form is schema-driven.

### What you change

- Add/modify a parameter in the backend parameter schema returned by `GET /api/params/`.

### What you do NOT need to change (usually)

- You typically do not need to touch `BacktestFormPage` to get a new input field to appear.

### Required schema fields (conceptual)

Each param definition should include:

- `name`
- `label`
- `group`
- `field_type`: `str | int | float | bool | datetime | choice | hidden`
- optional defaults / choices / constraints

The frontend renders inputs based on `field_type` and automatically groups by `group`.

---

## Development

### Run locally

1) Django backend:

```bash
python3 -m venv web-app/.venv
source web-app/.venv/bin/activate
pip install -r web-app/requirements.txt
python web-app/manage.py runserver
```

2) React dev server:

```bash
cd react-app
npm install
npm run dev
```

Default addresses:

- Django: `http://127.0.0.1:8000`
- React: `http://127.0.0.1:5173`

---

## Troubleshooting / invariants

- The React app assumes the Django server returns JSON for API routes.
- `JobPage` expects status polling to return `stdout_tail` and `stderr_tail` strings (may be empty).
- `ResultJson.symbols` is expected to be a dictionary keyed by symbol.
- Favorites are persisted by the `favoritesSlice`; avoid duplicating localStorage logic elsewhere.
