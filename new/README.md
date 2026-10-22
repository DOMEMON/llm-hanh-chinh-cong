# Hành chính công — Design B

This workspace is **Design B**, the new retrieval-and-generation prototype,
adapted from (and intentionally distinct from) the earlier G1 chat application
preserved in [`old/`](../old/). It is intended for local evaluation with the
supplied procedure corpus. It is not verified legal advice.

## Quick start on Windows

### Prerequisites

- Windows 10/11 and PowerShell.
- Node.js 20.19 or newer (tested with 24.20.0).
- Python 3.12 (tested with 3.12.10).
- PostgreSQL 17, running locally, plus an empty database and login for this
  prototype. The tested local cluster uses port 5433.

### Install project dependencies

From the repository root, run this single command:

```powershell
powershell -ExecutionPolicy Bypass -File .\new\scripts\setup-local.ps1
```

It creates the backend virtual environment, installs the backend, retrieval,
and generation packages, installs the web dependencies from the lockfile, and
creates local `.env` files only when they do not already exist. It does not
install or configure PostgreSQL or download the optional model.

### Configure and start

1. Create a dedicated PostgreSQL role and empty database (if they do not
   already exist), then update `new/person2-backend/.env` with those values.
   Do not reuse a database containing unrelated data. Keep `.env` local.
2. Import the supplied corpus once, from the repository root:

   ```powershell
   .\new\person2-backend\.venv\Scripts\python.exe `
     .\new\person2-backend\scripts\import_corpus.py .\new\data\corpus
   ```

3. Start the API in a PowerShell terminal:

   ```powershell
   Set-Location .\new\person2-backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

   Confirm it is healthy at `http://127.0.0.1:8000/health`.
4. Start the web app in a second terminal:

   ```powershell
   Set-Location .\new\web
   npm.cmd run dev -- --host 127.0.0.1
   ```

   Open `http://127.0.0.1:3000`.

The default generator is a deterministic extractive mock. To use the
previously tested Qwen3 1.7B local model instead, follow the optional model
instructions in [`web/README.md`](web/README.md). Model download and model
server startup are separate from the dependency-install command.

## What Design B changes from the old application

The old G1 application is preserved under `old/`. Its web UI was designed
around login, conversation/message routes, and feedback. Design B instead
connects the web directly to the new backend's `POST /api/v1/answer` contract.
It has no login or feedback workflow; a conversation session ID supports
follow-up questions, while the visible transcript is kept in the current
browser tab.

Design B uses the new supplied corpus and a retrieval-first pipeline. It
returns grounded-answer statuses and citations; the generator can be the
default extractive mock or an optional local model. The new backend and its
contracts—not the old G1 routes or old core policies—define this prototype.
The corpus is marked draft, and successful citations demonstrate traceability,
not legal validity or semantic correctness.

## Implementation at a glance

- **Track owners:** Person 1 — MinhKek (corpus and retrieval); Person 2 —
  BanuTheBanana (backend, grounding, and this local web integration); Person 3
  — Domemon (generation and evaluation).
- **Web:** React + TypeScript + Vite; calls the answer API, displays status
  and source citations, and retains the tab transcript in `sessionStorage`.
- **Backend:** FastAPI + SQLAlchemy async + PostgreSQL; validates requests,
  manages session follow-up state, imports versioned corpus snapshots, and
  records retrieval metadata.
- **Retrieval:** Person 1's Vietnamese segmentation and lexical BM25 retrieval
  select procedure evidence. No vector database is required.
- **Generation and grounding:** Person 2 checks answerability and citations;
  Person 3 supplies the optional llama.cpp-compatible local model adapter.
  Model errors are surfaced rather than replaced with mock answers.
- **Shared contracts:** JSON Schemas define corpus, retrieval, evidence, and
  grounded-answer data exchanged by the tracks.

## Tested library/runtime versions

| Component | Version |
| --- | --- |
| Node.js | 24.20.0 (minimum 20.19) |
| Python | 3.12.10 |
| PostgreSQL | 17 |
| React / React DOM | 19.2.8 |
| Vite | 8.2.2 |
| TypeScript | 6.0.3 |
| FastAPI | 0.141.1 |
| Uvicorn | 0.54.0 |
| SQLAlchemy | 2.0.54 |
| asyncpg | 0.31.0 |
| pydantic-settings | 2.15.0 |
| jsonschema / referencing | 4.26.0 / 0.37.0 |
| underthesea | 9.5.0 |
| pyvi | 0.1.1 |
| Playwright | 1.63.0 |

JavaScript dependencies are locked by `web/package-lock.json`. Backend
dependencies are pinned in `person2-backend/requirements.txt`; retrieval and
generation manifests pin some dependencies and specify minimum/ranged
versions for others.

## Validation

From `new/web/`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

For the browser test, start the API and web app, then run:

```powershell
$env:PLAYWRIGHT_CHANNEL = 'msedge'
npm.cmd run test:e2e
```

From `new/person2-backend/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest -q
```

PostgreSQL integration tests require a separate empty test database configured
through `TEST_DATABASE_URL`.

## More detail

- [Local web setup, API usage, and optional Qwen instructions](web/README.md)
- [Backend and API details](person2-backend/README.md)
- [Corpus format and notes](data/corpus/README.md)
