"""The `Writer` over PydanticAI: any provider, one model per role from `LlmRoles` (skill `llm-calls`)."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.exceptions import ModelOverloadedError, ModelRateLimitError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import Model

from acervo.domain.cards import Card, CardInput, PatchRequest, WrittenPatch

PROMPTS = Path(__file__).parent / "prompts"
RATE_LIMIT_ATTEMPTS = 4
RATE_LIMIT_FIRST_WAIT = 1.0


class InvalidOutput(Exception):
    """The model's output failed validation twice (once, then its single retry); `raw` is what it last sent."""

    def __init__(self, role: str, raw: str) -> None:
        super().__init__(f"{role}: invalid output after one retry: {raw}")
        self.role = role
        self.raw = raw


def prompt(role: str) -> str:
    return (PROMPTS / f"{role}.md").read_text()


def make_agent(model: Model | str, output_type: Any, deps_type: Any = None) -> Agent[Any, Any]:
    # A model string is resolved at the first call, so building a client needs no provider key.
    return Agent(model, output_type=output_type, deps_type=deps_type, retries={"output": 1}, defer_model_check=True)


async def run(role: str, agent: Agent[Any, Any], user_prompt: str, deps: Any = None) -> Any:
    """One run of `agent`, waiting and trying again on a rate limit or an overload (429, 529)."""
    for attempt in range(RATE_LIMIT_ATTEMPTS):
        with capture_run_messages() as messages:
            try:
                result = await agent.run(user_prompt, deps=deps)
            except (ModelRateLimitError, ModelOverloadedError) as error:
                if attempt == RATE_LIMIT_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(error.retry_after or RATE_LIMIT_FIRST_WAIT * 2**attempt)
                continue
            except UnexpectedModelBehavior as error:
                raise InvalidOutput(role, _last_raw(messages)) from error
        return result.output
    raise AssertionError("unreachable")


def _last_raw(messages: list[ModelMessage]) -> str:
    response = next((message for message in reversed(messages) if isinstance(message, ModelResponse)), None)
    if response is None:
        return ""
    return "\n".join(
        part.args_as_json_str() if isinstance(part, ToolCallPart) else part.content
        for part in response.parts
        if isinstance(part, ToolCallPart | TextPart)
    )


class LlmWriter:
    """Each role's prompt file filled with its input, sent to the role's model, its output validated."""

    def __init__(self, models: Mapping[str, Model | str]) -> None:
        self._agents = {
            "card": make_agent(models["card"], Card),
            "patch": make_agent(models["patch"], WrittenPatch),
        }
        self._prompts = {role: prompt(role) for role in self._agents}

    async def card(self, source: CardInput) -> Card:
        card: Card = await self._write(
            "card", text=source.text, file_name=source.file_name or "", outline="\n".join(source.outline)
        )
        return card

    async def patch(self, request: PatchRequest) -> WrittenPatch:
        patch: WrittenPatch = await self._write(
            "patch",
            heading=request.heading,
            section=request.section_markdown,
            action=request.action,
            card=request.card.model_dump_json(),
        )
        return patch

    async def _write(self, role: str, **values: str) -> Any:
        return await run(role, self._agents[role], self._prompts[role].format_map(values))
