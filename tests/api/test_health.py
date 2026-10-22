import httpx


async def test_health_needs_no_key(client: httpx.AsyncClient) -> None:
    del client.headers["X-API-Key"]

    response = await client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
