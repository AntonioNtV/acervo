from collections.abc import Callable
from uuid import uuid4

from acervo.core.settings import RetrievalLimits, Thresholds
from acervo.domain.decisions import Choice, Question, Score
from acervo.domain.index import Passage
from acervo.model_clients.fakes import FakeDecider, FakeProbs
from acervo.pipeline.search.engine import search
from acervo.pipeline.search.tree import SearchNode


def doc(path: str, sections: dict[str, str]) -> SearchNode:
    node_id, parts = uuid4(), path.split("/")
    children = [
        SearchNode(
            id=f"{node_id}:{title}",
            node_id=node_id,
            kind="section",
            title=title,
            path=parts,
            page=page,
            end_page=page,
            passage_list=[Passage(id=f"p{page}", section_id=title, text=text, page=page, end_page=page)],
        )
        for page, (title, text) in enumerate(sections.items(), start=1)
    ]
    return SearchNode(
        id=str(node_id),
        node_id=node_id,
        kind="file",
        title=parts[-1],
        path=parts,
        built="; ".join(sections),
        loaded=children,
    )


def folder(path: str, *children: SearchNode) -> SearchNode:
    parts = path.split("/")
    return SearchNode(id=path, node_id=uuid4(), kind="folder", title=parts[-1], path=parts, loaded=list(children))


def jev(
    routes: dict[str, float], scores: dict[str, float], none: float = 0.0, set_score: float = 0.0
) -> Callable[[str, Question], FakeProbs]:
    """Routes by an option's title (others weigh 0.01); a passage scores by the first key its text contains."""

    def answer(state: str, question: Question) -> FakeProbs:
        if isinstance(question, Choice):
            raw = [routes.get(option.split("\n")[0], 0.01) for option in question.options[:-1]] + [none]
            return [weight / sum(raw) for weight in raw]
        if question.id == "evidence_set":
            return set_score
        return next((score for key, score in scores.items() if key in question.question), 0.0)

    return answer


def scored(decider: FakeDecider) -> list[str]:
    """The passages scored, in order, as the text after the evidence's header."""
    return [
        q.question.rsplit("\n\n", 1)[-1]
        for _, questions in decider.calls
        for q in questions
        if isinstance(q, Score) and q.id != "evidence_set"
    ]


def routes(decider: FakeDecider) -> list[list[Choice]]:
    return [
        [q for q in questions if isinstance(q, Choice)]
        for _, questions in decider.calls
        if isinstance(questions[0], Choice)
    ]


async def test_it_follows_the_preferred_branch_and_stops_at_a_full_answer() -> None:
    tree = [
        folder(
            "Bradesco",
            folder(
                "Bradesco/Auto",
                doc(
                    "Bradesco/Auto/Tabela auto 2026.pdf",
                    {"Franquia": "A franquia do auto é R$ 2.000.", "Vidros": "Vidros têm franquia própria."},
                ),
            ),
        ),
        folder("Itaú", doc("Itaú/Residencial.pdf", {"Incêndio": "Incêndio coberto.", "Roubo": "Roubo coberto."})),
    ]
    decider = FakeDecider(
        answer=jev(
            {"Bradesco": 0.88, "Itaú": 0.02, "Franquia": 0.9}, {"franquia do auto": 3.0, "Vidros": 2.0}, none=0.1
        )
    )
    steps = []

    async def on_step(step: object) -> None:
        steps.append(step)

    result, decisions = await search(
        "Qual a franquia do auto?", tree, decider, RetrievalLimits(per_score_call=1), Thresholds(), on_step
    )

    assert scored(decider) == ["A franquia do auto é R$ 2.000."]
    assert [(e.text, e.score, e.path) for e in result.evidence] == [
        ("A franquia do auto é R$ 2.000.", 3.0, ["Bradesco", "Auto", "Tabela auto 2026.pdf"])
    ]
    assert [
        (s.stage, s.label) for s in result.trace if s.label in {"Bradesco", "Auto", "Tabela auto 2026.pdf", "Franquia"}
    ] == [
        ("folder", "Bradesco"),
        ("folder", "Auto"),
        ("document", "Tabela auto 2026.pdf"),
        ("section", "Franquia"),
        ("passage", "Franquia"),
    ]
    assert steps == result.trace
    assert "Bradesco/Auto/Tabela auto 2026.pdf" in result.looked_in
    assert {d.step for d in decisions} == {"route", "evidence"}
    assert len(decisions) == sum(len(questions) for _, questions in decider.calls)


async def test_a_branch_none_beats_waits_until_the_evidence_is_weak() -> None:
    def tree() -> list[SearchNode]:
        return [
            folder("Auto", doc("Auto/Tabela.pdf", {"Preços": "Tabela de preços do auto."})),
            folder("Vida", doc("Vida/Condições.pdf", {"Carência": "A carência do seguro auto é de 30 dias."})),
        ]

    weak = FakeDecider(answer=jev({"Auto": 0.6, "Vida": 0.1}, {"carência": 3.0, "preços": 1.0}, none=0.3))
    result, _ = await search("Carência do auto?", tree(), weak, RetrievalLimits(), Thresholds())

    # Vida is deferred at the first level and only opened after Auto's evidence fell short.
    assert scored(weak) == ["Tabela de preços do auto.", "A carência do seguro auto é de 30 dias."]
    assert [e.section_title for e in result.evidence] == ["Carência"]

    strong = FakeDecider(answer=jev({"Auto": 0.6, "Vida": 0.1}, {"preços": 3.0}, none=0.3))
    result, _ = await search("Preços do auto?", tree(), strong, RetrievalLimits(), Thresholds())

    assert scored(strong) == ["Tabela de preços do auto."]
    assert "Vida" not in result.looked_in


async def test_after_eight_sections_of_a_document_another_document_comes_first() -> None:
    big = doc("Manual.pdf", {f"Capítulo {i}": f"Texto do capítulo {i}." for i in range(10)})
    small = doc("Resumo.pdf", {"Resumo": "Texto do resumo."})
    decider = FakeDecider(answer=jev({"Manual.pdf": 0.9, "Resumo.pdf": 0.1}, {"Texto": 1.6}))

    await search("Pergunta", [big, small], decider, RetrievalLimits(), Thresholds())

    order = scored(decider)
    assert order[:8] == [f"Texto do capítulo {i}." for i in range(8)]
    assert order.index("Texto do resumo.") < order.index("Texto do capítulo 8.")


async def test_a_hundred_children_become_grouped_menus() -> None:
    big = folder("Arquivo", *[doc(f"Arquivo/Doc {i}.pdf", {"Única": f"Texto {i}."}) for i in range(100)])
    decider = FakeDecider(answer=jev({}, {}))

    await search("Pergunta", [big], decider, RetrievalLimits(), Thresholds())

    asked = routes(decider)
    # The folder's menu offers two groups; both groups' menus go in one call.
    assert [len(choice.options) for choice in asked[0]] == [3]
    assert [len(choice.options) for choice in asked[1]] == [65, 37]


async def test_four_menus_share_one_call() -> None:
    tree = [folder(f"P{i}", doc(f"P{i}/A.pdf", {"S": "a"}), doc(f"P{i}/B.pdf", {"S": "b"})) for i in range(6)]
    decider = FakeDecider(answer=jev({}, {}))

    await search("Pergunta", tree, decider, RetrievalLimits(beam=6), Thresholds())

    assert [len(menus) for menus in routes(decider)[:3]] == [1, 4, 2]


async def test_budgets_are_never_exceeded() -> None:
    tree = [
        folder(
            f"F{f}",
            *[
                doc(f"F{f}/D{d}.pdf", {f"S{s}": f"Passagem {f}.{d}.{s} " + "x" * 40 for s in range(5)})
                for d in range(10)
            ],
        )
        for f in range(20)
    ]
    scores = {
        f"Passagem {f}.{d}.{s}": 1.5 + (f + d + s) % 10 / 10 for f in range(20) for d in range(10) for s in range(5)
    }
    decider = FakeDecider(answer=jev({}, scores))
    limits = RetrievalLimits(expansions=10, passages=20, per_score_call=6, results=5, result_chars=200)

    result, _ = await search("Pergunta", tree, decider, limits, Thresholds())

    assert sum(len(menus) for menus in routes(decider)) <= limits.expansions
    assert all(len(menus) <= limits.menus_per_call for menus in routes(decider))
    assert len(scored(decider)) <= limits.passages
    assert all(sum(q.id.startswith("evidence:") for q in questions) <= 6 for _, questions in decider.calls)
    assert 0 < len(result.evidence) <= limits.results
    assert sum(len(e.text) for e in result.evidence) <= limits.result_chars
    ranks = [(e.score, e.route_score) for e in result.evidence]
    assert ranks == sorted(ranks, reverse=True)


async def test_nothing_useful_returns_no_evidence_and_where_it_looked() -> None:
    tree = [folder("Auto", doc("Auto/Tabela.pdf", {"Preços": "Preços."})), doc("Vida.pdf", {"Carência": "Carência."})]
    decider = FakeDecider(answer=jev({}, {"Preços": 1.4}))

    result, decisions = await search("Pergunta", tree, decider, RetrievalLimits(), Thresholds())

    assert result.evidence == []
    assert set(result.looked_in) == {"Auto", "Auto/Tabela.pdf", "Vida.pdf"}
    assert [d.action for d in decisions if d.step == "evidence"] == ["dropped", "dropped"]
