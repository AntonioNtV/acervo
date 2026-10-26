from acervo.repositories.uow import UnitOfWork
from acervo.services.access_service import AccessService
from acervo.services.mailer import Mailer
from acervo.services.storage import Storage


class OrganizationService:
    """Organizations and their members: create, rename, logo, roles, remove, leave."""

    def __init__(self, uow: UnitOfWork, storage: Storage, mailer: Mailer, access: AccessService) -> None:
        self._uow = uow
        self._storage = storage
        self._mailer = mailer
        self._access = access
