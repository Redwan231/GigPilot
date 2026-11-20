"""Jobs API: GET /jobs (feed with filters/sort/pagination), GET /jobs/{id}.
Derives: US-B1–B3, 02_AppFlow §4.5–4.6. Budget filter includes NULL-budget
jobs by default (04_TRD §4.3)."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_tenant_db
from app.db.models.job import Job
from app.db.models.score import Score
from app.db.session import system_session
from app.schemas.jobs import JobDetailOut, JobListOut, JobOut, ScoreOut
from app.services.scoring import score_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_out(j: Job) -> JobOut:
    return JobOut(
        id=j.id,
        platform=j.platform,
        external_id=j.external_id,
        title=j.title,
        description=j.description,
        company=j.company,
        category=j.category,
        skills=j.skills,
        budget_min=j.budget_min,
        budget_max=j.budget_max,
        currency=j.currency,
        url=j.url,
        posted_at=j.posted_at,
        fetched_at=j.fetched_at,
        is_active=j.is_active,
    )


@router.get("", response_model=JobListOut)
async def list_jobs(
    platform: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
    budget_min: Optional[float] = Query(None),
    budget_max: Optional[float] = Query(None),
    min_score: Optional[int] = Query(None),
    sort: str = Query("newest", pattern="^(newest|score)$"),
    limit: int = Query(20, ge=1, le=50),
    cursor: Optional[str] = Query(None),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobListOut:
    async with system_session() as session:
        q: Select = select(Job).where(Job.is_active.is_(True))

        if platform:
            q = q.where(Job.platform == platform)
        if category:
            q = q.where(Job.category == category)
        if skill:
            q = q.where(Job.skills.any(skill))
        if budget_min is not None:
            q = q.where((Job.budget_max >= budget_min) | (Job.budget_max.is_(None)))
        if budget_max is not None:
            q = q.where((Job.budget_min <= budget_max) | (Job.budget_min.is_(None)))

        if sort == "newest":
            q = q.order_by(Job.posted_at.desc().nullslast(), Job.fetched_at.desc())
        else:
            q = q.order_by(Job.fetched_at.desc())

        offset = 0
        if cursor:
            try:
                offset = int(cursor)
            except ValueError:
                pass

        q = q.offset(offset).limit(limit + 1)
        rows = (await session.scalars(q)).all()

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(offset + limit)

    return JobListOut(
        items=[_job_out(j) for j in rows],
        next_cursor=next_cursor,
    )


@router.post("/{job_id}/score", response_model=ScoreOut)
async def score_job_endpoint(
    job_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScoreOut:
    async with system_session() as session:
        try:
            s = await score_job(user_id, job_id, session)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))

        return ScoreOut(
            id=s.id,
            score=s.score,
            confidence=s.confidence,
            dimensions=s.dimensions,
            reasoning=s.reasoning,
            profile_version=s.profile_version,
            created_at=s.created_at,
        )


@router.get("/{job_id}", response_model=JobDetailOut)
async def get_job(
    job_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobDetailOut:
    async with system_session() as session:
        job = await session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

        score = await session.scalar(
            select(Score)
            .where(Score.user_id == user_id, Score.job_id == job_id)
            .order_by(Score.created_at.desc())
            .limit(1)
        )

    user_score = None
    if score:
        user_score = ScoreOut(
            id=score.id,
            score=score.score,
            confidence=score.confidence,
            dimensions=score.dimensions,
            reasoning=score.reasoning,
            profile_version=score.profile_version,
            created_at=score.created_at,
        )

    return JobDetailOut(
        **_job_out(job).model_dump(),
        user_score=user_score,
    )
