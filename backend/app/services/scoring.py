"""Job scoring service (04_TRD §5, §5b).

Cheap skill-overlap pre-filter → AI score (4 data-honest dimensions) →
cache in `scores` by (user, job, profile_version), daily Redis cap.
Lazy reasoning generation on "Why?" (P2-9)."""

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import chat_json, chat_text
from app.config import settings
from app.db.models.job import Job
from app.db.models.proposal import Proposal
from app.db.models.score import Score
from app.db.models.user import Profile, Subscription
from app.guardrails.sanitize import sanitize_text

log = logging.getLogger(__name__)

SKILL_OVERLAP_THRESHOLD = 0.0

_SCORING_SYSTEM = """You are a job-fit scoring engine for freelancers. You assess how well a freelancer matches a job posting.

Return ONLY a JSON object with this exact structure:
{"score": <int 0-100>, "confidence": <float 0.00-1.00>, "dims": {"skills": <int 0-100>, "seniority": <int 0-100>, "rate": <int 0-100>, "freshness": <int 0-100>}}

Dimensions:
- skills: overlap between the freelancer's skills and job requirements
- seniority: match between freelancer's experience level and the job's implied level
- rate: fit between freelancer's hourly rate and job budget (neutral/50 when job has no budget)
- freshness: job recency as a competition proxy (newer = higher)

Be data-honest: only score what you can observe. Do NOT assess client history or proposal counts — this data is unavailable."""


def compute_skill_overlap(profile_skills: list[str], job_skills: list[str], job_desc: str) -> float:
    if not profile_skills:
        return 0.0
    p_lower = {s.lower() for s in profile_skills}
    j_lower = {s.lower() for s in job_skills}

    matched = p_lower & j_lower
    if not matched:
        desc_lower = job_desc.lower()
        matched = {s for s in p_lower if s in desc_lower}

    return len(matched) / len(p_lower) if p_lower else 0.0


async def _check_daily_cap(user_id: uuid.UUID, tier: str) -> bool:
    """Check and increment daily scoring count in Redis. Returns True if allowed."""
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        cap = settings.pro_scores_per_day if tier == "pro" else settings.free_scores_per_day
        key = f"score_cap:{user_id}:{date.today().isoformat()}"

        current = await r.get(key)
        if current is not None and int(current) >= cap:
            await r.aclose()
            return False

        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)
        await pipe.execute()
        await r.aclose()
        return True
    except Exception:
        log.warning("Redis unavailable for scoring cap; allowing request")
        return True


async def _get_feedback_line(user_id: uuid.UUID, session: AsyncSession) -> str:
    """Build one-line outcome stats for feedback loop (04_TRD §5c)."""
    try:
        from sqlalchemy import func

        won = await session.scalar(
            select(func.count()).where(Proposal.user_id == user_id, Proposal.outcome == "won")
        ) or 0
        lost = await session.scalar(
            select(func.count()).where(Proposal.user_id == user_id, Proposal.outcome == "lost")
        ) or 0
        no_resp = await session.scalar(
            select(func.count()).where(Proposal.user_id == user_id, Proposal.outcome == "no_response")
        ) or 0

        if won + lost + no_resp == 0:
            return ""

        return f"This user's recent outcomes: won {won}, lost {lost}, no-response {no_resp}."
    except Exception:
        return ""


async def score_job(
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    session: AsyncSession,
) -> Score:
    """Score a job for a user. Returns cached score if exists, else computes."""
    profile = await session.get(Profile, user_id)
    if profile is None:
        raise ValueError("Profile required before scoring")

    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError("Job not found")

    existing = await session.scalar(
        select(Score).where(
            Score.user_id == user_id,
            Score.job_id == job_id,
            Score.profile_version == profile.profile_version,
        )
    )
    if existing is not None:
        return existing

    sub = await session.get(Subscription, user_id)
    tier = sub.tier if sub else "free"

    allowed = await _check_daily_cap(user_id, tier)
    if not allowed:
        raise PermissionError("Daily scoring limit reached")

    overlap = compute_skill_overlap(
        profile.skills or [],
        job.skills or [],
        job.description or "",
    )

    rate_part = f"Rate: ${profile.hourly_rate}/hr. " if profile.hourly_rate else ""
    profile_summary = (
        f"Skills: {', '.join(profile.skills or [])}. "
        f"Experience: {profile.experience_level}. "
        f"{rate_part}"
        f"Category: {profile.primary_category}."
    )

    job_summary = sanitize_text(
        f"Title: {job.title}. "
        f"Skills: {', '.join(job.skills or [])}. "
        f"Description: {job.description[:1000]}. "
        f"Budget: {job.budget_min or '?'}-{job.budget_max or '?'} {job.currency}. "
        f"Posted: {job.posted_at.isoformat() if job.posted_at else 'unknown'}."
    )

    feedback_line = await _get_feedback_line(user_id, session)

    messages = [
        {"role": "system", "content": _SCORING_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Freelancer profile:\n{profile_summary}\n\n"
                f"Job posting:\n{job_summary}\n\n"
                f"Pre-computed skill overlap: {overlap:.0%}\n\n"
                f"{feedback_line}"
            ),
        },
    ]

    result = await chat_json(
        messages,
        user_id=str(user_id),
        operation="score",
        temperature=0.3,
        max_tokens=256,
    )

    raw_score = max(0, min(100, int(result.get("score", 50))))
    raw_conf = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
    dims = result.get("dims", {})
    dimensions = {
        "skills": max(0, min(100, int(dims.get("skills", 50)))),
        "seniority": max(0, min(100, int(dims.get("seniority", 50)))),
        "rate": max(0, min(100, int(dims.get("rate", 50)))),
        "freshness": max(0, min(100, int(dims.get("freshness", 50)))),
    }

    score_row = Score(
        user_id=user_id,
        job_id=job_id,
        profile_version=profile.profile_version,
        score=raw_score,
        confidence=round(raw_conf, 2),
        dimensions=dimensions,
    )
    session.add(score_row)
    await session.flush()
    return score_row


_REASONING_SYSTEM = """You are a job-fit analyst. Given a freelancer's score for a job, explain WHY in 2-4 sentences.

Reference the four dimensions (skills match, seniority fit, rate/budget fit, freshness) and their sub-scores.
Be concise, honest, and data-grounded. Do NOT mention data you don't have (client history, proposal counts)."""


async def generate_reasoning(
    score: Score,
    session: AsyncSession,
) -> str:
    """Lazy-generate natural-language reasoning for a score. Caches in score.reasoning."""
    if score.reasoning:
        return score.reasoning

    job = await session.get(Job, score.job_id)
    if job is None:
        raise ValueError("Job not found")

    dims = score.dimensions or {}
    prompt = (
        f"Job: {job.title}\n"
        f"Overall score: {score.score}/100 (confidence: {score.confidence})\n"
        f"Dimensions: skills={dims.get('skills')}, seniority={dims.get('seniority')}, "
        f"rate={dims.get('rate')}, freshness={dims.get('freshness')}\n\n"
        f"Explain this score briefly."
    )

    reasoning = await chat_text(
        [
            {"role": "system", "content": _REASONING_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        user_id=str(score.user_id),
        operation="score_reasoning",
        temperature=0.4,
        max_tokens=256,
    )

    score.reasoning = reasoning.strip()
    await session.flush()
    return score.reasoning
