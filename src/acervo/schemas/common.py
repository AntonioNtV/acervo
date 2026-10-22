from typing import Any, Literal

from pydantic import BaseModel, Field


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
