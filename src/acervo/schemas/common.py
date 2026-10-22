from typing import Any, Literal

from pydantic import BaseModel, Field


class PageParams(BaseModel):
    """Pagination of a list route."""

    limit: int = Field(default=50, ge=1, le=200, description="Maximum number of items to return.")
    offset: int = Field(default=0, ge=0, description="Number of items to skip.")


class Paginated[T](BaseModel):
    """One page of a list and the total it was cut from."""

    items: list[T] = Field(description="Items of this page.")
    total: int = Field(description="Number of items across every page.")
    limit: int = Field(description="Limit used for this page.")
    offset: int = Field(description="Offset used for this page.")


class ErrorResponse(BaseModel):
    """Body of every error response."""

    error: str = Field(
        description="Error code: not_found, conflict, validation, unauthorized, decision_unavailable, or one the "
        "screens tell apart: title_taken, duplicate, stale_page, same_file."
    )
    message: str = Field(description="Human-readable explanation; the app shows the code's own text instead.")
    details: dict[str, Any] = Field(default_factory=dict, description="Extra context about the error.")


class HealthResponse(BaseModel):
    """Liveness of the API itself."""

    status: Literal["ok"] = Field(default="ok", description="Always ok while the API answers.")
