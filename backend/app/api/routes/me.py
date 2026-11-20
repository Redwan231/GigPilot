"""Current-user endpoints: GET /me (full profile), PATCH /me/profile (upsert +
profile_version bump + onboarding completion). Derives: US-A3, 02_AppFlow §4.4."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_id, get_tenant_db
from app.db.models.user import Profile, User
from app.db.session import system_session
from app.schemas.me import MeOut, ProfileOut, ProfileUpsert

router = APIRouter(tags=["me"])


def _profile_out(p: Profile) -> ProfileOut:
    return ProfileOut(
        user_id=p.user_id,
        display_name=p.display_name,
        primary_category=p.primary_category,
        skills=p.skills,
        experience_level=p.experience_level,
        hourly_rate=p.hourly_rate,
        bio=p.bio,
        style_tone=p.style_tone,
        style_length=p.style_length,
        style_greeting=p.style_greeting,
        profile_version=p.profile_version,
    )


@router.get("/me", response_model=MeOut)
async def read_me(user: User = Depends(get_current_user)) -> MeOut:
    async with system_session() as session:
        profile = await session.get(Profile, user.id)
    return MeOut(
        id=user.id,
        email=user.email,
        email_verified=user.email_verified,
        profile_complete=user.profile_complete,
        profile=_profile_out(profile) if profile else None,
    )


@router.patch("/me/profile", response_model=MeOut)
async def upsert_profile(
    payload: ProfileUpsert,
    user: User = Depends(get_current_user),
) -> MeOut:
    async with system_session() as session:
        profile = await session.get(Profile, user.id)
        if profile is None:
            profile = Profile(user_id=user.id, profile_version=1)
            session.add(profile)
        else:
            profile.profile_version = profile.profile_version + 1

        profile.display_name = payload.display_name
        profile.primary_category = payload.primary_category
        profile.skills = payload.skills
        profile.experience_level = payload.experience_level
        profile.hourly_rate = payload.hourly_rate
        profile.bio = payload.bio
        profile.style_tone = payload.style_tone
        profile.style_length = payload.style_length
        profile.style_greeting = payload.style_greeting

        if not user.profile_complete:
            db_user = await session.get(User, user.id)
            if db_user is not None:
                db_user.profile_complete = True

        await session.flush()
        # Re-read user for response
        db_user = await session.get(User, user.id)

    return MeOut(
        id=db_user.id,
        email=db_user.email,
        email_verified=db_user.email_verified,
        profile_complete=db_user.profile_complete,
        profile=_profile_out(profile),
    )
