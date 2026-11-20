# GigPilot Backend

FastAPI + SQLAlchemy (async) + Celery + LangGraph service for GigPilot: aggregates
freelance jobs across platforms, scores them against the user's profile, and drafts
voice-matched proposals. See `../docs/` for the locked specs (PRD, TRD, Schema, Plan).

## Dev setup

```bash
# from backend/ using the project virtualenv (.venv)
pip install -e ".[dev]"      # install deps (pinned in pyproject.toml / requirements.lock)
ruff check app               # lint
black app tests              # format
pytest                       # tests
```

Stack/versions are locked in `../docs/04_TRD.md §1`. Do not add libraries without
updating that doc.
