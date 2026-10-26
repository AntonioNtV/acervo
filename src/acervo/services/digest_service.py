from datetime import datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from acervo.repositories.digest import DigestChange
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import Language
from acervo.schemas.notification import Notification
from acervo.services.mail_templates import join_names
from acervo.services.mailer import Mailer, MailTemplate, Unsubscribe

YOU: dict[Language, str] = {"pt-BR": "Você", "en": "You"}
DELETED_ACCOUNT: dict[Language, str] = {"pt-BR": "Conta excluída", "en": "Deleted account"}


class DigestService:
    """The daily "Resumo do dia": the followed pages someone else changed the previous local day."""

    def __init__(self, uow: UnitOfWork, mailer: Mailer) -> None:
        self._uow = uow
        self._mailer = mailer

    async def due(self, now: datetime) -> list[UUID]:
        """The accounts whose digest goes out in this run: the toggle on, 8:xx local, none sent today."""
        return await self._uow.digests.due(now)

    async def send(self, account_id: UUID, now: datetime) -> None:
        """Sends the account's digest for the day before its local `now`, once a day; with nothing changed, the
        day is marked and no email goes out. A deleted account is skipped. A mail that fails gives the day back and
        raises, for the caller to retry."""
        account = await self._uow.digests.account(account_id)
        if account is None:
            return
        zone = ZoneInfo(account.timezone)
        today = now.astimezone(zone).date()
        if not await self._uow.digests.claim(account_id, today):
            return
        self._uow.act_as(account_id)
        start = datetime.combine(today - timedelta(days=1), time(), zone)
        changes = await self._uow.digests.changes(account_id, start, datetime.combine(today, time(), zone))
        await self._uow.commit()
        pages = _pages(changes, account_id, account.language)
        if not pages:
            return
        values = {"count": str(len(pages)), "pages": "\n".join("\t".join(page) for page in pages)}
        unsubscribe = Unsubscribe(account_id, Notification.FOLLOWED)
        try:
            await self._mailer.send(
                account.email, MailTemplate.DIGEST, account.language, values, unsubscribe=unsubscribe
            )
        except Exception:
            # The day goes back, so the activity's retry sends it; two runs at once still claim it once.
            await self._uow.digests.release(account_id, today, account.digest_sent_on)
            await self._uow.commit()
            raise


def _pages(changes: list[DigestChange], account_id: UUID, language: Language) -> list[tuple[str, str, str]]:
    """(title, authors, base) of each page with a version by someone else; the person comes first, as "Você"."""
    by_page: dict[UUID, list[DigestChange]] = {}
    for change in changes:
        by_page.setdefault(change.node_id, []).append(change)
    pages = []
    for versions in by_page.values():
        if all(v.author_id == account_id for v in versions):
            continue
        names = [YOU[language]] if any(v.author_id == account_id for v in versions) else []
        for v in versions:
            name = v.author or DELETED_ACCOUNT[language]
            if v.author_id != account_id and name not in names:
                names.append(name)
        pages.append((versions[0].title, join_names(names, language), versions[0].base))
    return pages
