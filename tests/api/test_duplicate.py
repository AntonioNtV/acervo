from collections.abc import Awaitable, Callable
from typing import Any

import httpx

MakeTree = Callable[..., Awaitable[Any]]


async def test_duplicate_a_folder_is_422(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["CG 2026.pdf"]})

    for path in ("Bradesco", "Bradesco/CG 2026.pdf"):
        response = await client.post(f"/v1/nodes/{tree[path].id}/duplicate")
        assert response.status_code == 422, response.text


async def test_returns_201_with_the_copy(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["Emissão.md"]})

    response = await client.post(f"/v1/nodes/{tree['Bradesco/Emissão.md'].id}/duplicate")

    assert response.status_code == 201, response.text
    copy = response.json()
    assert (copy["title"], copy["kind"], copy["parent_id"]) == ("Emissão (cópia)", "page", str(tree["Bradesco"].id))
    detail = (await client.get(f"/v1/nodes/{copy['id']}")).json()
    assert detail["page"]["markdown"] == "# Emissão\n"
