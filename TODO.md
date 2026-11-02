# TODO

## Phase 1: Foundations
[x] 1.1 Project skeleton, requirements, .gitignore, .env.example, git init
[x] 1.2 llm.py: ask() with disk cache + test
[x] 1.3 state.py (TripState) and schemas.py (TripRequest)
[ ] 1.4 intake node + 3 tests
[ ] 1.5 One-step graph + test
[ ] 1.6 FastAPI: /health and /plan/intake + tests
[ ] 1.7 Review against rules, push to GitHub

## Phase 2: RAG
[ ] 2.1 Guide documents for Jaipur, Chennai, Goa (2-3 each, with source headers)
[ ] 2.2 Chunking with metadata
[ ] 2.3 ingest.py (local embeddings, Chroma)
[ ] 2.4 retrieve(city, query, k) with city filter and empty-result case
[ ] 2.5 retrieve node added to the graph
[ ] 2.6 20 retrieval test questions + hit rate script

## Phase 3: Tools and agent loop
[ ] 3.1 get_weather (Open-Meteo) + mocked tests
[ ] 3.2 get_distance (OpenStreetMap-based) + fallback + tests
[ ] 3.3 data/costs.json (estimates)
[ ] 3.4 fetch node
[ ] 3.5 draft node (structured itinerary, sources, "unverified" labels)
[ ] 3.6 check_budget, check_logistics, check_sources + tests
[ ] 3.7 check and revise nodes, loop capped at 3
[ ] 3.8 run_trip.py terminal runner

## Phase 4: API and frontend
[ ] 4.1 POST /plan streaming progress events
[ ] 4.2 React trip form
[ ] 4.3 Live progress display
[ ] 4.4 Day-by-day timeline with estimated costs
[ ] 4.5 Leaflet map with pins and routes
[ ] 4.6 Citations, "unverified" badge, "estimates" notice
[ ] 4.7 Swap stop / change budget -> re-plan
[ ] 4.8 Loading, error, and empty states + tests

## Phase 5: Accounts, saving, approval
[ ] 5.1 Signup/login (hashed passwords, token auth)
[ ] 5.2 Database tables: users, trips
[ ] 5.3 Approval step and POST /trips/{id}/approve
[ ] 5.4 List, reopen, delete saved trips
[ ] 5.5 Friendly errors (no guide data, tool failure, model failure)
[ ] 5.6 Auth and trip endpoint tests

## Phase 6: Evaluation, deployment, docs
[ ] 6.1 eval/trips.json (18 test trips)
[ ] 6.2 Eval script + results_single_agent.json
[ ] 6.3 Run without retrieval -> results_no_rag.json
[ ] 6.4 Dockerfile(s) and docker-compose
[ ] 6.5 GitHub Actions CI
[ ] 6.6 Deploy to free hosting + /health check
[ ] 6.7 README: architecture diagram, results, limitations, demo video link

## Phase 7 (optional): Multi-agent upgrade (branch: multi-agent)
[ ] 7.1 Budget agent and Logistics agent (parallel review)
[ ] 7.2 Editor agent
[ ] 7.3 Re-run the 18 test trips -> results_multi_agent.json
[ ] 7.4 Single vs multi-agent comparison table in README