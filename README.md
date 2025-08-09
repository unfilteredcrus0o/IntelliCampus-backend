# IntelliCampus Backend

Backend API for IntelliCampus — an AI-powered learning and campus management platform.

## Tech Stack
- FastAPI
- PostgreSQL
- Python 3.10+
- LLM Integration (Groq, OpenAI, Claude)

## Health Check
`GET /health` → returns backend status.

## Run Locally
```bash
uvicorn app.main:app --reload --port 8000
