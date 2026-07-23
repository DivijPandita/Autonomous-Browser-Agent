# Autonomous Browser Agent

An AI agent that browses real websites - clicking, typing, searching, extracting
data - to complete a natural-language task end to end.

## Architecture

```
                          ┌─────────────────────┐
   POST /tasks            │   FastAPI (app/main) │
   {instruction, url} ───▶│   app/api/routes.py  │
                          └──────────┬───────────┘
                                     │ background task
                                     ▼
                          ┌─────────────────────────┐
                          │   LangGraph state graph   │
                          │   app/agent/graph.py      │
                          │                           │
                          │   ┌─────────┐             │
                          │   │ perceive │◀───┐        │
                          │   └────┬────┘    │        │
                          │        ▼         │        │
                          │   ┌─────────┐    │loop     │
                          │   │  plan    │    │until    │
                          │   │ (LLM)    │    │done or  │
                          │   └────┬────┘    │max_steps│
                          │        ▼         │        │
                          │   ┌─────────┐    │        │
                          │   │  act     │────┘        │
                          │   └─────────┘             │
                          └──────────┬────────────────┘
                                     │ drives
                                     ▼
                          ┌─────────────────────┐
                          │  Playwright browser   │
                          │  app/browser/controller│
                          └─────────────────────┘

                          ┌─────────────────────┐
                          │   PostgreSQL          │
                          │   tasks / steps /      │
                          │   extracted_data       │
                          └─────────────────────┘
```

**The loop, in plain terms:**
1. **Perceive** - read the current URL, a trimmed dump of visible text, and a
   *numbered list of every clickable/typeable element on the page* (this is
   the "set-of-marks" trick real browser agents use, since asking an LLM to
   invent CSS selectors blindly is unreliable).
2. **Plan** - send that + task instruction + recent history to GPT-5, which
   returns one JSON action: `navigate`, `click`, `type`, `scroll`, `extract`,
   `wait`, or `finish`.
3. **Act** - `app/agent/tools.py` executes that action against the real
   browser via Playwright, and logs the outcome.
4. Repeat until the model calls `finish` or `max_steps` is hit.

Every step (thought, action, outcome) is persisted to Postgres via
`app/db/models.py`, so you get a full audit trail per task - useful both for
debugging and for showing off in an interview ("here's how I made the agent's
reasoning inspectable").

## Why this tech stack

- **LangGraph** - the agent is fundamentally a loop with state and
  conditional branching (keep going / stop). A graph makes that explicit and
  easy to extend later (e.g. add a "verify" node, a "replan on failure" node).
- **Playwright** over Selenium - faster, better async support, built-in
  auto-waiting, and easier element/accessibility introspection.
- **FastAPI** - async-native, so it plays nicely with Playwright's async API
  and Postgres via asyncpg without blocking.
- **PostgreSQL** - relational fits naturally here (tasks → steps →
  extracted_data is a clean 1-to-many-to-many shape), and it's the DB
  interviewers expect you to know.

## Setup (WSL + VSCode)

```bash
# 1. Clone/open the project in WSL, then create a venv
cd autonomous-browser-agent
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright's browser binaries (separate from the pip package)
playwright install chromium
playwright install-deps   # installs OS-level libs Chromium needs on Linux/WSL

# 4. Copy env template and fill in your OpenAI key
cp .env.example .env
# edit .env - set OPENAI_API_KEY, and OPENAI_MODEL if gpt-5 isn't available
# on your account yet (gpt-4o / gpt-4o-mini work fine as a placeholder)

# 5. Start Postgres (needs Docker Desktop with WSL integration enabled)
docker compose up -d

# 6. Run the API
uvicorn app.main:app --reload

# 7. In another terminal, fire a test task
python tests/manual_run.py
```

If you don't want Docker, install Postgres directly in WSL
(`sudo apt install postgresql`) and update `DATABASE_URL` / `SYNC_DATABASE_URL`
in `.env` to match.

## API

- `POST /tasks` `{"instruction": "...", "start_url": "https://..."}` → creates
  and kicks off a task in the background, returns immediately with task id.
- `GET /tasks/{id}` → status, final result/error, and full step-by-step log.
- `GET /tasks` → list all tasks.

## Project structure

```
app/
  main.py              FastAPI app + startup
  core/config.py        env-driven settings
  api/routes.py          HTTP endpoints
  agent/
    state.py             AgentState (the graph's shared memory)
    graph.py              builds & runs the LangGraph state machine
    nodes.py               perceive / plan / act node implementations
    tools.py                action schema + executor
  browser/controller.py    Playwright wrapper, element numbering
  db/
    models.py               SQLAlchemy models
    session.py                async engine/session
  schemas/task.py             Pydantic I/O schemas
tests/manual_run.py            quick end-to-end smoke test
docker-compose.yml               local Postgres
requirements.txt
.env.example
```

## Where to take it next (good talking points for interviews)

- **Reliability**: add a `verify` node after `act` that re-checks whether the
  action actually had the intended effect (e.g. did the URL change, did an
  expected element appear) before looping back - right now failures only
  surface via the next `plan` call reading history.
- **Retries / self-correction**: wrap `act` in `tenacity` retries for
  transient failures (element not yet rendered, network blip).
- **Parallel tasks**: move execution off FastAPI's `BackgroundTasks` and onto
  a real queue (Celery + Redis, or an async worker pool) so many tasks run
  concurrently without blocking the API process.
- **Auth-required sites**: add a `context.storage_state()` save/load flow so
  the agent can reuse a logged-in session instead of logging in every run.
- **Guardrails**: whitelist/blacklist domains, cap money-spending actions
  behind human confirmation, add a `--dry-run` mode that plans without acting.
- **Evaluation**: build a small benchmark of 10-20 fixed tasks with known
  expected outcomes, and track success rate as you tweak prompts/models -
  this is exactly the kind of "I measured it" detail that stands out in
  placement interviews.