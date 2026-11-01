# Trip Planner Agent: Build Brief

## What we are building
A full-stack web app where a user describes a trip and an AI agent builds a
day-by-day itinerary from travel guides (RAG) and live weather/distance data.
The agent checks its own plan against budget and timing, revises it
(max 3 times), cites its sources, and asks the user to approve before saving.
Cities: Jaipur, Chennai, Goa only.

Features: trip form; live progress; itinerary timeline; map; a source
citation for every suggestion; "unverified" labels where no guide data
exists; edit and re-plan; approval step; accounts and saved trips.

Not included: booking, live prices or availability, other cities.
Costs are ESTIMATES from guide text plus a small cost table; say so in the UI.

## Stack
Backend: Python, FastAPI, LangGraph, Pydantic, pytest.
Vector store: Chroma with local sentence-transformers embeddings.
Model: a free-tier API for a free-tier LLM API (provider not chosen yet, ask me before writing llm.py), called ONLY through ask() in llm.py.
Live data: Open-Meteo (weather), OpenStreetMap-based distance/geocoding.
Frontend: React with Leaflet. Database: SQLite (keep it swappable to Postgres).
Deploy: Docker, GitHub Actions CI, free hosting.

## Rules (apply to every phase)
- One graph step = one function in nodes.py. No giant functions.
- All steps read and write the shared TripState (graph/state.py).
- All model calls go through ask() in llm.py. It caches responses on disk.
- Never hardcode keys. Use .env, keep .env.example updated.
- Do not add libraries beyond this brief without asking me first.
- Every node, tool and endpoint gets a test. Mock model calls in tests.
- Keep the budget and logistics checks as separate functions that return
  (passed: bool, reason: str). They may later become agents.
- Log each graph step: node name, short input, short output, seconds taken.
- Keep the repo clean: no dead code, no unrequested features.
- If something in the brief is unclear or a free API fails, say so and ask
  instead of guessing.
- Commit using the repository's existing Git config (user.name and user.email). Never set or override the author.

## How to work (apply to every phase)
- Work through the phase's tasks in order. After each task: run its tests,
  tick it in TODO.md, and make a git commit with a clear message.
- TODO.md lists every phase and task as checkboxes. Create it in Phase 1.
- At the END of each phase, STOP and print:
  1. What was built (a few lines, plain language).
  2. Verify: the exact commands I should run and what I should see.
  3. Three "explain it back" questions about this phase. Do not answer
     them unless I ask.
  4. Anything uncertain, skipped, or that deviates from the brief.
  Then wait. Do not start the next phase until I paste the starter prompt.

## Phases

### Phase 1: Foundations
Create backend/app/{main.py, llm.py, schemas.py, graph/{state.py, nodes.py,
build.py}}, backend/tests/, requirements.txt, .gitignore (.env, cache/,
chroma/, __pycache__/, .venv/), .env.example. Init git.
- llm.py: ask(prompt, model) hashes model+prompt; returns cache/<hash>.json
  if present (print "cache hit"), else calls the model, saves, returns.
- state.py: TripState (TypedDict): user_input dict, request dict|None,
  passages list, live_data dict, draft dict|None, feedback list[str],
  revisions int.
- schemas.py: TripRequest (destination: Jaipur|Chennai|Goa; days 1-7;
  budget > 0; interests list[str]; style relaxed|packed).
- nodes.py: intake(state): ask() for JSON matching TripRequest, validate,
  return {"request": ...} or {"feedback": [reason]} without crashing.
- build.py: LangGraph graph with intake only; expose compiled graph.
- main.py: GET /health; POST /plan/intake (422 with reason on failure).
- Tests: cache hit, schema validation, intake (normal, missing budget,
  nonsense destination), graph, API.
Done when: a trip form to /plan/intake returns a structured request and
all tests pass.

### Phase 2: RAG
- data/guides/: 2-3 documents per city with a header (city, source name,
  source URL). Use open sources such as Wikivoyage with attribution; for
  anything else ask me to supply the text. Do not scrape sites whose
  terms forbid it.
- chunking: split by headings, then max ~250 words, 1-2 sentence overlap;
  metadata: city, section, source_name, source_url.
- ingest.py: chunk, embed locally, store in Chroma (re-runnable).
- retrieve(city, query, k=4): filter by city, return text, source, section;
  return [] if nothing relevant.
- retrieve node: writes state["passages"]; add after intake in the graph.
- tests/retrieval_cases.json: 20 questions with the expected source chunk;
  a script that prints the hit rate (expected chunk in top 4).
Done when: retrieval works for all 3 cities, hit rate is printed, tests pass.

### Phase 3: Tools and the agent loop
- tools: get_weather(city, dates) via Open-Meteo; get_distance(a, b) via
  an OpenStreetMap-based service with a simple fallback; both cached and
  tested with mocked HTTP.
- data/costs.json: small table of typical costs per city (entry fees,
  meals, local transport). Label as estimates.
- fetch node: writes state["live_data"].
- draft node: ask() writes the itinerary as structured JSON (days, stops,
  time slots, estimated cost, source for each stop). Stops with no
  supporting passage are marked "unverified".
- checks: check_budget (total within budget), check_logistics (travel
  time between stops realistic, no outdoor stops on heavy-rain days),
  check_sources (every stop has a source or the unverified label).
- check node and revise node: failed checks put reasons in
  state["feedback"]; revise sends them back to the model; loop at most
  3 times (state["revisions"]), then finish with the remaining issues
  listed to the user.
- graph: intake -> retrieve -> fetch -> draft -> check -> (revise ->
  check)* -> END.
- A terminal script run_trip.py to run the whole flow.
- Tests: each check on passing and failing plans; the loop stops at 3.
Done when: run_trip.py produces a cited itinerary, and a deliberately
over-budget request gets fixed or reported.

### Phase 4: API and frontend
- POST /plan streams progress events (server-sent events) per node, then
  the final plan. Keep /plan/intake.
- React app: trip form; progress display; day-by-day timeline with
  estimated costs; Leaflet map with pins and routes per day; citation
  next to every stop; "unverified" badge; "costs are estimates" notice;
  controls to swap a stop or change the budget, which triggers a re-plan.
- Handle loading, error and empty states properly.
- Tests for the endpoints; basic component tests.
Done when: a trip can be planned from the browser and shown with citations.

### Phase 5: Accounts, saving, approval
- Email + password signup/login (hashed passwords, token auth), SQLite
  storage via an ORM; tables: users, trips.
- Approval step: the plan is shown, and only POST /trips/{id}/approve
  saves it as approved. List, reopen and delete saved trips.
- Friendly errors for: no guide data, tool failure, model failure.
- Tests for auth and trip endpoints.
Done when: a user can sign up, plan, approve, save and reopen a trip.

### Phase 6: Evaluation, deployment, docs
- eval/trips.json: 18 test trips across the 3 cities, varied budgets,
  days and interests (include a few impossible budgets).
- eval script records per trip: passes budget and logistics checks,
  unsupported claims (stops with no source and no unverified label),
  seconds per plan, number of model calls. Save results to
  eval/results_single_agent.json and print a summary.
- Run again with retrieval turned off and save eval/results_no_rag.json
  to show what RAG adds.
- Dockerfile(s), docker-compose, GitHub Actions CI (tests on every push),
  deployment config for free hosting, /health check.
- README: what it does, architecture diagram (Mermaid), workflow, how to
  run, results table, limitations, what I would do at scale. Add a
  placeholder for a demo video link.
Done when: the app runs from docker-compose, CI is green, and the README
has real numbers.

### Phase 7 (optional): Multi-agent upgrade
Do this on a new branch named multi-agent. Keep main untouched.
- Convert check_budget and check_logistics into a Budget agent and a
  Logistics agent (own instructions) that review the draft in parallel.
- Add an Editor agent that merges their feedback and revises.
- Keep the same state, tools, retrieval and 3-revision cap.
- Re-run the same 18 test trips and save eval/results_multi_agent.json.
- Add a comparison table (single vs multi-agent) to the README: pass
  rate, unsupported claims, time per plan, model calls per plan. Report
  honestly if it is not better.
Done when: the comparison is in the README.