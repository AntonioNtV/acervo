"""Every question the pipeline asked, with its answer and what code did with it (rule 7)."""

from acervo.domain.decisions import Answers, Choice
from acervo.schemas.proposal import Decision


def record(answers: Answers, id: str, step: str, action: str, threshold: float | None = None) -> Decision:
    question = answers.question(id)
    return Decision(
        step=step,
        question_type=question.type,
        options=list(question.options) if isinstance(question, Choice) else [question.question],
        probs=list(answers.probs[id]),
        threshold=threshold,
        action=action,
        latency_ms=answers.latency_ms,
        cached=answers.cached,
    )


def best(answers: Answers, id: str) -> tuple[int, float]:
    """The index and probability of a Choice's most likely option; a tie keeps the first."""
    probs = answers.probs[id]
    index = max(range(len(probs)), key=lambda i: (probs[i], -i))
    return index, probs[index]
