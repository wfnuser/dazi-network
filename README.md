# dazi-network

Matching engine backend for the dazi social platform. AI-native social matching for harness users.

## Tech Stack

- Python 3.12+, FastAPI
- Postgres + pgvector (vector similarity search)
- MiniMax LLM (intent parsing + profile analysis)
- Ed25519 did:key authentication
- Railway deployment

## Quick Start

1. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

2. Start Postgres with pgvector:
   ```bash
   docker run -d --name dazi-pg \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=dazi \
     -p 5432:5432 \
     pgvector/pgvector:pg16
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Run:
   ```bash
   uvicorn app.main:app --reload
   ```

5. Test:
   ```bash
   docker exec dazi-pg psql -U postgres -c "CREATE DATABASE dazi_test;"
   python -m pytest tests/ -v
   ```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /profile | Create/update profile |
| POST | /search | Search for matching candidates |
| POST | /interest | Express interest in someone |
| GET | /connections | Get pending + matched connections |
| DELETE | /profile | Delete account and all data |
| GET | /health | Health check |

## Architecture

```
Client (dazi-skill) -> POST /search { intent: "找搭子" }
                         |
                    Server LLM parses intent -> filters + embedding dimensions
                         |
                    Hard filter (city, age, gender)
                         |
                    pgvector cosine similarity on selected dimensions
                         |
                    Return top 30 (nickname + tags only)
```
