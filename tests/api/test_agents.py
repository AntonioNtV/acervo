import httpx


async def _base(client: httpx.AsyncClient) -> str:
    response = await client.post("/v1/kbs", json={"name": "Seguros · Operação"})
    assert response.status_code == 201, response.text
    kb_id: str = response.json()["id"]
    return kb_id


async def test_create_switch_mode_and_revoke(client: httpx.AsyncClient) -> None:
    kb_id = await _base(client)

    created = await client.post(f"/v1/kbs/{kb_id}/agents", json={"name": "Claude"})
    assert created.status_code == 201, created.text
    agent = created.json()
    assert agent["mode"] == "ask" and agent["token"].startswith("acv_")
    assert agent["token_hint"] == agent["token"][-4:]

    listed = (await client.get(f"/v1/kbs/{kb_id}/agents")).json()
    assert [(item["name"], item["built_in"]) for item in listed] == [("Chat do Acervo", True), ("Claude", False)]
    assert "token" not in listed[1]

    switched = await client.patch(f"/v1/agents/{agent['id']}", json={"mode": "auto"})
    assert (switched.status_code, switched.json()["mode"], switched.json()["name"]) == (200, "auto", "Claude")

    revoked = await client.delete(f"/v1/agents/{agent['id']}")
    assert revoked.status_code == 200 and revoked.json()["revoked_at"] is not None
    chat = await client.delete(f"/v1/agents/{listed[0]['id']}")
    assert (chat.status_code, chat.json()["error"]) == (409, "conflict")
