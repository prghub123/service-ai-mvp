# ServiceAI MVP

Agentic AI SaaS for Plumbing/HVAC Small Businesses.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

## Development Setup

### macOS

```bash
# Clone the repository
git clone https://github.com/prghub123/service-ai-mvp.git
cd service-ai-mvp/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API keys

# Start services (PostgreSQL, Redis)
docker-compose up -d postgres redis

# Run the application
uvicorn app.main:app --reload
```

### Windows

**Option 1: Using Docker (Recommended)**

Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) with WSL2 backend enabled.

```powershell
# Clone the repository
git clone https://github.com/prghub123/service-ai-mvp.git
cd service-ai-mvp\backend

# Copy environment file
copy .env.example .env
# Edit .env with your API keys

# Start all services
docker-compose up -d
```

**Option 2: Native Python Development**

```powershell
# Clone the repository
git clone https://github.com/prghub123/service-ai-mvp.git
cd service-ai-mvp\backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env
# Edit .env with your API keys

# Start PostgreSQL and Redis via Docker
docker-compose up -d postgres redis

# Run the application
uvicorn app.main:app --reload
```

**Running Celery Workers on Windows:**

Celery has limited Windows support. Use the `solo` pool:

```powershell
celery -A app.workers worker --pool=solo --loglevel=info
```

## Running with Docker Compose

Start all services:

```bash
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- FastAPI application on port 8000

## Database Migrations (Alembic)

This project uses Alembic for database migrations.

```bash
cd backend

# Generate a new migration after changing models
alembic revision --autogenerate -m "Description of changes"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# View current database version
alembic current
```

**First-time setup:** After cloning, run `alembic upgrade head` to create all tables.

## API Documentation

Once running, access the interactive API docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Environment Variables

See `.env.example` for all configuration options. Required variables:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `OPENAI_API_KEY` - OpenAI API key for LLM features
- `TWILIO_*` - Twilio credentials for SMS/voice
- `VAPI_*` - Vapi.ai credentials for voice AI

## Project Structure

```
backend/
├── app/
│   ├── agents/          # AI agent implementations
│   ├── api/             # FastAPI routes
│   ├── integrations/    # Third-party service clients
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic
│   └── workers/         # Background job workers
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
