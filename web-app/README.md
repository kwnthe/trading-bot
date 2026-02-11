# Trading Bot Web Dashboard (Django)

This is a Django dashboard for running backtests and visualizing results with **TradingView lightweight-charts**.

All web-app code lives under `web-app/`.

## Run locally

From repo root:

```bash
python3 -m venv web-app/.venv
source web-app/.venv/bin/activate
pip install -r web-app/requirements.txt
python web-app/manage.py runserver
```

Then open `http://127.0.0.1:8000/`.

Notes:
- `web-app/requirements.txt` includes `../requirements.txt`, so the runner has access to your existing backtesting dependencies (pandas, backtrader, etc.).
- On macOS/Homebrew Python you may see “externally-managed-environment” (PEP 668) if you try to `pip install` globally; always use the venv above.
- If you already have a separate venv for the trading bot, you can force the runner to use it by setting `BACKTEST_RUNNER_PYTHON` before starting Django:

```bash
export BACKTEST_RUNNER_PYTHON="/absolute/path/to/your/bot-venv/bin/python"
```

## How it works

- The UI posts parameters (defaults are prefilled from your `test.py` and repo `.env`).
- The server launches a **separate Python subprocess** to run `main.backtesting()` with per-run env overrides.
- The subprocess writes:
  - `stdout.log` / `stderr.log` (for live log tailing)
  - `result.json` (OHLC/EMA/zones/trades/stats for the browser chart)

Job artifacts are stored under `web-app/var/jobs/<job_id>/`.

## Pages & API

- **Form page**: `/`
- **Run backtest** (POST): `/run/`
- **Job page**: `/jobs/<job_id>/`
- **Job status API**: `/api/jobs/<job_id>/status/`
  - returns status, pid, error, `stdout_tail`, `stderr_tail`, and `result_url` when ready
- **Job result API**: `/api/jobs/<job_id>/result/`
  - returns JSON used by the browser chart
- **Presets API**:
  - `GET /api/presets/` (list preset names)
  - `POST /api/presets/` (upsert preset)
  - `GET /api/presets/<name>/` (load preset values)
  - `DELETE /api/presets/<name>/` (delete preset)

## Parameters exposed in the UI (with current defaults)

## Extending parameters (single source of truth)

All parameters are defined in one place:

- `web-app/backtests/params.py` → `PARAM_DEFS`

That list drives:

- Django form fields (`web-app/backtests/forms.py`)
- Form rendering/groups on the `/` page (`web-app/backtests/views.py` + template)
- How params are split into:
  - `backtest_args` (passed to `main.backtesting(**backtest_args)`)
  - `env_overrides` (applied as environment variables in the runner subprocess)

To add a new parameter, **append one `ParamDef` to `PARAM_DEFS`** (choose `destination="backtest"` or `destination="env"`).

### Backtesting() call parameters (from `test.py`)

- **symbols**: default `XAGUSD` (comma-separated in UI)
- **timeframe**: default `H1`
- **start_date**: default `2021-11-26 13:10`
- **end_date**: default “now”
- **max_candles**: default empty (= no limit)
- **spread_pips**: default `0.0`

### Env overrides (from `.env` and/or forced in `test.py`)

These are applied **per job** as environment variables in the runner subprocess (so they do not affect the Django process or other jobs).

- **RR**: `.env` has `2`, `test.py` sets `2`
- **INITIAL_EQUITY**: `.env` has `100000000`
- **RISK_PER_TRADE**: `.env` has `0.0001`
- **BREAKOUT_LOOKBACK_PERIOD**: `.env` has `48`
- **ZONE_INVERSION_MARGIN_ATR**: `.env` has `1`, `test.py` sets `1`
- **BREAKOUT_MIN_STRENGTH_ATR**: `.env` has `30`, `test.py` sets `0.2` (UI is prefilled with `test.py`)
- **MIN_RISK_DISTANCE_ATR**: `.env` has `0.5`, `test.py` sets `0.5`
- **SR_CANCELLATION_THRESHOLD_ATR**: `.env` has `0.2`, `test.py` sets `0.2`
- **SL_BUFFER_ATR**: `.env` has `0.3`, `test.py` sets `0.3`
- **EMA_LENGTH**: `.env` has `40`, `test.py` sets `40`
- **CHECK_FOR_DAILY_RSI**: `test.py` sets `True` (UI checkbox)
- **BACKTEST_FETCH_CSV_URL**: `.env` has `http://192.168.2.22:5000` (UI field)
- **MODE**: forced to `backtest` (hidden field)
- **MARKET_TYPE**: from `.env` (hidden field)

## Output format (`result.json`)

The runner converts the Backtrader objects returned by `main.backtesting()` into browser-friendly JSON:

- **candles**: OHLC array for lightweight-charts candlestick series
- **ema**: line series (if available on the strategy)
- **zones**: support/resistance exported as horizontal **segments** (rendered as line series)
- **markers**: trade entry markers (basic)
- **trades**: raw completed trades list (from your strategy) for later use
- **stats**: the `stats` dict returned by `main.backtesting()`

## Where jobs are stored

Each run creates `web-app/var/jobs/<job_id>/` containing:

- `params.json` (what the UI submitted)
- `status.json` (`queued` → `running` → `finished`/`failed`)
- `stdout.log`, `stderr.log`
- `result.json` (only when finished)

## Presets

Presets are stored locally at:

- `web-app/var/presets.json`

You can create/save/load presets from the `/` page. The file is under `web-app/var/` so it won’t be committed (it’s in `web-app/.gitignore`).

## Cookie persistence

When you click **Run backtest**, the dashboard saves the current form values into a cookie (`bt_params`) and restores them next time you open `/`.

## Lightweight-charts usage

The job page loads TradingView lightweight-charts via CDN and renders:

- Candles
- EMA line
- Support/resistance segments (from `cerebro.data_indicators[*]['breakout']` when present)
- Basic entry markers

Implementation lives in `web-app/static/backtests/app.js`.

## Optional / next steps (future prompt)

- **True live log streaming**: switch polling to SSE or WebSocket and stream your `self.log_trade(...)` events.
- **More overlays**: SL/TP boxes, exit markers, per-trade hover tooltips (we already export `trades`).


