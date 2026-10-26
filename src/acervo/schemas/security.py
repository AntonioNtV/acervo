from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acervo.schemas.account import SignInMethod

TwoFactorMethod = Literal["email", "whatsapp"]


class SecurityEventKind(StrEnum):
    """What a line of the activity (account) or of the audit (organization) says happened."""

    SIGNED_IN = "signed_in"
    WRONG_PASSWORD = "wrong_password"
    WRONG_CODE = "wrong_code"
    LOCKED_OUT = "locked_out"
    PASSWORD_CHANGED = "password_changed"
    EMAIL_CHANGED = "email_changed"
    PASSKEY_ADDED = "passkey_added"
    PASSKEY_REMOVED = "passkey_removed"
    # A passkey whose signature counter went back: maybe a cloned authenticator.
    PASSKEY_REFUSED = "passkey_refused"
    TWO_FACTOR_ON = "two_factor_on"
    TWO_FACTOR_OFF = "two_factor_off"
    GOOGLE_LINKED = "google_linked"
    GOOGLE_UNLINKED = "google_unlinked"
    SESSION_ENDED = "session_ended"
    INVITED = "invited"
    INVITE_REVOKED = "invite_revoked"
    JOINED = "joined"
    ROLE_CHANGED = "role_changed"
    REMOVED = "removed"
    BASE_CREATED = "base_created"
    BASE_TRASHED = "base_trashed"
    BASE_RESTORED = "base_restored"
    ACCESS_CHANGED = "access_changed"
    TWO_FACTOR_REQUIRED = "two_factor_required"


class PasskeyCreate(BaseModel):
    account_id: UUID
    credential_id: bytes
    public_key: bytes
    sign_count: int
    transports: list[str]
    name: str
    aaguid: str


class PasskeyUpdate(BaseModel):
    name: str | None = None
    sign_count: int | None = None
    last_used_at: datetime | None = None


class PasskeyRecord(PasskeyCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    last_used_at: datetime | None
    created_at: datetime


class PasskeyRead(BaseModel):
    """A passkey as Conta › Segurança lists it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Passkey ID.")
    name: str = Field(description="From the authenticator (1Password, iCloud Keychain…), editable.")
    created_at: datetime
    last_used_at: datetime | None = Field(description="The last sign-in with it; null when never used.")


class PasskeyRename(BaseModel):
    name: str = Field(min_length=1, description="New name of the passkey.")


class WebAuthnOptions(BaseModel):
    """What the browser's WebAuthn call takes, as py_webauthn writes it."""

    options: dict[str, Any] = Field(description="PublicKeyCredentialCreationOptions or RequestOptions, as JSON.")


class WebAuthnCredential(BaseModel):
    """What the browser's WebAuthn call gave, passed to py_webauthn as is."""

    credential: dict[str, Any] = Field(description="The PublicKeyCredential, as JSON.")
    name: str | None = Field(default=None, min_length=1, description="Name for a new passkey; else from the AAGUID.")


class TwoFactorStart(BaseModel):
    method: TwoFactorMethod = Field(description="Where the codes go: the account email, or WhatsApp.")
    phone: str | None = Field(
        default=None, pattern=r"^\+[1-9]\d{7,14}$", description="The WhatsApp number in E.164; required for whatsapp."
    )


class TwoFactorConfirm(BaseModel):
    code: str = Field(pattern=r"^\d{6}$", description="The 6 digits sent by email or WhatsApp.")


class TwoFactorResend(BaseModel):
    channel: Literal["email"] | None = Field(
        default=None, description="email sends it to the account email whatever the method (Receber por email)."
    )


class PendingSignIn(BaseModel):
    """A right password on an account with two-step verification: the code is the next step, no session yet."""

    pending: Literal[True] = True
    method: TwoFactorMethod = Field(description="Where the code went.")
    destination: str = Field(description="The email or number it went to, masked: a•••@example.com, +55 •• ••••-1234.")


class PendingSignInCreate(BaseModel):
    token_hash: str
    account_id: UUID
    expires_at: datetime
    code_hash: str
    code_sent_at: datetime
    method: TwoFactorMethod
    user_agent: str | None


class PendingSignInUpdate(BaseModel):
    code_hash: str | None = None
    code_sent_at: datetime | None = None
    attempts: int | None = None
    method: TwoFactorMethod | None = None


class PendingSignInRecord(PendingSignInCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attempts: int
    created_at: datetime


class SessionRead(BaseModel):
    """A signed-in browser as Conta › Sessões lists it."""

    id: UUID = Field(description="Session ID.")
    browser: str | None = Field(description="From the user agent (Chrome, Safari…); null when unknown.")
    system: str | None = Field(description="From the user agent (macOS, iPhone…); null when unknown.")
    created_at: datetime = Field(description="When it signed in.")
    last_seen_at: datetime = Field(description="Its last request.")
    current: bool = Field(description="Whether it is the session asking (Este aparelho).")
    method: SignInMethod = Field(description="How it signed in.")


class Reauthenticate(BaseModel):
    password: str


class SecurityEventCreate(BaseModel):
    account_id: UUID | None = None
    organization_id: UUID | None = None
    actor_id: UUID | None = None
    kind: SecurityEventKind
    data: dict[str, Any] = {}
    user_agent: str | None = None


class SecurityEventRecord(SecurityEventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class SecurityEventRead(BaseModel):
    """A line of Conta › Atividade."""

    id: UUID = Field(description="Event ID.")
    kind: SecurityEventKind
    data: dict[str, Any] = Field(description="What the kind names: the sign-in method, the passkey's name…")
    browser: str | None = Field(description="From the user agent of the request; null when unknown.")
    system: str | None = Field(description="From the user agent of the request; null when unknown.")
    created_at: datetime


class AuditEventRead(BaseModel):
    """A line of Organização › Auditoria."""

    id: UUID = Field(description="Event ID.")
    kind: SecurityEventKind
    data: dict[str, Any] = Field(description="What the kind names: the member, the base, the roles…")
    actor_id: UUID | None = Field(description="Who did it; null once their account is gone.")
    actor_name: str | None
    actor_email: str | None
    created_at: datetime
