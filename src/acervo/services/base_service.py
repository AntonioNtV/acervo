from acervo.repositories.uow import UnitOfWork


class BaseService:
    """Knowledge bases: create, list, rename, trash and restore them."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
