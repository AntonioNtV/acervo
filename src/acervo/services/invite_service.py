from collections.abc import Callable
from datetime import UTC, datetime

from acervo.repositories.uow import UnitOfWork
from acervo.services.access_service import AccessService
from acervo.services.mailer import Mailer


def _now() -> datetime:
    return datetime.now(UTC)


class InviteService:
    """Invites to an organization or to a base: send, resend, revoke, accept."""

    def __init__(
        self, uow: UnitOfWork, mailer: Mailer, access: AccessService, now: Callable[[], datetime] = _now
    ) -> None:
        self._uow = uow
        self._mailer = mailer
        self._access = access
        self._now = now
