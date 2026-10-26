from fastapi import Response

from acervo.core.settings import Settings

SESSION_COOKIE = "acervo_session"
# Between a right password and the two-step code; it opens nothing.
PENDING_COOKIE = "acervo_pending"


def _secure(settings: Settings) -> bool:
    return settings.public_url.startswith("https://")


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=_secure(settings),
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax", secure=_secure(settings))


def set_pending_cookie(response: Response, token: str, max_age: int, settings: Settings) -> None:
    response.set_cookie(PENDING_COOKIE, token, max_age=max_age, httponly=True, samesite="lax", secure=_secure(settings))


def clear_pending_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(PENDING_COOKIE, httponly=True, samesite="lax", secure=_secure(settings))
