async def test_create_list_rename_trash_restore(client) -> None:
    created = await client.post("/kbs", json={"name": "Seguros · Operação", "description": "Apólices"})
    assert created.status_code == 201
    kb_id = created.json()["id"]
    await client.post(f"/kbs/{kb_id}/nodes", json={"kind": "page", "title": "Emissão de apólice"})

    [listed] = (await client.get("/kbs", params={"q": "operacao"})).json()
    assert (listed["id"], listed["pages"], listed["files"]) == (kb_id, 1, 0)

    renamed = await client.patch(f"/kbs/{kb_id}", json={"name": "Seguros", "description": ""})
    assert (renamed.json()["name"], renamed.json()["description"]) == ("Seguros", "")

    trashed = await client.delete(f"/kbs/{kb_id}")
    assert trashed.json()["deleted_at"] is not None
    assert (await client.get("/kbs")).json() == []
    assert [kb["id"] for kb in (await client.get("/trash/kbs")).json()] == [kb_id]

    restored = await client.post(f"/kbs/{kb_id}/restore")
    assert restored.json()["deleted_at"] is None
    assert [kb["name"] for kb in (await client.get("/kbs")).json()] == ["Seguros"]
    missing = await client.post(f"/kbs/{kb_id}/restore")
    assert (missing.status_code, missing.json()["error"]) == (404, "NotFoundError")
