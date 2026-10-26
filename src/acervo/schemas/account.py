from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Theme = Literal["light", "dark", "system"]
PageWidth = Literal["default", "wide"]
Language = Literal["pt-BR", "en"]
StartPage = Literal["last", "bases"]
CodePurpose = Literal["verify_email", "change_email"]

PASSWORD_MIN = 10


class Preferences(BaseModel):
    """How the app looks and opens for the account, on every device."""

    model_config = ConfigDict(from_attributes=True)

    theme: Theme = Field(default="system", description="light, dark, or system to follow the device.")
    page_width: PageWidth = Field(default="default", description="default (720 px) or wide (1040 px).")
    language: Language = Field(default="pt-BR", description="Language of the app and of the emails.")
    start_page: StartPage = Field(default="last", description="What opens on start: the last page opened, or Bases.")


class AccountCreate(BaseModel):
    """An account to store; preferences start at their defaults."""

    email: str = Field(description="As typed.")
    name: str = Field(description="Shown name.")
    password_hash: str | None = Field(default=None, description="argon2id hash; null for a Google-only account.")
    google_sub: str | None = Field(default=None, description="Google's id of the person.")
    email_verified_at: datetime | None = Field(default=None, description="Null until the email is confirmed.")


class AccountUpdate(BaseModel):
    """Fields to change on an account; omitted fields keep their value."""

    email: str | None = None
    name: str | None = None
    password_hash: str | None = None
    google_sub: str | None = None
    email_verified_at: datetime | None = None
    photo_key: str | None = None
    theme: Theme | None = None
    page_width: PageWidth | None = None
    language: Language | None = None
    start_page: StartPage | None = None


class AccountRecord(AccountCreate):
    """A stored account with its secrets; never sent to the web app (that is `AccountRead`)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    photo_key: str | None
    theme: Theme
    page_width: PageWidth
    language: Language
    start_page: StartPage
    created_at: datetime


class AccountRead(BaseModel):
    """The signed-in person as the web app sees them."""

    id: UUID = Field(description="Account ID.")
    email: str = Field(description="As typed.")
    name: str = Field(description="Shown name.")
    has_password: bool = Field(description="False for an account that only signs in with Google.")
    has_google: bool = Field(description="Whether Google is linked.")
    email_verified: bool = Field(description="Whether the email was confirmed.")
    photo_url: str | None = Field(description="The photo, a 256 px square; null shows the initials.")
    preferences: Preferences

    @classmethod
    def of(cls, account: AccountRecord) -> Self:
        photo_url = None
        if account.photo_key is not None:
            # The key's name changes with the photo, so a new one is never served from the browser's cache.
            photo_url = f"/v1/accounts/{account.id}/photo?v={PurePosixPath(account.photo_key).stem}"
        return cls(
            id=account.id,
            email=account.email,
            name=account.name,
            has_password=account.password_hash is not None,
            has_google=account.google_sub is not None,
            email_verified=account.email_verified_at is not None,
            photo_url=photo_url,
            preferences=Preferences.model_validate(account),
        )


class SignUp(BaseModel):
    name: str = Field(min_length=1, description="Shown name.")
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN)


class SignIn(BaseModel):
    email: EmailStr
    password: str


class CodeIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$", description="The 6 digits sent by email.")


class EmailCodeIn(CodeIn):
    """A code that confirms the email of an account not yet signed in."""

    email: EmailStr


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirm(BaseModel):
    token: str = Field(description="From the link sent by email.")
    password: str = Field(min_length=PASSWORD_MIN)


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, description="New shown name.")


class EmailChange(BaseModel):
    new_email: EmailStr
    password: str | None = Field(default=None, description="The current password; required when the account has one.")


class SessionCreate(BaseModel):
    token_hash: str
    account_id: UUID
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None


class SessionUpdate(BaseModel):
    last_seen_at: datetime | None = None
    expires_at: datetime | None = None


class SessionRecord(SessionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class EmailCodeCreate(BaseModel):
    account_id: UUID
    purpose: CodePurpose
    target_email: str
    code_hash: str
    expires_at: datetime


class EmailCodeUpdate(BaseModel):
    attempts: int | None = None
    used_at: datetime | None = None


class EmailCodeRecord(EmailCodeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attempts: int
    used_at: datetime | None
    created_at: datetime


class PasswordResetCreate(BaseModel):
    token_hash: str
    account_id: UUID
    expires_at: datetime


class PasswordResetUpdate(BaseModel):
    used_at: datetime | None = None


class PasswordResetRecord(PasswordResetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    used_at: datetime | None
    created_at: datetime


class LoginFailureCreate(BaseModel):
    email_lower: str


class LoginFailureRecord(LoginFailureCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
