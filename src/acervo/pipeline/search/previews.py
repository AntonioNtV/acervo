"""What Jev sees of a folder or a section, built at search time from the index (skill `markdown-pages`).

A section shows its page range and up to 3 excerpts chosen for the question: term weights over the document's
sections, how informative a fragment is, and a penalty for repeating one already chosen. Nothing here is retrieval:
the excerpts only describe an option Jev routes among.
"""

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from acervo.domain.index import DocIndex, Section

EXCERPTS = 3
FRAGMENT = 280
SHORTEST = 25
_WORD = re.compile(r"\w{2,}")
_COMMON = set(
    _WORD.findall(
        "as os ao aos às de da do das dos em no na nos nas um uma uns umas para por pelo pela pelos pelas com sem que "
        "qual quais quanto quantos quanta quantas como onde quando se ou não mais menos seu sua seus suas este esta "
        "isto esse essa isso ser são foi tem ter há the and of to in for on is are what which how"
    )
)


def terms(text: str) -> list[str]:
    return [word for word in _WORD.findall(text.lower()) if word not in _COMMON]


def _fragments(text: str) -> list[str]:
    """Paragraphs cut into runs of whole sentences of at most FRAGMENT characters; a longer sentence at spaces."""
    out: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        pending = ""
        for sentence in re.split(r"(?<=[.!?;])\s+", " ".join(paragraph.split())):
            if pending and len(pending) + len(sentence) + 1 > FRAGMENT:
                out.append(pending)
                pending = ""
            while len(sentence) > FRAGMENT:
                cut = sentence.rfind(" ", FRAGMENT // 2, FRAGMENT)
                cut = cut if cut > 0 else FRAGMENT
                out.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            pending = f"{pending} {sentence}".strip()
        if pending:
            out.append(pending)
    return [text for text in dict.fromkeys(out) if len(text) >= SHORTEST]


@dataclass
class _Sample:
    text: str
    section: Section
    position: int
    words: Counter[str]
    relevance: float = 0.0
    information: float = 0.0


def _similarity(a: Counter[str], b: Counter[str]) -> float:
    shared = len(a.keys() & b.keys())
    return shared / max(1, len(a) + len(b) - shared)


def _excerpt(text: str, budget: int, query: set[str]) -> str:
    """A window of `budget` characters around the first word of the question, cut at spaces."""
    if len(text) <= budget:
        return text
    hit = next((m.start() for m in _WORD.finditer(text) if m.group().lower() in query), 0)
    start = max(0, hit - budget // 3)
    if start and 0 <= (space := text.find(" ", start)) < start + 40:
        start = space + 1
    end = min(len(text), start + budget - 2)
    if end < len(text) and (space := text.rfind(" ", start, end)) > start + budget // 2:
        end = space
    return f"{'…' if start else ''}{text[start:end].strip()}{'…' if end < len(text) else ''}"


def _pages(section: Section) -> str:
    if section.page is None:
        return ""
    return f"Páginas {section.page}–{section.end_page or section.page}"


def section_previews(index: DocIndex, query: str, chars: int) -> dict[str, str]:
    """Each section's description without its title, so title and preview fit in `chars` together."""
    blocks = {block.id: block for block in index.blocks}
    own: dict[str, list[_Sample]] = {}

    def gather(section: Section) -> None:
        text = "\n\n".join(blocks[id].text for id in section.block_ids if id in blocks and blocks[id].kind != "heading")
        own[section.id] = [
            _Sample(fragment, section, position, Counter(terms(fragment)))
            for position, fragment in enumerate(_fragments(text))
        ]
        for child in section.children:
            gather(child)

    for section in index.sections:
        gather(section)

    everything = [sample for samples in own.values() for sample in samples]
    sections_with = Counter(word for samples in own.values() for word in {w for s in samples for w in s.words})
    count = max(1, len(own))

    def weight(word: str) -> float:
        frequency = sections_with[word]
        return math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))

    query_terms = set(terms(query))
    average = sum(sample.words.total() for sample in everything) / max(1, len(everything))
    for sample in everything:
        length = sample.words.total()
        for word in query_terms:
            if frequency := sample.words[word]:
                norm = 1.2 * (0.25 + 0.75 * length / max(1.0, average))
                sample.relevance += weight(word) * frequency * 2.2 / (frequency + norm)
        top = sorted((weight(word) for word in sample.words), reverse=True)[:12]
        sample.information = sum(top) / max(1, len(top))

    previews: dict[str, str] = {}

    def visit(section: Section) -> list[_Sample]:
        pool = own[section.id] + [sample for child in section.children for sample in visit(child)]
        budget = chars - len(section.title) - 1
        head = _pages(section)
        if not pool:
            previews[section.id] = head[:budget]
            return pool
        most_relevant = max(max(sample.relevance for sample in pool), 1e-9)
        most_informative = max(max(sample.information for sample in pool), 1e-9)
        chosen: list[_Sample] = []

        def choose(focused: bool) -> bool:
            best, best_score = None, -math.inf
            for sample in pool:
                redundancy = max((_similarity(prior.words, sample.words) for prior in chosen), default=0.0)
                if redundancy > 0.8 or any(prior.text == sample.text for prior in chosen):
                    continue
                score = (
                    (sample.relevance / most_relevant if focused else 0)
                    + 0.2 * sample.information / most_informative
                    + (0.15 if all(prior.section is not sample.section for prior in chosen) else 0)
                    + (0.05 if sample.position == 0 else 0)
                    - 0.45 * redundancy
                )
                if score > best_score:
                    best, best_score = sample, score
            if best is None:
                return False
            chosen.append(best)
            return True

        if most_relevant > 1e-9:
            choose(True)
        # The section's opening says what it is about, whatever the question.
        opening = (own[section.id] or pool)[0]
        if all(prior.text != opening.text for prior in chosen):
            chosen.append(opening)
        while len(chosen) < EXCERPTS and choose(most_relevant > 1e-9):
            pass
        prefix = f"{head}\nTrechos (parciais):" if head else "Trechos (parciais):"
        labels = [
            f"\n[{sample.section.title[:60]}{f', p. {sample.section.page}' if sample.section.page else ''}] "
            for sample in chosen
        ]
        share = (budget - len(prefix) - sum(map(len, labels))) // len(chosen)
        excerpts = (_excerpt(sample.text, share, query_terms) for sample in chosen)
        previews[section.id] = (prefix + "".join(map(str.__add__, labels, excerpts)))[:budget]
        return pool

    for section in index.sections:
        visit(section)
    return previews


def folder_description(children: Sequence[tuple[str, str]], chars: int) -> str:
    """A folder as its children's titles and outlines, each given an equal share of `chars`."""
    if not children:
        return ""
    prefix = "Contém:"
    share = max(0, (chars - len(prefix)) // len(children) - 1)
    lines = (f"\n{title}: {outline}" if outline else f"\n{title}" for title, outline in children)
    return prefix + "".join(line[: share + 1] for line in lines)
