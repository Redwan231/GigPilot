"""Rate limiting (slowapi). Per-IP keying by default; authenticated routes can
key by user via `user_or_ip_key`. Specific limits (auth brute-force, per-user
scoring/drafting) are applied on their routes in later tasks (04_TRD §7.5)."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def user_or_ip_key(request: Request) -> str:
    """Prefer the authenticated user id (set by a dependency) as the limit key,
    falling back to the client IP for anonymous requests."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_remote_address)
