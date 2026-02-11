# Trading Bot Web Dashboard (React + Redux)

This is a React SPA alternative to the existing Django dashboard under `web-app/`.

It keeps **Python/Django** as the backend and calls the same job APIs:

- `POST /api/run/`
- `GET /api/jobs/<job_id>/status/`
- `GET /api/jobs/<job_id>/result/`
- `GET/POST /api/presets/`
- `GET/DELETE /api/presets/<name>/`

The UI is implemented with:

- React + TypeScript
- Redux Toolkit (`@reduxjs/toolkit` + `react-redux`)
- React Router
- TradingView `lightweight-charts`

## Run locally

1) Start the Django backend:

```bash
python3 -m venv web-app/.venv
source web-app/.venv/bin/activate
pip install -r web-app/requirements.txt
python web-app/manage.py runserver
```

2) Start the React dev server:

```bash
cd react-app
npm install
npm run dev
```

Then open:

- `http://127.0.0.1:5173/`

## Notes

- Dev-time API calls are same-origin (`/api/...`) and proxied by Vite to `http://127.0.0.1:8000` (see `vite.config.ts`).
- The form persists the last-used parameters in a cookie (`bt_params`) like the Django version.
- Presets are stored by Django in `web-app/var/presets.json` (same as the Django UI).
