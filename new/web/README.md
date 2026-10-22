# Web prototype — local retrieval demo

React + TypeScript + Vite client for `new/person2-backend`. It sends questions
to `POST /api/v1/answer`, displays the grounded-answer status and citations,
and reuses the backend conversation session ID for follow-up questions.

This client does not implement the older G1 login/conversation/feedback API.
The backend stores follow-up state and query metadata, not chat transcripts;
the visible transcript is kept in the current browser tab's `sessionStorage`.

## Demo limitations

- The supplied corpus is marked `draft`; the default local setup allows draft
  data for evaluation.
- The default generator is a deterministic extractive mock. The backend can
  instead use the optional local Qwen model through llama.cpp.
- Corpus content and generated responses are not verified legal advice.
- The backend needs a local PostgreSQL server.

## Requirements

- Node.js `>=20.19.0` (Node 24 is supported).
- Python 3.12.
- PostgreSQL 17 is the tested database version. The local example below uses
  `127.0.0.1:5433`; configure the port for your own PostgreSQL instance.

## Install project dependencies with one command

From the repository root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\new\scripts\setup-local.ps1
```

This installs the backend, retrieval, and generation Python packages and the
locked web packages, then creates local `.env` files if they do not exist.
PostgreSQL must be installed and running separately; the script does not
install PostgreSQL or download the optional Qwen model. To install manually,
continue with the backend and web steps below.

## Start the local stack

### 1. Create a PostgreSQL database

Install/start PostgreSQL for Windows if it is not already installed. Create a
dedicated local role and empty database for this prototype; do not reuse a
database with unrelated data. Example SQL, run with a PostgreSQL administrator:

```sql
CREATE ROLE app_user WITH LOGIN PASSWORD 'replace-with-a-local-password';
CREATE DATABASE hanh_chinh_mvp OWNER app_user;
```

If the role or database already exists, verify its credentials and ownership
instead of running the creation statements again.

This workspace currently uses a separate UTF-8 PostgreSQL 17 cluster on port
5433 so it does not use the installer-managed service on port 5432. If that
cluster has stopped, start it in PowerShell:

```powershell
$pgCtl = 'C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe'
$pgData = Join-Path $env:LOCALAPPDATA 'HanhChinhDemo\PostgreSQL\17\data'
$pgLog = Join-Path (Split-Path $pgData -Parent) 'postgres.log'
& $pgCtl -D $pgData -l $pgLog -o '-h 127.0.0.1 -p 5433' -w start
```

The ignored local backend `.env` is configured for port 5433. To stop only
this workspace's data cluster:

```powershell
& $pgCtl -D $pgData -m fast -w stop
```

### 2. Install and configure the backend

From the repository root in PowerShell:

```powershell
Set-Location new\person2-backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e ..\person1-retrieval
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `new/person2-backend/.env` with the local PostgreSQL values. Keep the
password local and do not commit `.env`.

Before the first backend startup, import the supplied corpus so the backend
does not seed its separate demo fixture:

```powershell
.\.venv\Scripts\python.exe scripts\import_corpus.py ..\data\corpus
```

Start the API from `new/person2-backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another PowerShell terminal, confirm database health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The response should report `status: ok` and a non-empty `active_snapshot`.

### 3. Start the web client

From the repository root in a second terminal:

```powershell
Set-Location new\web
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:3000`. The Vite development server uses strict port
3000. The API allows only the local web origins on that port; do not expose
the development server or backend to an untrusted network.

The web environment variable is:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

It is a public build-time URL, not a place for credentials. Leave `API_TOKEN`
empty for this loopback-only demo; never put a backend token in `VITE_*`.

## Try an API request directly

```powershell
$body = @{
  query_text_raw = 'Thủ tục đăng ký khai sinh cần những giấy tờ gì?'
  session_id = 'local-demo'
} | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/answer `
  -ContentType 'application/json; charset=utf-8' `
  -Body $body
```

The API response includes a status, answer text, citation fragment/source IDs,
and an `X-Conversation-Session-Id` response header. Follow-up turns should use
the same session ID. The web handles this automatically.

## Checks

From `new/web/`:

```powershell
npm test
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

If Chromium's download is unavailable but Microsoft Edge is installed:

```powershell
$env:PLAYWRIGHT_CHANNEL = 'msedge'
npm run test:e2e
```

From `new/person2-backend/` after backend dependencies are installed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The PostgreSQL integration test requires a separate empty test database via
`TEST_DATABASE_URL`; do not point it at the prototype or any database with
data you need to preserve.

## Stop the local services

Press `Ctrl+C` in each terminal running Vite or Uvicorn. PostgreSQL remains a
Windows service and can be stopped through Windows Services if desired.

## Optional local Qwen model

The default backend configuration uses the mock extractive generator. To use a
local Qwen3 1.7B GGUF (Apache-2.0, official Qwen Q8_0, about 1.83 GB) through
llama.cpp, keep the model on D: and start the
llama.cpp OpenAI-compatible server in a separate PowerShell terminal:

```powershell
$modelDir = 'D:\models\Qwen3-1.7B-GGUF'
$modelPath = Join-Path $modelDir 'Qwen3-1.7B-Q8_0.gguf'
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
if (-not (Test-Path $modelPath)) {
  curl.exe --location --fail --retry 3 `
    --output $modelPath `
    'https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/90862c4b9d2787eaed51d12237eafdfe7c5f6077/Qwen3-1.7B-Q8_0.gguf'
  if ($LASTEXITCODE -ne 0) { throw 'Qwen model download failed' }
}
Get-FileHash -Algorithm SHA256 $modelPath
```

Verify the hash below before running the model:

```powershell
$llamaServer = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe'
$apiKeyFile = 'D:\models\Qwen3-1.7B-GGUF\llama-api-key.txt'
& $llamaServer `
  --model 'D:\models\Qwen3-1.7B-GGUF\Qwen3-1.7B-Q8_0.gguf' `
  --host 127.0.0.1 --port 8080 --ctx-size 4096 --parallel 1 `
  --n-gpu-layers 99 --api-key-file $apiKeyFile
```

Expected model SHA-256:
`061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a`.

In `new/person2-backend/.env`, set:

```dotenv
GENERATOR_BACKEND=llama_cpp
LLM_BASE_URL=http://127.0.0.1:8080
LLM_MODEL=Qwen3-1.7B-Q8_0
LLM_TIMEOUT_SECONDS=180
LLM_API_KEY=<same local key stored in llama-api-key.txt>
```

From the repository root, generate a random key once and store the same key
in the ignored `.env` and the key file outside the repository:

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$apiKey = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
$rng.Dispose()
$apiKeyFile = 'D:\models\Qwen3-1.7B-GGUF\llama-api-key.txt'
[System.IO.File]::WriteAllText($apiKeyFile, $apiKey)
$envPath = 'new\person2-backend\.env'
$lines = @(Get-Content $envPath | Where-Object { $_ -notmatch '^LLM_API_KEY=' })
$lines += "LLM_API_KEY=$apiKey"
[System.IO.File]::WriteAllLines($envPath, $lines)
```

The llama.cpp server listens only on loopback and requires this key; never
commit either local credential file.

Install the Person 3 package in the backend virtual environment once:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ..\person3-generation-evaluation
```

Restart the backend after changing `.env`. Its health response reports the
selected generator. If the model server is unavailable, answer requests fail
explicitly; the backend does not silently fall back to mock answers. Generation
is only invoked for resolved, sufficient evidence, and every generated
citation is checked against the current evidence bundle.
