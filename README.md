# Web Data Scraping Assistant (WDSP)

FastAPI backend + Vite/React frontend for decision-based scraping:

1. **Document HTML** (server-rendered)
2. **XHR/API** (only with a user-provided API URL)
3. **Selenium** (only when explicitly enabled)

## Production readiness (important)

This is **good enough for student research** if you deploy it **privately** (your machine / a VM / behind authentication).


### Critical deployment safeguards

- **SSRF protection**: enabled by default via `WDSP_BLOCK_PRIVATE_NETWORKS=true`.
  - This blocks URLs that resolve to private/internal IP ranges.
  - Only disable it (`WDSP_BLOCK_PRIVATE_NETWORKS=false`) if you fully trust users.
- **CORS**: configure allowed origins via `WDSP_CORS_ALLOW_ORIGINS`.
- **Resource limits**: scraping is slow; Selenium can be very slow/heavy.


## Run locally

### Backend

```powershell
cd backend
..\.venv312\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check: `GET http://127.0.0.1:8000/healthz`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

- Dev mode uses Vite proxy for `/analyze/*` and `/download/*`.
- For preview/build without proxy, set `VITE_BACKEND_URL=http://127.0.0.1:8000` (see `frontend/.env.example`).

## Environment variables

Backend (prefix `WDSP_`):

- `WDSP_CORS_ALLOW_ORIGINS`: JSON array (`["https://your-frontend"]`) or comma-separated string.
- `WDSP_EXPORTS_DIR`: CSV export directory (default `exports`).
- `WDSP_BLOCK_PRIVATE_NETWORKS`: `true|false` (default `true`).
- `WDSP_HTTP_MAX_BYTES`: max response size in bytes (default 2,000,000).
- `WDSP_HTTP_CONNECT_TIMEOUT_S`, `WDSP_HTTP_READ_TIMEOUT_S`: request timeouts.

## Selenium in deployment

Selenium requires a working Chrome/Chromium + driver environment.

- On a local Windows machine (what you’ve been using), this typically works.
- In Docker/Linux deployments, you usually need to install Chromium and extra OS deps, or run Selenium as a separate service.
