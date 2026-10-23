import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.repositories.node_index import NodeIndexRepository


async def _states(client: httpx.AsyncClient, kb_id: str) -> dict[str, str]:
    response = await client.get(f"/v1/kbs/{kb_id}/children")
    assert response.status_code == 200, response.text
    return {node["title"]: node["index_state"] for node in response.json()}


async def test_the_tree_shows_each_index_state_and_a_retry_builds_again(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    kb_id = (await client.post("/v1/kbs", json={"name": "Seguros · Operação"})).json()["id"]
    folder = (await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "folder", "title": "Bradesco"})).json()
    page = (await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "page", "title": "Prazos"})).json()
    assert await _states(client, kb_id) == {"Bradesco": "none", "Prazos": "none"}

    indexes = NodeIndexRepository(session)
    await indexes.start(uuid.UUID(page["id"]), "v1")
    await indexes.fail(uuid.UUID(page["id"]), "v1", "não foi possível indexar")
    await session.commit()
    assert await _states(client, kb_id) == {"Bradesco": "none", "Prazos": "failed"}

    retried = await client.post(f"/v1/nodes/{page['id']}/index")
    assert retried.status_code == 202, retried.text
    assert retried.json()["index_state"] == "building"
    assert await _states(client, kb_id) == {"Bradesco": "none", "Prazos": "building"}

    assert (await client.post(f"/v1/nodes/{folder['id']}/index")).status_code == 422
    assert (await client.post(f"/v1/nodes/{uuid.uuid4()}/index")).status_code == 404
