# Cairn frontend

Trip plans, traced to their sources. React renders the trip form, streamed planning progress, costs, map, citations and check results.

## Install

Use Node.js 24 and npm. From `frontend/`:

```sh
npm ci
```

## Run

```sh
npm run dev
```

Vite serves the app on port 5173. Start the backend separately.

`VITE_API_URL` sets the backend base URL and defaults to `http://127.0.0.1:8000`. Set it before starting Vite or building; do not put credentials in frontend environment variables.

PowerShell example for a backend on another port:

```powershell
$env:VITE_API_URL = "http://127.0.0.1:8001"
npm run dev
```

## Local preview backend

From the repository root, with the existing Python virtual environment installed:

```powershell
$env:DEMO_MODE = "1"
$env:USE_GEOCODING = "0"
$env:USE_OSRM = "0"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, run `npm run dev` from `frontend/`. The backend serves `/options` and `/plan`; the latter streams completed steps followed by the checked itinerary. Preview output carries the chip **Preview · sample data**. It is not a live generated plan, and this mode does not contact the model provider.

Leave the start date empty for an offline preview. Providing a date can trigger a weather request. Map tiles are fetched from OpenStreetMap. Pins use only coordinates returned by the backend; with place lookup disabled, the map centres on the returned city centre and shows the place list instead of pins. Enabling `USE_GEOCODING=1` separately permits external place lookups.

The backend allows Vite's default local origins. If using another frontend port, set backend `CORS_ORIGINS` to the exact frontend origin before starting it.

## Test and build

From `frontend/`:

```sh
npm test
npm run build
npm run preview
```

Tests mock planning responses and map controls. The build goes into `dist/`; `npm run preview` serves that build locally. Allow its origin in backend CORS settings when testing it against the API.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Reading a plan

The cost summary uses `cost_breakdown` for the whole-trip estimate, budget and categories. Incomplete costs are labelled stops-only and do not imply that the whole trip fits the budget. Costs are estimates, not live prices.

Numbered pins match stop numbers within each day. Dashed lines connect adjacent located stops in order; they are not road routes. The text place list remains available when coordinates or tiles are missing.

Each stop shows its short excerpt and source links, or an unverified badge. The collapsible checks panel retains the backend's reasons and revision count. A reason beginning with `skipped:` is shown as SKIPPED rather than PASS.

The destination search uses `/options`; unsupported searches offer only available destinations. Stop swapping and budget re-planning are not implemented yet.
