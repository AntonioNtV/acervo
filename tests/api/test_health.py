import httpx


async def test_health_needs_no_session(anon_client: httpx.AsyncClient) -> None:
    response = await anon_client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
