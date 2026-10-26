from typing import Annotated

import httpx
import pydantic
import pytest
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, SecretStr

from acervo.api.deps import current_account
from acervo.api.main import create_app
from acervo.core.errors import (
    AcervoError,
    AuthError,
    ConflictError,
    Duplicate,
    NotFoundError,
    SameFile,
    StalePage,
    TitleTaken,
    ValidationError,
)
from acervo.core.settings import Settings

ERRORS: dict[str, type[AcervoError]] = {
    error.code: error
    for error in (
        NotFoundError,
        ConflictError,
        TitleTaken,
        Duplicate,
        StalePage,
        SameFile,
        ValidationError,
        AuthError,
        AcervoError,
    )
}


class Body(BaseModel):
    name: str


router = APIRouter(prefix="/v1/test-errors", dependencies=[Depends(current_account)])


@router.get("/{code}")
async def raise_error(code: str) -> None:
    raise ERRORS[code]("boom", details={"code": code})


@router.post("/body")
async def take_body(body: Body) -> None:
    return None


@router.get("")
async def take_query(limit: Annotated[int, Query()]) -> None:
    return None


@pytest.fixture(autouse=True)
def _test_router(app: FastAPI) -> None:
    app.include_router(router)


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("not_found", 404),
        ("conflict", 409),
        ("title_taken", 409),
        ("duplicate", 409),
        ("stale_page", 409),
        ("same_file", 409),
        ("validation", 422),
        ("unauthorized", 401),
        ("internal", 500),
    ],
)
async def test_error_maps_to_status_and_code(client: httpx.AsyncClient, code: str, status: int) -> None:
    response = await client.get(f"/v1/test-errors/{code}")

    assert response.status_code == status
    assert response.json() == {"error": code, "message": "boom", "details": {"code": code}}


async def test_invalid_body_is_422_validation_with_details(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/test-errors/body", json={"name": 3})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation"
    assert body["details"]["errors"][0]["loc"] == ["body", "name"]


async def test_invalid_query_is_422_validation(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/test-errors", params={"limit": "many"})

    assert (response.status_code, response.json()["error"]) == (422, "validation")


@pytest.mark.parametrize("headers", [{}, {"Cookie": "acervo_session=wrong"}])
async def test_route_without_a_live_session_is_401(anon_client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    response = await anon_client.get("/v1/test-errors/not_found", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized", "message": "Missing or ended session.", "details": {}}


# Health and everything that signs a person in or out answer without a session.
PUBLIC = ("/v1/health", "/v1/auth/")


async def test_routes_need_a_session(app: FastAPI, anon_client: httpx.AsyncClient) -> None:
    routes = [
        (method, path)
        for path, operations in app.openapi()["paths"].items()
        if not path.startswith(PUBLIC) and not path.startswith("/v1/test-errors")
        for method in operations
    ]
    assert routes

    statuses = {
        (method, path): (await anon_client.request(method, path.format_map(_AnyParam()))).status_code
        for method, path in routes
    }

    assert {route: status for route, status in statuses.items() if status != 401} == {}


class _AnyParam(dict[str, str]):
    """Fills every path parameter with an id, so the request reaches the route's dependencies."""

    def __missing__(self, key: str) -> str:
        return "00000000-0000-0000-0000-000000000000"


def test_empty_session_secret_is_refused_at_startup() -> None:
    with pytest.raises(pydantic.ValidationError, match="SESSION_SECRET cannot be empty"):
        create_app(Settings(_env_file=None, session_secret=SecretStr("")))
