from acervo.db.models.membership import Membership
from acervo.repositories.base import BaseRepository
from acervo.schemas.organization import MembershipCreate, MembershipRecord, MembershipUpdate


class MembershipRepository(BaseRepository[Membership, MembershipRecord, MembershipCreate, MembershipUpdate]):
    orm_model = Membership
    read_schema = MembershipRecord
