from acervo.repositories.uow import UnitOfWork


class TreeService:
    """The tree of a base: folders, pages and files, their order, moves, renames, search and the trash."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
