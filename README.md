# GovLens AI

An autonomous, multi-agent AI platform built with **FastAPI**, **LangGraph**, **Groq (Llama models)**, **SQLAlchemy**, and **Next.js 16**.

The platform researches Indian Government recruitment exams (e.g. *BPSC TRE 4.0*, *SSC CGL 2026*, *UPSC CDS 2026*), extracts structured evidence with source citations and confidence scores, resolves conflicting notification data using source-authority rules, evaluates personalized candidate eligibility, supports human-in-the-loop (HITL) section re-research, and exports professional, cited PDF reports.

---

## 1. System Architecture & End-to-End Workflow

```
[ User Input (Next.js UI) ] 
       │
       ▼
[ POST /research (FastAPI) ] ──► Creates Job in SQLite ──► Launches Background Task
                                                                │
   ┌────────────────────────────────────────────────────────────┘
   ▼
[ LangGraph Orchestration Flow ]
   │
   ├──► 1. query_agent (groq/compound-mini)
   │       └── Parses query into org/exam/year/post hints + user profile
   │
   ├──► 2. recruitment_id_agent
   │       ├── Searches official portals for recruitment cycle
   │       └── If Ambiguous: Pauses graph & surfaces Candidate List to UI
   │
   ├──► 3. source_agent (ddgs)
   │       └── Generates 5 adaptive search queries (eligibility, vacancies, fees, pattern, dates)
   │
   ├──► 4. extraction_agent (groq/compound)
   │       └── Fetches page/PDF text, hashes content (SHA256), extracts Pydantic Fact objects
   │
   ├──► 5. conflict_agent
   │       └── Resolves conflicting values (Corrigendum > Notification > Website > Secondary > Blog)
   │
   ├──► 6. verification_agent
   │       └── Re-verifies high-risk fields; max 2 retries; fallback: "Not specified in available official sources"
   │
   ├──► 7. report_agent
   │       └── Synthesizes 14-section report & calculates Personalized Eligibility
   │
   └──► 8. request_agent (HITL Re-entry)
           └── Parses follow-up user request ──► Triggers targeted section re-research ──► Saves Report v1.1
```

---

## 2. File-by-File Code Guide

### Root Directory
- `.gitignore`: Excludes environment files (`.env`), python caches (`__pycache__`), virtual environments (`.venv`), node dependencies (`node_modules`), next build output (`.next`), and SQLite databases (`*.db`).
- `.env.example`: Template for environment variables.
- `README.md`: System documentation & setup guide.

---

### Backend (`backend/`)

#### Configuration & Core App Entrypoint
- `backend/pyproject.toml`: Managed by `uv`. Defines python version `>=3.14` and dependencies (`fastapi`, `uvicorn`, `langgraph`, `langgraph-checkpoint-sqlite`, `groq`, `sqlalchemy`, `ddgs`, `httpx`, `pypdf`, `weasyprint`).
- `backend/conftest.py`: Pytest configuration file that inserts `backend/` into `sys.path` so test files can import `app.*` cleanly.
- `backend/.env`: Local environment file storing `GROQ_API_KEY`, `LLM_MODEL=groq/compound`, `LLM_MODEL_FAST=groq/compound-mini`, `SEARCH_PROVIDER=duckduckgo`, `DATABASE_URL=sqlite:///./app.db`.
- `backend/app/main.py`: The FastAPI application entrypoint.
  - Calls `load_dotenv()` on startup.
  - Implements `lifespan` security check: fails fast if `GROQ_API_KEY` is missing.
  - Initializes database tables (`init_db()`).
  - Configures `CORSMiddleware` (`ALLOWED_ORIGINS`).
  - Exposes health check route (`GET /health`).

#### Data Models & Schemas
- `backend/app/models/domain.py`: Pydantic domain models:
  - `Fact`: Field, value, source URL, source type, source date, confidence score (`0.0 - 1.0`).
  - `Conflict`: Field, list of conflicting facts, resolved value, resolution reason.
  - `SourceItem`: URL, title, snippet, source type classification.
  - `UserProfile`: Candidate education degree, age, category, state.
  - `RecruitmentCandidate`: Disambiguation candidate (name, org, year, advt_number).
- `backend/app/schemas/api_schemas.py`: REST API request/response schemas for `/research`, `/status`, `/resolve-recruitment`, `/report`, `/report/versions`, and `/request-change`.

#### Database Layer
- `backend/app/db/models.py`: SQLAlchemy ORM database models representing the persistent application read model:
  - `JobModel`: Job tracking (`id`, `status`, `current_step`, `candidates_json`, `error`).
  - `RecruitmentModel`: Exam metadata (`id`, `name`, `org`, `year`, `advt_number`, `post`).
  - `SourceModel`: Cited web/PDF sources (`id`, `recruitment_id`, `url`, `title`, `content_hash`).
  - `FactModel`: Extracted facts (`field`, `value`, `confidence`).
  - `ConflictModel`: Detected conflicts & resolution records.
  - `UserRequestModel`: Human-in-the-loop (HITL) follow-up change requests.
  - `ReportModel`: Immutable report versions (`id`, `recruitment_id`, `version`, `changed_sections_json`, `sections_json`).
- `backend/app/db/session.py`: Database session setup using SQLAlchemy `create_engine` and SQLite helper `init_db()`.

#### Services (LLM, Search, Fetcher)
- `backend/app/services/llm.py`: Central LLM abstraction wrapping `groq.Groq` SDK.
  - Features exponential backoff retries for rate limits (`429`).
  - Supports model tiers (`groq/compound` for large extraction vs `groq/compound-mini` for fast parsing).
  - Validates and parses JSON outputs into Pydantic models.
- `backend/app/services/fetcher.py`: Web and PDF fetching engine using `httpx`, `BeautifulSoup` (HTML cleaner), `pypdf` (PDF text extractor), and SHA256 content hashing (`content_hash`).
- `backend/app/services/search/base.py`: Abstract `SearchProvider` base class.
- `backend/app/services/search/duckduckgo_provider.py`: Implementation using `ddgs` library with automated source-type classification (`official_notification`, `official_website`, `secondary`).
- `backend/app/services/search/official.py`: `OfficialSourceSearch` wrapper optimizing search queries for official portals (`.gov.in`, `.nic.in`, BPSC, SSC, UPSC).
- `backend/app/services/search/general.py`: `GeneralWebSearch` fallback.
- `backend/app/services/search/__init__.py`: Search provider factory (`get_search_provider()`).

#### LangGraph Stateful Agent Graph
- `backend/app/graph/state.py`: Defines `ResearchState` (TypedDict) passed across all agent nodes.
- `backend/app/graph/checkpointer.py`: Initializes LangGraph `SqliteSaver` checkpointer for graph state persistence per `thread_id`.
- `backend/app/graph/research_graph.py`: Builds and compiles `StateGraph(ResearchState)` with node wiring and conditional routing (`check_recruitment_ambiguity`).

#### Agents (`backend/app/agents/`)
- `query_agent.py`: Node 1. Uses `groq/compound-mini` to extract exam hints (`org`, `exam_name`, `year`, `post`) and candidate profile details from query text.
- `recruitment_id_agent.py`: Node 2. Checks official sources to determine if query is ambiguous. If multiple recruitment cycles match, sets status to `"ambiguous"` and surfaces candidates.
- `source_agent.py`: Node 3. Generates 5 adaptive search queries and collects official + secondary web sources.
- `extraction_agent.py`: Node 4. Fetches top 8 web/PDF pages, passes up to 12,000 characters per page to `groq/compound`, and extracts structured `Fact` objects with confidence scores.
- `conflict_agent.py`: Node 5. Groups facts by field and applies source authority hierarchy (`Corrigendum > Notification > Website > Secondary > Blog`).
- `verification_agent.py`: Node 6. Evaluates high-risk fields (dates, eligibility, fees, vacancies, links). Retries low-confidence fields max 2 times before setting fallback `"Not specified in the available official sources."`.
- `report_agent.py`: Node 7. Assembles all 14 mandatory report sections from verified facts and evaluates candidate eligibility (`Eligible`, `Not Eligible`, `Needs verification`).
- `request_agent.py`: Node 8. Parses follow-up user requests, identifies affected sections, and routes targeted re-research.

#### PDF Export Engine & API Layer
- `backend/app/pdf/generator.py`: HTML/CSS template renderer converting 14-section report data into PDF byte streams using `WeasyPrint` with HTML fallback.
- `backend/app/api/routes.py`: FastAPI REST API handlers:
  - `POST /research`: Starts async research job via `BackgroundTasks`.
  - `GET /research/{id}/status`: Polling endpoint returning current step, job status, and candidates list if ambiguous.
  - `POST /research/{id}/resolve-recruitment`: Accepts candidate selection and resumes paused graph thread.
  - `GET /research/{id}/report`: Returns latest report version (or specific `?version=`).
  - `GET /research/{id}/report/versions`: Returns list of all report versions.
  - `POST /research/{id}/request-change`: Submits HITL request, triggers targeted re-research, and creates new report version (`v1.1`, `v2.0`).
  - `GET /research/{id}/sources`: Returns cited official & secondary sources.
  - `GET /research/{id}/conflicts`: Returns detected conflicts & resolution rules.
  - `GET /research/{id}/pdf`: Downloads current cited PDF.

#### Unit Tests (`backend/tests/`)
- `test_conflicts.py`: Verifies deterministic conflict resolution (Official vs Blog, Notification vs Corrigendum).
- `test_eligibility.py`: Verifies personalized eligibility rules (exact match, differing qualification rule, missing profile info).
- `test_ambiguity.py`: Verifies ambiguity state detection and graph conditional routing.
- `test_confidence_retries.py`: Verifies bounded field retries (max 2) and fallback emission.
- `test_duckduckgo.py`: Live integration test for `ddgs` web search provider.
- `test_pdf.py`: Verifies WeasyPrint / HTML PDF rendering.

---

### Frontend (`frontend/`)

- `frontend/package.json`: Next.js 16 (React 19 + TypeScript + Tailwind CSS).
- `frontend/app/layout.tsx`: Root HTML layout wrapper.
- `frontend/app/globals.css`: Tailwind CSS configuration and dark theme styles.
- `frontend/app/page.tsx`: Full interactive Web Dashboard UI:
  - Exam Search input bar & candidate profile drawer.
  - Live progress polling bar (`/status`).
  - Ambiguity Candidate Selection Modal.
  - 14-Section Tabbed Report Viewer with Personalized Eligibility badge status (`Eligible`, `Not Eligible`, `Needs verification`).
  - Report Version selector (`v1.0`, `v1.1`).
  - Human-in-the-Loop (HITL) Request Change drawer.
  - Download Cited PDF action button.

---

## 3. Running the Project

### Start Backend
```bash
cd backend
uv run uvicorn app.main:app --reload
```

### Start Frontend
```bash
cd frontend
npm run dev
```

### Run All Unit Tests
```bash
cd backend
uv run pytest
```
