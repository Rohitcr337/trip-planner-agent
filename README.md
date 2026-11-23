# Cairn

Cairn builds source-traced trip itineraries for Jaipur, Chennai and Goa. It combines local guide retrieval, weather and cost estimates, a checked itinerary draft, and a frontend that streams progress and displays sources.

## How it works

```text
trip form -> intake -> retrieve guide passages -> fetch weather/costs
          -> draft itinerary -> locate stops -> check/revise -> streamed result
```

## Features

- Structured trip intake with destination, days, budget, interests, pace, start date and places to avoid.
- TF-IDF guide retrieval with source citations and rejection of unsupported questions.
- Demo mode with deterministic sample plans and no model-provider call.
- Weather and estimated cost data when configured and available.
- Itinerary checks, revision feedback, unresolved warnings and stop coordinates.
- React UI with progress streaming, cost summary, map, citations, checks and stop swapping.

## Tech stack

| Area | Technology |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic |
| Workflow | LangGraph |
| Retrieval | scikit-learn TF-IDF, NumPy cosine similarity, joblib |
| Frontend | React, Vite, Tailwind CSS |
| Map | Leaflet and React Leaflet |
| Model integration | Google GenAI SDK |

## Project structure

- `backend/app/` contains the API, graph nodes, retrieval, checks, tools and sample model.
- `backend/tests/` contains backend unit and integration tests plus retrieval cases.
- `frontend/src/` contains the React application and component tests.
- `data/guides/` contains fetched guide files used to build the local index.
- `scripts/` contains guide-fetching and retrieval-evaluation utilities.
- `docs/` contains retrieval experiment notes.
- `index/` is the generated local retrieval index and is not committed.

## Getting started

### Backend

From the repository root, create and activate a Python 3.12 virtual environment, then install the requirements:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the model and optional service settings. Fetch the guides and build the local index:

```powershell
.\.venv\Scripts\python.exe scripts\fetch_guides.py
.\.venv\Scripts\python.exe ingest.py
```

For a local deterministic preview, run:

```powershell
$env:DEMO_MODE = "1"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

In a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal.

## Demo mode

Set `DEMO_MODE=1` for deterministic offline sample plans. It does not call the model provider; map tiles and any explicitly enabled external weather or place services can still make network requests. Costs in demo and live plans are estimates.

## Tests

Backend tests run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Frontend tests and the production build run from `frontend/`:

```powershell
npm test
npm run build
```

## Evaluation results

The easy set puts 20 of 20 answerable questions in the top 4, with 18 of 20 first and MRR 0.950. The hard set puts 8 of 15 answerable questions in the top 4, with 7 of 15 first and MRR 0.483; 3 of 5 unanswerable questions are rejected. TF-IDF is word-based, so wording and morphology can affect retrieval. See [docs/retrieval_results.md](docs/retrieval_results.md) for experiments that were tried and reverted.

## Limitations

- Only three destinations are supported.
- Costs are estimates, not live prices.
- Retrieval is word-based rather than neural.
- The model provider has a small daily free-tier quota.
- There are no user accounts yet.

## Roadmap

Accounts and an approval step are planned, along with Docker packaging and neural embeddings.

## Data note

`scripts/fetch_guides.py` fetches guide text from Wikivoyage through its public API. The fetched guide files are local data and are not committed.
