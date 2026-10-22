from acervo.repositories.uow import UnitOfWork


class PageService:
    """Markdown pages: versions, drafts, diffs and links."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
