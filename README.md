## Manuscript Processor

Full‑stack app to process PDFs into structured XML/DocBook with a FastAPI backend and Angular frontend.

### Monorepo layout

```
backend/   # FastAPI service (MongoDB, S3, schedulers)
frontend/  # Angular 20 web UI
```

## Prerequisites

- Backend: Python 3.11+ (3.11/3.12 recommended), pip, virtualenv
- Frontend: Node.js 20+ and npm
- Database: MongoDB (local or Docker)
  - Quick Docker: `docker run -d --name mongo -p 27017:27017 mongo:6`
- Optional (S3 features): AWS credentials/profile with access to your bucket

## Quickstart

### 1) Start MongoDB (required)

```bash
docker run -d --name mongo -p 27017:27017 mongo:6
# or use a locally installed mongod on port 27017
```

### 2) Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# (Optional) create .env in backend/ to override defaults
cat > .env << 'ENV'
# MongoDB
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=manuscript_processor

# App
DEBUG=true
HOST=0.0.0.0
PORT=8000
SECRET_KEY=dev-secret-change-me

# AWS (optional for S3 features)
AWS_REGION=us-east-1
S3_BUCKET_NAME=manuscript-processor-bucket
ENV

# Run dev server
python run.py
# Uvicorn directly (equivalent):
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend URLs:

- API base: `http://localhost:8000/xmlconverter/api/v1`
- Docs: `http://localhost:8000/xmlconverter/docs`
- Health: `http://localhost:8000/xmlconverter/health`

### 3) Frontend (Angular)

The frontend is preconfigured to call the backend at `http://localhost:8000/xmlconverter` (see `frontend/src/environments/environment.ts`).

```bash
cd frontend
npm install
npm start
# App at http://localhost:4200/
```

## Testing locally

### Backend tests

MongoDB must be running on `localhost:27017` (see step 1). From `backend/`:

```bash
# All suites + coverage
python run_tests.py --type all

# Unit only
python run_tests.py --type unit

# Integration only (DB)
python run_tests.py --type integration

# S3-only (uses mocked client by default)
python run_tests.py --type s3
```

### Frontend tests

From `frontend/`:

```bash
# Unit tests (headless)
npm run test:unit

# E2E (Cypress headless)
npm run test:e2e

# Open Cypress runner (interactive)
npm run test:e2e:open
```

## Configuration notes

- Backend settings are loaded via `.env` in `backend/` (see example above). Defaults target local Mongo on `localhost:27017` and expose FastAPI at port 8000.
- The backend mounts API at `/xmlconverter/api/v1`; the frontend `apiUrl` defaults to `http://localhost:8000/xmlconverter` so paths resolve like `.../xmlconverter/api/v1/...`.
- AWS is optional; S3 operations require valid credentials or an AWS profile. Without them, core API and most tests still run; S3 integration tests patch the client.

## Common issues

- Port in use: change `PORT` in backend `.env` or `npm start -- --port 4300` for the frontend.
- Mongo not running: start with the Docker command above.
- CORS: backend allows all origins in dev; if you customize, ensure `http://localhost:4200` is allowed.

