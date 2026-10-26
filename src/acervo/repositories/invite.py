from acervo.db.models.invite import Invite
from acervo.repositories.base import BaseRepository
from acervo.schemas.organization import InviteRecord, InviteRecordCreate, InviteRecordUpdate


class InviteRepository(BaseRepository[Invite, InviteRecord, InviteRecordCreate, InviteRecordUpdate]):
    orm_model = Invite
    read_schema = InviteRecord
