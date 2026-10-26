from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import CodeInvalid, InviteMismatch
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, EmailCodeIn, SignUp
from acervo.schemas.organization import InviteCreate, MembershipCreate, OrganizationRecord
from acervo.services.access_service import AccessService
from acervo.services.auth_service import AuthService
from acervo.services.invite_service import InviteService
from acervo.services.mailer import FakeMailer, MailTemplate
from acervo.services.session_service import SessionService

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]
MakeTree = Callable[..., Awaitable[Any]]


class Clock:
    def __init__(self) -> None:
        # Real time: `make_account` rows get the database's clock.
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
async def entered(uow: UnitOfWork, session: AsyncSession) -> AsyncIterator[UnitOfWork]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield uow


@pytest.fixture
def invites(entered: UnitOfWork, fake_mailer: FakeMailer, clock: Clock) -> InviteService:
    return InviteService(entered, fake_mailer, AccessService(entered), clock)


@pytest.fixture
async def ana(make_account: MakeAccount) -> AccountRead:
    return await make_account()


@pytest.fixture
async def team(ana: AccountRead, make_organization: MakeOrganization) -> OrganizationRecord:
    return await make_organization(ana.id)


def last_link(fake_mailer: FakeMailer) -> str:
    return [mail for mail in fake_mailer.sent if mail.template == MailTemplate.ORG_INVITE][-1].values["link"]


async def is_member(uow: UnitOfWork, account: AccountRead, team: OrganizationRecord) -> bool:
    return await AccessService(uow).org_role(account.id, team.id) == "member"


@pytest.mark.parametrize("death", ["expired", "revoked", "used"])
async def test_a_dead_link_is_refused(
    death: str,
    invites: InviteService,
    ana: AccountRead,
    team: OrganizationRecord,
    make_account: MakeAccount,
    fake_mailer: FakeMailer,
    clock: Clock,
) -> None:
    julia = await make_account(email="julia@example.com", name="Julia")
    [invite] = await invites.invite_to_organization(ana.id, team.id, InviteCreate(emails=[julia.email], role="member"))
    token = last_link(fake_mailer)
    if death == "expired":
        clock.advance(timedelta(days=7, seconds=1))
    elif death == "revoked":
        await invites.revoke(ana.id, invite.id)
    else:
        await invites.accept(julia.id, token)

    with pytest.raises(CodeInvalid):
        await invites.accept(julia.id, token)


async def test_an_invite_for_another_email_is_refused(
    invites: InviteService,
    entered: UnitOfWork,
    ana: AccountRead,
    team: OrganizationRecord,
    make_account: MakeAccount,
    fake_mailer: FakeMailer,
) -> None:
    bruno = await make_account(email="bruno@example.com", name="Bruno")
    await invites.invite_to_organization(ana.id, team.id, InviteCreate(emails=["julia@example.com"], role="member"))

    with pytest.raises(InviteMismatch) as refused:
        await invites.accept(bruno.id, last_link(fake_mailer))
    assert refused.value.details == {"email": "julia@…"}
    assert not await is_member(entered, bruno, team)


async def test_signing_up_with_an_invited_email_joins_once_the_email_is_confirmed(
    invites: InviteService,
    entered: UnitOfWork,
    ana: AccountRead,
    team: OrganizationRecord,
    fake_mailer: FakeMailer,
    clock: Clock,
) -> None:
    await invites.invite_to_organization(ana.id, team.id, InviteCreate(emails=["julia@example.com"], role="member"))
    auth = AuthService(entered, SessionService(entered, 30, clock), fake_mailer, clock)

    await auth.sign_up(SignUp(name="Julia Lima", email="Julia@example.com", password="senha-de-teste"))
    code = fake_mailer.sent[-1].values["code"]
    julia, _ = await auth.verify_email(EmailCodeIn(email="julia@example.com", code=code), None)

    assert await is_member(entered, julia, team)
    accepted = fake_mailer.sent[-1]
    assert (accepted.to, accepted.template, accepted.values["member_email"]) == (
        ana.email,
        MailTemplate.INVITE_ACCEPTED,
        "Julia@example.com",
    )
    assert await invites.pending_for_organization(ana.id, team.id) == []


async def test_inviting_an_email_again_resends_its_invite(
    invites: InviteService,
    entered: UnitOfWork,
    ana: AccountRead,
    team: OrganizationRecord,
    make_account: MakeAccount,
    fake_mailer: FakeMailer,
    clock: Clock,
) -> None:
    julia = await make_account(email="julia@example.com", name="Julia")
    data = InviteCreate(emails=["julia@example.com"], role="member")
    [first] = await invites.invite_to_organization(ana.id, team.id, data)
    old_token = last_link(fake_mailer)
    clock.advance(timedelta(minutes=2))

    [again] = await invites.invite_to_organization(
        ana.id, team.id, InviteCreate(emails=["JULIA@example.com"], role="member")
    )

    assert again.id == first.id
    assert [i.id for i in await invites.pending_for_organization(ana.id, team.id)] == [first.id]
    assert len([mail for mail in fake_mailer.sent if mail.template == MailTemplate.ORG_INVITE]) == 2
    with pytest.raises(CodeInvalid):
        await invites.accept(julia.id, old_token)
    await invites.accept(julia.id, last_link(fake_mailer))
    assert await is_member(entered, julia, team)


async def test_a_member_of_the_organization_is_added_to_the_base_at_once(
    invites: InviteService,
    entered: UnitOfWork,
    ana: AccountRead,
    team: OrganizationRecord,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
    make_tree: MakeTree,
    fake_mailer: FakeMailer,
) -> None:
    julia = await make_account(email="julia@example.com", name="Julia")
    await entered.memberships.create(MembershipCreate(organization_id=team.id, account_id=julia.id, role="member"))
    tree = await make_tree({}, organization=team.id)

    issued = await invites.invite_to_base(ana.id, tree.kb.id, InviteCreate(emails=[julia.email], role="admin"))

    assert issued == []
    added = await entered.base_members.get_by(kb_id=tree.kb.id, account_id=julia.id)
    assert added is not None
    assert added.role == "admin"
    assert (fake_mailer.sent[-1].to, fake_mailer.sent[-1].template) == (julia.email, MailTemplate.BASE_SHARED)


async def test_a_guest_of_a_team_base_gets_only_the_base_role(
    invites: InviteService,
    entered: UnitOfWork,
    ana: AccountRead,
    team: OrganizationRecord,
    make_account: MakeAccount,
    make_tree: MakeTree,
    fake_mailer: FakeMailer,
) -> None:
    carla = await make_account(email="carla@example.com", name="Carla")
    tree = await make_tree({}, organization=team.id)
    await invites.invite_to_base(ana.id, tree.kb.id, InviteCreate(emails=[carla.email], role="reader"))

    await invites.accept(carla.id, last_link(fake_mailer))

    access = AccessService(entered)
    assert (await access.base_role(carla.id, tree.kb.id), await access.org_role(carla.id, team.id)) == ("reader", None)
    assert fake_mailer.sent[-1].values["link"] == f"/kbs/{tree.kb.id}"
