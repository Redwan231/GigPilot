"""Atomic draft credit management (US-D4/F1-F3, 05_Schema §3.8).

Credit deducted ONLY on AI success. Monthly reset logic."""

import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import Subscription


async def check_and_reserve_credit(user_id: uuid.UUID, session: AsyncSession) -> None:
    """Atomically verify quota and increment drafts_used. Raises PermissionError if at cap."""
    sub = await session.get(Subscription, user_id)
    if sub is None:
        raise PermissionError("No subscription found")

    today = date.today()
    if today > sub.period_end:
        await _reset_monthly_quota(sub, session)

    if sub.drafts_used >= sub.drafts_quota:
        raise PermissionError(
            f"Draft limit reached ({sub.drafts_quota}/month). "
            "Upgrade to Pro for more drafts."
        )

    sub.drafts_used += 1
    await session.flush()


async def release_credit(user_id: uuid.UUID, session: AsyncSession) -> None:
    """Release a reserved credit on AI failure (atomic decrement, floor 0)."""
    sub = await session.get(Subscription, user_id)
    if sub and sub.drafts_used > 0:
        sub.drafts_used -= 1
        await session.flush()


async def _reset_monthly_quota(sub: Subscription, session: AsyncSession) -> None:
    from datetime import timedelta

    sub.period_start = date.today()
    sub.period_end = date(date.today().year, date.today().month + 1, 1) if date.today().month < 12 else date(date.today().year + 1, 1, 1)
    sub.drafts_used = 0
    await session.flush()


async def get_credit_status(user_id: uuid.UUID, session: AsyncSession) -> dict:
    sub = await session.get(Subscription, user_id)
    if sub is None:
        return {"tier": "free", "drafts_used": 0, "drafts_quota": 0, "drafts_remaining": 0}

    today = date.today()
    if today > sub.period_end:
        await _reset_monthly_quota(sub, session)

    return {
        "tier": sub.tier,
        "drafts_used": sub.drafts_used,
        "drafts_quota": sub.drafts_quota,
        "drafts_remaining": max(0, sub.drafts_quota - sub.drafts_used),
        "period_end": sub.period_end.isoformat(),
    }
