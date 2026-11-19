# DocuGoSync

> AI-powered code-to-documentation synchronization — detects when code changes make documentation wrong.

DocuGoSync solves a real developer pain point: code gets updated but the README, API docs, and guides stay wrong. It builds explicit relationships between source code symbols and documentation sections, then detects drift when code changes.

---

## What It Does

1. **Connects** to a GitHub repository or ZIP archive
2. **Indexes** source-code symbols (functions, classes, parameters, env vars)
3. **Parses** documentation into sections (Markdown headings)
4. **Maps** code symbols to the documentation sections that describe them
5. **Detects** drift: outdated signatures, removed parameters, changed defaults
6. **Generates** exact corrections with source-code evidence
7. **Applies** approved corrections directly to documentation files

**Key principle:** Every finding cites exact evidence. No hallucinated behaviour.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+

### Setup

```bash
# Clone or extract the project
cd docugosync

# Backend
pip install -r requirements.txt
cp .env.example .env

# Frontend
cd frontend
npm install
cd ..
```

### Run

```bash
# Terminal 1 — Backend
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Demo Workflow

1. Open the **Repositories** page and upload `tests/fixtures/test_repo.zip`
2. Wait for indexing to complete (the status badge turns green)
3. Go to **Analyze** and select your repository
4. Load the "Function signature change" fixture
5. Click **Detect Drift**
6. See the critical finding: `login()` signature is documented as `login(username, password)` but the code now has `login(username, password, remember=False, mfa_code=None)`
7. The suggested correction is generated automatically
8. Click **Approve** → then **Apply Patch to File**

---

## Architecture

```
docugosync/
├── backend/            FastAPI REST API + orchestration
│   ├── api/routes/     Endpoints: repositories, analysis, drift, github
│   ├── core/           Config, database connection
│   └── services/       Indexer, DriftAnalyzer orchestrators
├── code_indexer/       Python AST + JS regex symbol extraction
├── content_extractor/  Markdown section parser
├── relationship_engine/ Multi-strategy code↔doc mapping
├── drift_detector/     Deterministic drift detection
├── suggestion_engine/  Correction generation (deterministic + AI-augmented)
├── document_crawler/   Repository discovery (filesystem + ZIP + GitHub)
├── github_integration/ Git diff client + webhook handler
├── history_replay/     Historical PR replay testing
├── storage/            SQLAlchemy ORM models (SQLite/PostgreSQL)
├── frontend/           React + TypeScript + Vite + Tailwind dashboard
└── tests/              51 unit + integration tests
```

### Code → Doc Mapping Strategies (in priority order)

| Strategy | Example | Confidence |
|---|---|---|
| Backtick function ref | `` `login(username, password)` `` in section | 0.95 |
| Exact name + backtick | `` `login` `` appears in section | 0.90 |
| Exact name plain text | "login" as word boundary | 0.65 |
| Environment variable | `DATABASE_URL` in env_var list | 0.85 |
| Section heading match | Heading contains symbol name | 0.70 |
| Keyword/camelCase split | "AuthManager" → "auth", "manager" in text | 0.45 |

### Drift Detection Types

| Type | Severity | Example |
|---|---|---|
| Outdated signature | Critical | Docs show `login(user, pass)`, code is `login(user, pass, mfa=None)` |
| Removed parameter | High | Docs mention `--debug` flag that no longer exists |
| Changed default | High | Docs say `timeout=30`, code now has `timeout=60` |
| New required param | High | New required param not documented |
| Deleted symbol | Critical | Function removed but still documented |
| Renamed symbol | Critical | Function renamed but old name in docs |
| Missing documentation | Medium | New public function with no docs |

---

## AI Configuration

The system works **fully without an AI provider** — deterministic AST parsing and Git diffs handle detection. AI augments prose correction quality.

| Provider | Cost | Setup |
|---|---|---|
| None (default) | Free | No config needed |
| Groq | Free tier | `GROQ_API_KEY` in `.env` |
| Ollama | Free (local) | Install [Ollama](https://ollama.com), set `AI_PROVIDER=ollama` |
| OpenAI | Paid | `OPENAI_API_KEY` in `.env` |

---

## GitHub Integration

### Webhook Setup (Phase 3)

1. Go to your GitHub repo → Settings → Webhooks
2. Add webhook: `https://your-server.com/api/github/webhook`
3. Set secret: matches `GITHUB_WEBHOOK_SECRET` in `.env`
4. Events: `push`, `pull_request`

### Personal Access Token (for cloning private repos)

```env
GITHUB_TOKEN=ghp_your_token_here
```

---

## Testing

```bash
# All tests
python -m pytest tests/ -v

# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests (includes end-to-end and history replay)
python -m pytest tests/integration/ -v -s

# Single test category
python -m pytest tests/unit/test_drift_detector.py -v
```

### Test Results

| Category | Tests | Result |
|---|---|---|
| Python AST analyzer | 9 | ✅ All pass |
| Markdown extractor | 7 | ✅ All pass |
| Drift detector (all 12 TCs) | 12 | ✅ All pass |
| Relationship mapper | 5 | ✅ All pass |
| Suggestion generator | 3 | ✅ All pass |
| End-to-end (upload→index→detect→approve) | 10 | ✅ All pass |
| Historical PR replay (3 real repos) | 5 | ✅ 3/3 detected |

---

## Historical Replay

DocuGoSync was tested against fixture cases based on real-world scenarios:

| Repo | Change | Detected |
|---|---|---|
| requests (psf/requests) | `send()` gained `proxies` parameter | ✅ Yes |
| Flask (pallets/flask) | `run()` default port changed 5000→8000 | ✅ Yes |
| httpx (encode/httpx) | `get()` timeout default changed 5.0→30.0 | ✅ Yes |

> **Note:** Test cases use pre-extracted code/doc content. No automated issues or PRs were sent to these repositories.

---

## Known Limitations (Phase 1 MVP)

- Python and JavaScript/TypeScript analysis only (TypeScript uses regex, not Tree-sitter)
- GitHub PR creation requires Phase 3 GitHub App integration
- Webhook-triggered analysis requires a public server URL
- Large repositories (>500 files) may take 30–60 seconds to index
- Semantic embedding matching deferred to Phase 2

---

## Roadmap

| Phase | Status |
|---|---|
| Phase 1: Core MVP (upload, index, detect, suggest, approve) | ✅ Complete |
| Phase 2: AI augmentation, semantic matching, approval workflow | 🔄 Partial |
| Phase 3: GitHub webhooks, PR creation, Checks API | 📋 Planned |
| Phase 4: Historical replay, more languages, incremental indexing | 🔄 Partial |
