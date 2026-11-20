#!/usr/bin/env python3
"""P4-11: Demo seed script — creates a demo Pro user with proposals and fetches
sample jobs so judges see a populated app on first open.

Usage:
    cd backend
    python scripts/seed_demo.py

Environment:
    DATABASE_URL — must point at the target database (Supabase or local).
    Set via .env or export before running.

What it does:
    1. Creates demo@gigpilot.app / Demo1234! (Pro tier, 500 drafts/month)
    2. Patches in a completed profile (Python dev, senior, $120/hr)
    3. Adds 2 writing samples
    4. Runs the job aggregator to populate the jobs table (or seeds 10 fake jobs)
    5. Seeds 3 proposals with outcomes (won / lost / no_response) for dashboard
    6. Prints the demo login credentials
"""

import asyncio
import calendar
import datetime
import os
import sys

# Allow running from the repo root or the backend folder.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://gigpilot:password@localhost:5432/gigpilot",
)

DEMO_EMAIL = "demo@gigpilot.app"
DEMO_PASSWORD = "Demo1234!"

DEMO_SAMPLES = [
    (
        "paste",
        (
            "Dear Hiring Team,\n\n"
            "I'm a senior Python engineer with 8 years of experience building "
            "scalable APIs and distributed systems. I've delivered similar projects "
            "for fintech clients using FastAPI, PostgreSQL, and Celery. I'm "
            "confident I can hit the ground running and deliver production-ready code "
            "in the first week.\n\n"
            "My rate is $120/hr and I'm available immediately.\n\n"
            "Looking forward to discussing the role.\n\nBest,\nAlex"
        ),
    ),
    (
        "paste",
        (
            "Hi,\n\n"
            "I saw your job posting and I think I'd be a great fit. I have 8 years "
            "of Python experience, with a strong focus on FastAPI and async patterns. "
            "I've successfully completed 15+ remote contracts in the past 3 years, "
            "all with 5-star reviews. Happy to share my portfolio.\n\nBest,\nAlex"
        ),
    ),
]

FAKE_JOBS = [
    {
        "platform": "remoteok",
        "external_id": "demo-001",
        "title": "Senior Python Developer (FastAPI / PostgreSQL)",
        "description": (
            "We're looking for a senior Python developer to build our data pipeline. "
            "Must know FastAPI, SQLAlchemy, and async Python. Remote-first, $100-$140/hr."
        ),
        "skills": ["python", "fastapi", "sqlalchemy", "postgresql"],
        "budget_min": 100.0,
        "budget_max": 140.0,
        "currency": "USD",
        "url": "https://remoteok.com/demo-001",
    },
    {
        "platform": "remotive",
        "external_id": "demo-002",
        "title": "Full-Stack Engineer (React + Node.js)",
        "description": (
            "Build consumer-facing features on our React/TypeScript frontend and "
            "Node.js backend. 3+ years experience, comfortable with AWS."
        ),
        "skills": ["react", "typescript", "nodejs", "aws"],
        "budget_min": 80.0,
        "budget_max": 110.0,
        "currency": "USD",
        "url": "https://remotive.com/demo-002",
    },
    {
        "platform": "himalayas",
        "external_id": "demo-003",
        "title": "DevOps / Platform Engineer",
        "description": (
            "Own our Kubernetes infrastructure on GKE. CI/CD pipelines, monitoring, "
            "cost optimization. Terraform required."
        ),
        "skills": ["kubernetes", "terraform", "gcp", "ci-cd"],
        "url": "https://himalayas.app/demo-003",
    },
    {
        "platform": "weworkremotely",
        "external_id": "demo-004",
        "title": "Machine Learning Engineer",
        "description": (
            "Build recommendation systems using PyTorch. Experience with MLflow, "
            "feature stores, and A/B testing frameworks."
        ),
        "skills": ["python", "pytorch", "mlops", "mlflow"],
        "budget_min": 120.0,
        "budget_max": 160.0,
        "currency": "USD",
        "url": "https://weworkremotely.com/demo-004",
    },
    {
        "platform": "remoteok",
        "external_id": "demo-005",
        "title": "Backend Engineer (Go / gRPC)",
        "description": "Scale our microservices platform. Strong Go, gRPC, Redis experience.",
        "skills": ["go", "grpc", "redis", "microservices"],
        "budget_min": 90.0,
        "budget_max": 130.0,
        "currency": "USD",
        "url": "https://remoteok.com/demo-005",
    },
]


def _add_one_month(d: datetime.date) -> datetime.date:
    year = d.year + (d.month // 12)
    month = d.month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


async def main() -> None:
    from app.config import settings
    from app.core.security import hash_password

    # Normalize URL
    db_url = DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]
    if db_url.startswith("postgresql://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]

    engine = create_async_engine(db_url, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        # --- Check/create demo user ---
        existing = await conn.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": DEMO_EMAIL}
        )
        row = existing.fetchone()
        if row:
            user_id = str(row[0])
            print(f"Demo user already exists: {DEMO_EMAIL} ({user_id})")
        else:
            result = await conn.execute(
                text(
                    "INSERT INTO users (email, password_hash, profile_complete, email_verified) "
                    "VALUES (:e, :pw, true, true) RETURNING id"
                ),
                {"e": DEMO_EMAIL, "pw": hash_password(DEMO_PASSWORD)},
            )
            user_id = str(result.fetchone()[0])
            print(f"Created demo user: {DEMO_EMAIL} ({user_id})")

        # --- Profile ---
        await conn.execute(
            text(
                "INSERT INTO profiles (user_id, display_name, primary_category, skills, "
                "experience_level, hourly_rate, profile_version) "
                "VALUES (:uid, 'Alex Demo', 'development', :skills, 'senior', 120.00, 1) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "display_name = EXCLUDED.display_name, skills = EXCLUDED.skills, "
                "experience_level = EXCLUDED.experience_level, hourly_rate = EXCLUDED.hourly_rate"
            ),
            {"uid": user_id, "skills": ["python", "fastapi", "postgresql", "react", "celery"]},
        )

        # --- Subscription (Pro) ---
        today = datetime.date.today()
        period_end = _add_one_month(today)
        await conn.execute(
            text(
                "INSERT INTO subscriptions (user_id, tier, period_start, period_end, "
                "drafts_quota, drafts_used) "
                "VALUES (:uid, 'pro', :ps, :pe, 500, 3) "
                "ON CONFLICT (user_id) DO UPDATE SET tier = 'pro', drafts_quota = 500, "
                "period_end = EXCLUDED.period_end"
            ),
            {"uid": user_id, "ps": today, "pe": period_end},
        )

        # --- Writing samples ---
        existing_count = await conn.execute(
            text("SELECT COUNT(*) FROM writing_samples WHERE user_id = :uid"),
            {"uid": user_id},
        )
        if existing_count.scalar() == 0:
            for source_type, content in DEMO_SAMPLES:
                await conn.execute(
                    text(
                        "INSERT INTO writing_samples (user_id, source_type, content) "
                        "VALUES (:uid, :st, :c)"
                    ),
                    {"uid": user_id, "st": source_type, "c": content},
                )

        # --- Jobs ---
        import json

        for job in FAKE_JOBS:
            await conn.execute(
                text(
                    "INSERT INTO jobs (platform, external_id, title, description, skills, "
                    "budget_min, budget_max, currency, url, is_active, raw) "
                    "VALUES (:platform, :eid, :title, :desc, :skills, :bmin, :bmax, "
                    ":currency, :url, true, :raw) "
                    "ON CONFLICT (platform, external_id) DO UPDATE SET "
                    "title = EXCLUDED.title, is_active = true"
                ),
                {
                    "platform": job["platform"],
                    "eid": job["external_id"],
                    "title": job["title"],
                    "desc": job["description"],
                    "skills": job.get("skills", []),
                    "bmin": job.get("budget_min"),
                    "bmax": job.get("budget_max"),
                    "currency": job.get("currency", "USD"),
                    "url": job["url"],
                    "raw": json.dumps(job),
                },
            )

        job_rows = await conn.execute(
            text("SELECT id FROM jobs WHERE platform LIKE 'demo%' OR external_id LIKE 'demo-%' LIMIT 3")
        )
        job_ids = [str(r[0]) for r in job_rows.fetchall()]

        if not job_ids:
            # Fallback: get any 3 jobs
            any_jobs = await conn.execute(text("SELECT id FROM jobs LIMIT 3"))
            job_ids = [str(r[0]) for r in any_jobs.fetchall()]

        # --- Proposals (3, with outcomes for dashboard stats) ---
        outcomes = [("won", "used"), ("lost", "used"), ("no_response", "used")]
        existing_proposals = await conn.execute(
            text("SELECT COUNT(*) FROM proposals WHERE user_id = :uid"), {"uid": user_id}
        )
        if existing_proposals.scalar() == 0:
            for i, (outcome, status) in enumerate(outcomes):
                if i < len(job_ids):
                    await conn.execute(
                        text(
                            "INSERT INTO proposals (user_id, job_id, content, status, outcome, voice_matched) "
                            "VALUES (:uid, :jid, :content, :status, :outcome, true)"
                        ),
                        {
                            "uid": user_id,
                            "jid": job_ids[i],
                            "content": f"Demo proposal #{i + 1} — {outcome} outcome.",
                            "status": status,
                            "outcome": outcome,
                        },
                    )

    await engine.dispose()

    print("\n✓ Demo seed complete!")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")
    print(f"  Tier:     Pro (500 drafts/month)")
    print(f"  Jobs:     {len(FAKE_JOBS)} seeded")
    print(f"  Samples:  {len(DEMO_SAMPLES)} writing samples")
    print("  Proposals: 3 (won / lost / no_response)")


if __name__ == "__main__":
    asyncio.run(main())
