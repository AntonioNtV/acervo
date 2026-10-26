from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.db.models.email_copy import EmailCopy


class EmailCopyRepository:
    """Email texts edited by an admin, by template and language; a missing one uses the code's text."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, template: str, language: str) -> dict[str, Any] | None:
        query = select(EmailCopy.copy).where(EmailCopy.template == template, EmailCopy.language == language)
        return await self._session.scalar(query)

    async def put(self, template: str, language: str, copy: dict[str, Any], by: UUID) -> None:
        """Saves the text, replacing an earlier edit."""
        upsert = insert(EmailCopy).values(template=template, language=language, copy=copy, updated_by=by)
        await self._session.execute(
            upsert.on_conflict_do_update(
                index_elements=[EmailCopy.template, EmailCopy.language],
                set_={"copy": copy, "updated_by": by, "updated_at": func.now()},
            )
        )

    async def delete(self, template: str, language: str) -> None:
        """Goes back to the code's text."""
        query = delete(EmailCopy).where(EmailCopy.template == template, EmailCopy.language == language)
        await self._session.execute(query)

    async def listed(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Every edited text by (template, language)."""
        rows = await self._session.execute(select(EmailCopy.template, EmailCopy.language, EmailCopy.copy))
        return {(template, language): copy for template, language, copy in rows}
