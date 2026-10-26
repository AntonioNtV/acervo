from acervo.db.models.password_reset import PasswordReset
from acervo.repositories.base import BaseRepository
from acervo.schemas.account import PasswordResetCreate, PasswordResetRecord, PasswordResetUpdate


class PasswordResetRepository(
    BaseRepository[PasswordReset, PasswordResetRecord, PasswordResetCreate, PasswordResetUpdate]
):
    orm_model = PasswordReset
    read_schema = PasswordResetRecord
