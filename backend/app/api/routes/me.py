"""Current-user endpoints. P1-9 provides the protected GET /me; P2-1 extends
this area with profile upsert and onboarding completion."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.models.user import User
from app.schemas.auth import UserPublic

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserPublic)
async def read_me(user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, profile_complete=user.profile_complete)
