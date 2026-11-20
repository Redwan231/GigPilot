"""Auth endpoints: signup, login, refresh (rotation + reuse-detection), logout
(05_Schema §6). All DB work runs on the privileged system session — these tables
(users, subscriptions, refresh_tokens) are outside the tenant RLS path."""

import calendar
import datetime
import uuid

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import security
from app.core.rate_limit import limiter
from app.db.models.user import RefreshToken, Subscription, User
from app.db.session import system_session
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
# Benign multi-tab refresh race window (05_Schema §6): a token revoked within this
# many seconds is treated as a race, not a reuse attack.
REUSE_GRACE_SECONDS = 10


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _add_one_month(d: datetime.date) -> datetime.date:
    year = d.year + (d.month // 12)
    month = d.month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


async def _issue_refresh(session: AsyncSession, user_id: uuid.UUID) -> str:
    """Create and persist a new refresh token; return the raw (un-hashed) value."""
    raw = security.generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=security.hash_refresh_token(raw),
            expires_at=_now() + datetime.timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    return raw


def _token_response(user: User, access: str) -> TokenResponse:
    return TokenResponse(
        access_token=access,
        user=UserPublic(id=user.id, email=user.email, profile_complete=user.profile_complete),
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def signup(payload: SignupRequest, response: Response) -> TokenResponse:
    async with system_session() as session:
        existing = await session.scalar(select(User.id).where(User.email == payload.email))
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        user = User(
            email=payload.email,
            password_hash=security.hash_password(payload.password),
            email_verified=settings.auth_auto_verify_email,
        )
        session.add(user)
        await session.flush()  # populate user.id

        today = datetime.date.today()
        session.add(
            Subscription(
                user_id=user.id,
                tier="free",
                period_start=today,
                period_end=_add_one_month(today),
                drafts_quota=settings.free_drafts_per_month,
                drafts_used=0,
            )
        )

        raw_refresh = await _issue_refresh(session, user.id)
        access = security.create_access_token(user.id)
        _set_refresh_cookie(response, raw_refresh)
        return _token_response(user, access)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, response: Response) -> TokenResponse:
    async with system_session() as session:
        user = await session.scalar(select(User).where(User.email == payload.email))
        # Generic error — no user enumeration (04_TRD §7.2).
        if user is None or not security.verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect.",
            )

        raw_refresh = await _issue_refresh(session, user.id)
        access = security.create_access_token(user.id)
        _set_refresh_cookie(response, raw_refresh)
        return _token_response(user, access)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response) -> TokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token."
        )

    token_hash = security.hash_refresh_token(raw)
    # Resolve the outcome inside one committed transaction, then act on it. We must
    # never raise while holding the transaction, or mutations (e.g. revoke-all on
    # reuse) would be rolled back.
    error: str | None = None
    issued: tuple[User, str] | None = None

    async with system_session() as session:
        row = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        now = _now()

        if row is None:
            error = "Invalid refresh token."
        elif row.revoked:
            # Reuse of an already-revoked token. It's a benign multi-tab rotation
            # race only if revoked within the grace window AND a valid successor
            # still exists (true after rotation, false after logout). Otherwise
            # treat as theft and revoke every token.
            within_grace = (
                row.revoked_at is not None
                and (now - row.revoked_at).total_seconds() <= REUSE_GRACE_SECONDS
            )
            has_successor = await _has_valid_token(session, row.user_id, now)
            if within_grace and has_successor:
                issued = await _rotate(session, row, now, revoke_presented=False)
            else:
                await _revoke_all(session, row.user_id, now)
                error = "Refresh token reuse detected."
        elif row.expires_at <= now:
            row.revoked = True
            row.revoked_at = now
            error = "Refresh token expired."
        else:
            issued = await _rotate(session, row, now, revoke_presented=True)

    if error is not None or issued is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid refresh token.",
        )

    user, new_raw = issued
    access = security.create_access_token(user.id)
    _set_refresh_cookie(response, new_raw)
    return _token_response(user, access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> Response:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        token_hash = security.hash_refresh_token(raw)
        async with system_session() as session:
            row = await session.scalar(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
            if row is not None and not row.revoked:
                row.revoked = True
                row.revoked_at = _now()
    response.delete_cookie(REFRESH_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


async def _rotate(
    session: AsyncSession,
    row: RefreshToken,
    now: datetime.datetime,
    revoke_presented: bool,
) -> tuple[User, str] | None:
    """Revoke the presented token (optional) and mint a fresh refresh for its user."""
    if revoke_presented:
        row.revoked = True
        row.revoked_at = now
    user = await session.get(User, row.user_id)
    if user is None:
        return None
    new_raw = await _issue_refresh(session, user.id)
    return user, new_raw


async def _has_valid_token(
    session: AsyncSession, user_id: uuid.UUID, now: datetime.datetime
) -> bool:
    found = await session.scalar(
        select(RefreshToken.id)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > now,
        )
        .limit(1)
    )
    return found is not None


async def _revoke_all(session: AsyncSession, user_id: uuid.UUID, now: datetime.datetime) -> None:
    rows = await session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
    )
    for r in rows:
        r.revoked = True
        r.revoked_at = now
