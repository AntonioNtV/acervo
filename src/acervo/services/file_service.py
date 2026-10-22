from acervo.repositories.uow import UnitOfWork
from acervo.services.storage import Storage


class FileService:
    """Stored files: upload, new versions, history and reading the bytes back."""

    def __init__(self, uow: UnitOfWork, storage: Storage) -> None:
        self._uow = uow
        self._storage = storage
