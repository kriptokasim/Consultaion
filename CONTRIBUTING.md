# Contributing to Consultaion

Thank you for your interest in contributing to Consultaion. This guide covers development setup, conventions, and the pull request process.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 22+
- PostgreSQL (or Supabase)
- Redis

### Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

### Running Tests

```bash
# Backend
cd apps/api && pytest tests/ -v

# Frontend
cd apps/web && npx vitest run
cd apps/web && npx tsc --noEmit
cd apps/web && npm run lint
cd apps/web && npm run build
```

## Repository Structure

```
Consultaion/
  apps/
    api/          # FastAPI backend (Python)
      models.py   # SQLModel/SQLAlchemy models
      routes/     # API route handlers
      orchestration/  # LLM orchestration logic
      alembic/    # Database migrations
      tests/      # Backend tests
    web/          # Next.js frontend (TypeScript)
      app/        # Next.js app router pages
      components/ # React components
      lib/        # Utilities, hooks, API client
```

## Branch Naming

- `feat/<description>` — New features
- `fix/<description>` — Bug fixes
- `chore/<description>` — Maintenance, refactoring, docs

## Commit Style

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add red team multi-lens analysis
fix: resolve challenge transcript field mapping
chore: update dependencies
docs: add API reference for oracle endpoints
```

## Code Quality

### Backend

- Type hints on all functions
- Docstrings on public functions
- No secrets in code or logs
- Run `pytest` before pushing

### Frontend

- TypeScript strict mode
- ESLint with zero errors
- No `console.log` in production code
- Respect `prefers-reduced-motion` for animations
- Use existing toast system (`useToast`) for notifications
- Use `localStorageTTL` helpers for client-side state

## Security

- Never commit secrets, API keys, or tokens
- Use environment variables for configuration
- Auth via session cookies only (no token injection from localStorage)
- Report security issues privately via email, not GitHub issues

## Pull Request Checklist

- [ ] Tests pass (`pytest`, `vitest`, `tsc`, `lint`, `build`)
- [ ] No new lint errors
- [ ] Migration is reversible (if schema changes)
- [ ] No hardcoded URLs, secrets, or credentials
- [ ] UI changes respect `prefers-reduced-motion`
- [ ] New endpoints have auth/permission checks
- [ ] User-facing copy avoids chain-of-thought / hidden reasoning claims

## Questions?

Open a discussion or reach out on the repository's issue tracker.
