from collections.abc import Awaitable, Callable

import httpx
from fastapi import FastAPI

from acervo.schemas.account import AccountRead
from acervo.schemas.organization import OrganizationRecord
from acervo.services.mailer import FakeMailer, MailTemplate

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]


async def test_a_created_organization_is_listed_after_pessoal_with_its_creator_as_owner(
    client: httpx.AsyncClient,
) -> None:
    created = await client.post("/v1/organizations", json={"name": "  Seguros SA "})
    listed = await client.get("/v1/organizations")

    assert created.status_code == 201, created.text
    assert [(o["name"], o["personal"], o["my_role"]) for o in listed.json()] == [
        ("Pessoal", True, "owner"),
        ("Seguros SA", False, "owner"),
    ]


async def test_members_are_listed_and_a_role_change_emails_the_member(
    app: FastAPI, client: httpx.AsyncClient, make_account: MakeAccount, make_organization: MakeOrganization
) -> None:
    ana_id = (await client.get("/v1/account")).json()["id"]
    bia = await make_account(email="bia@example.com", name="Bia")
    organization_id = (await make_organization(ana_id, members={bia.id: "member"})).id

    changed = await client.patch(f"/v1/organizations/{organization_id}/members/{bia.id}", json={"role": "admin"})
    members = await client.get(f"/v1/organizations/{organization_id}/members")

    assert changed.status_code == 200, changed.text
    assert [(m["name"], m["role"]) for m in members.json()] == [("Ana", "owner"), ("Bia", "admin")]
    mailer: FakeMailer = app.state.mailer
    sent = mailer.sent[-1]
    assert (sent.to, sent.template, sent.values["old_role"], sent.values["role"]) == (
        "bia@example.com",
        MailTemplate.ROLE_CHANGED,
        "member",
        "admin",
    )
