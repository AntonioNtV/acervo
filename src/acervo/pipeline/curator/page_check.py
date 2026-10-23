"""What the page the descent reached already says about the input: one call (skill `curator-agent`)."""

from dataclasses import dataclass, field

from acervo.core.settings import Thresholds
from acervo.domain.decisions import Choice, Noul, Question
from acervo.domain.sections import sections
from acervo.model_clients.decider import Decider
from acervo.pipeline.curator.log import Decision, best, record
from acervo.pipeline.curator.options import MAX_OPTIONS
from acervo.pipeline.curator.tree import PageText

STEP = "page_check"
NO_LINE = "nenhuma linha"


@dataclass
class PageSection:
    # Empty for the text before the first ##.
    anchor: str
    heading: str
    lines: list[str] = field(default_factory=list)

    @property
    def markdown(self) -> str:
        return "\n".join([f"## {self.heading}", *self.lines] if self.heading else self.lines)


@dataclass
class PageCheck:
    covered: bool
    contradicts: bool
    section: PageSection
    # The line about the same thing as the input, when there is one: the input edits it.
    line: str | None


def split(markdown: str) -> list[PageSection]:
    """The page cut at its ## headings, the text before the first one included."""
    headings = iter(sections(markdown))
    parts = [PageSection("", "")]
    in_code = False
    for line in markdown.splitlines():
        if line.startswith(("```", "~~~")):
            in_code = not in_code
        if not in_code and sections(line):
            heading = next(headings)
            parts.append(PageSection(heading.anchor, heading.heading))
        else:
            parts[-1].lines.append(line)
    return parts


def _content(line: str) -> bool:
    text = line.strip()
    return bool(text) and not text.startswith(("#", "<!--"))


async def check_page(
    state: str, page: PageText, decider: Decider, thresholds: Thresholds, log: list[Decision]
) -> PageCheck:
    parts = split(page.markdown)
    headed = [part for part in parts if part.heading]
    lines = list(dict.fromkeys(line for part in parts for line in part.lines if _content(line)))
    questions: list[Question] = [
        Noul(id="covered", question="O que a entrada diz já está escrito nesta página?"),
        Noul(id="contradicts", question="A entrada contradiz algo escrito nesta página?"),
    ]
    if headed:
        questions.append(
            Choice(
                id="section",
                question="Em qual seção da página a entrada se encaixa?",
                options=tuple(part.heading for part in headed),
            )
        )
    if lines and len(lines) < MAX_OPTIONS:
        questions.append(
            Choice(
                id="line",
                question="Qual linha da página fala do mesmo assunto que a entrada?",
                options=(*lines, NO_LINE),
            )
        )
    answers = await decider.ask(f"{state}\n\n---\n{page.markdown}", questions)

    covered = answers.p_yes("covered") > thresholds.covered
    contradicts = answers.p_yes("contradicts") > thresholds.contradicts
    section = headed[best(answers, "section")[0]] if headed else parts[0]
    line = None
    if "line" in answers.probs:
        index, p = best(answers, "line")
        picked = (*lines, NO_LINE)[index]
        line = picked if picked != NO_LINE and p >= thresholds.same_line else None
    if line is not None:
        section = next(part for part in parts if line in part.lines)

    log.append(record(answers, "covered", STEP, "already_written" if covered else "not_written", thresholds.covered))
    log.append(
        record(answers, "contradicts", STEP, "conflict" if contradicts else "no_conflict", thresholds.contradicts)
    )
    if headed:
        log.append(record(answers, "section", STEP, f"section {section.anchor}"))
    if "line" in answers.probs:
        log.append(record(answers, "line", STEP, "edit" if line else "append", thresholds.same_line))
    return PageCheck(covered, contradicts, section, line)
