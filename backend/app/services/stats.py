"""User stats service (US-E2, 02_AppFlow §4.9)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.proposal import Proposal
from app.db.models.score import Score
from app.db.models.user import Subscription


async def get_user_stats(user_id: uuid.UUID, session: AsyncSession) -> dict:
    total = await session.scalar(
        select(func.count()).where(Proposal.user_id == user_id)
    ) or 0

    won = await session.scalar(
        select(func.count()).where(Proposal.user_id == user_id, Proposal.outcome == "won")
    ) or 0

    lost = await session.scalar(
        select(func.count()).where(Proposal.user_id == user_id, Proposal.outcome == "lost")
    ) or 0

    no_response = await session.scalar(
        select(func.count()).where(Proposal.user_id == user_id, Proposal.outcome == "no_response")
    ) or 0

    win_rate = round(won / total, 2) if total > 0 else 0.0

    won_avg_score = await session.scalar(
        select(func.avg(Score.score))
        .join(Proposal, (Score.user_id == Proposal.user_id) & (Score.job_id == Proposal.job_id))
        .where(Proposal.user_id == user_id, Proposal.outcome == "won")
    )

    lost_avg_score = await session.scalar(
        select(func.avg(Score.score))
        .join(Proposal, (Score.user_id == Proposal.user_id) & (Score.job_id == Proposal.job_id))
        .where(Proposal.user_id == user_id, Proposal.outcome == "lost")
    )

    sub = await session.get(Subscription, user_id)
    credits = {
        "tier": sub.tier if sub else "free",
        "drafts_used": sub.drafts_used if sub else 0,
        "drafts_quota": sub.drafts_quota if sub else 0,
    } if sub else {}

    return {
        "proposals_total": total,
        "proposals_won": won,
        "proposals_lost": lost,
        "proposals_no_response": no_response,
        "win_rate": win_rate,
        "won_avg_score": round(float(won_avg_score), 1) if won_avg_score else None,
        "lost_avg_score": round(float(lost_avg_score), 1) if lost_avg_score else None,
        "credits": credits,
    }
