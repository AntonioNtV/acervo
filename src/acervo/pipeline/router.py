"""How the chat understands a message: guardar, organizar, perguntar or conversar (spec §1)."""

from pydantic import BaseModel, Field

from acervo.core.settings import Thresholds
from acervo.domain.cards import ROUTES, Route
from acervo.domain.decisions import Answers, Choice, Noul, Question
from acervo.model_clients.decider import Decider
from acervo.model_clients.writer import Writer
from acervo.pipeline.curator.log import Decision, record

STEP = "route"
_MEANING: dict[Route, str] = {
    "perguntar": "perguntar: quer uma resposta a partir do que está na base",
    "guardar": "guardar: traz um fato ou um arquivo para guardar na base",
    "organizar": "organizar: pede para mover, renomear ou desfazer uma mudança",
    "conversar": "conversar: cumprimenta, agradece ou fala de outra coisa",
}
INTENT = Choice(
    id="intent", question="O que a pessoa quer com esta mensagem?", options=tuple(_MEANING[r] for r in ROUTES)
)
TWO_SUBJECTS = Noul(id="two_subjects", question="A mensagem trata de duas ou mais coisas independentes?")


class RouteContext(BaseModel):
    """What surrounds the message in the chat."""

    files: list[str] = Field(default_factory=list, description="Names of the attached files.")
    page_path: str | None = Field(default=None, description="The open page, as context.")
    selection: str | None = Field(default=None, description="Text selected on that page.")
    history: list[str] = Field(default_factory=list, description="The last messages of the conversation.")


class Routed(BaseModel):
    text: str
    route: Route
    probability: float


class AskFirst(BaseModel):
    """Not clear enough: the person picks between the two likeliest readings before anything runs."""

    text: str
    options: tuple[Route, Route]


class Split(BaseModel):
    """A message about two things, each part understood on its own and handled in the same reply."""

    parts: list[Routed | AskFirst]


Understood = Routed | AskFirst | Split


def _state(message: str, context: RouteContext) -> str:
    lines = [f"Mensagem: {message}"]
    if context.files:
        lines.append(f"Arquivos anexados: {', '.join(context.files)}")
    if context.page_path:
        lines.append(f"Página aberta: {context.page_path}")
    if context.selection:
        lines.append(f"Trecho selecionado: {context.selection}")
    if context.history:
        lines += ["Mensagens anteriores:", *(f"- {text}" for text in context.history)]
    return "\n".join(lines)


async def _understand(
    message: str,
    context: RouteContext,
    decider: Decider,
    thresholds: Thresholds,
    log: list[Decision],
    extra: tuple[Question, ...] = (),
) -> tuple[Routed | AskFirst, Answers]:
    answers = await decider.ask(_state(message, context), [INTENT, *extra])
    probs = answers.probs[INTENT.id]
    first, second = sorted(range(len(ROUTES)), key=lambda i: (-probs[i], i))[:2]
    probability = probs[first]
    result: Routed | AskFirst
    if probability < thresholds.route_min:
        result = AskFirst(text=message, options=(ROUTES[first], ROUTES[second]))
        action = f"ask {result.options[0]} or {result.options[1]}"
    else:
        result = Routed(text=message, route=ROUTES[first], probability=probability)
        action = ROUTES[first]
    log.append(record(answers, INTENT.id, STEP, action, thresholds.route_min))
    return result, answers


async def route(
    message: str,
    context: RouteContext,
    decider: Decider,
    writer: Writer,
    thresholds: Thresholds,
    log: list[Decision],
) -> Understood:
    """One call with the intent and "two subjects"; a bare file is guardar without asking."""
    if not message.strip() and context.files:
        return Routed(text=message, route="guardar", probability=1.0)
    understood, answers = await _understand(message, context, decider, thresholds, log, (TWO_SUBJECTS,))
    two = answers.p_yes(TWO_SUBJECTS.id) > thresholds.route_split
    parts = await writer.split_message(message) if two else []
    split = len(parts) > 1
    log.append(record(answers, TWO_SUBJECTS.id, STEP, "split" if split else "whole", thresholds.route_split))
    if not split:
        return understood
    return Split(parts=[(await _understand(part, context, decider, thresholds, log))[0] for part in parts])
