"""One test per row of the policy table of skill `curator-agent`."""

import uuid
from collections.abc import Callable
from typing import Any
from uuid import UUID

from acervo.core.settings import Thresholds
from acervo.domain.cards import Card, CardInput, Placement, WrittenPatch
from acervo.domain.patch import Patch, apply
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.pipeline.curator.policy import AlreadyWritten, NotSure, Propose, file_pdf, file_text
from acervo.pipeline.curator.tree import PageText
from acervo.schemas.proposal import (
    ConflictPayload,
    CreatePagePayload,
    Decision,
    PatchPayload,
    ReplacePdfPayload,
    SavePdfPayload,
)

Make = Callable[[Any], Any]
TREE = {"Bradesco": {"Residencial": ["Emissão de apólice.md", "CG 2026.pdf"]}, "Itaú": []}
PAGE = "Bradesco/Residencial/Emissão de apólice.md"
MARKDOWN = "# Emissão de apólice\n\n## Prazos\n- Emissão leva 3 dias úteis\n\n## Documentos\n- RG e CPF\n"
VERSION = uuid.uuid4()
FACT = CardInput(text="Emissão leva 5 dias úteis")
PDF = CardInput(text="Condições gerais 2027", file_name="cg.pdf", outline=["Coberturas"])

# Down to the page, sure enough to show no second place.
TO_PAGE = {
    "descent:": {"Bradesco (pasta)": 1.0},
    "descent:Bradesco": {"Residencial (pasta)": 1.0},
    "descent:Bradesco/Residencial": {"Emissão de apólice (página)": 0.95, "nova página aqui": 0.05},
}
TO_FOLDER = {"descent:": {"Bradesco (pasta)": 1.0}, "descent:Bradesco": {"Residencial (pasta)": 1.0}}


def _page_check(
    covered: float = 0.1, contradicts: float = 0.1, line: str = "nenhuma linha", p_line: float = 0.8
) -> dict[str, Any]:
    return {"covered": covered, "contradicts": contradicts, "section": {"Prazos": 0.9}, "line": {line: p_line}}


def _reader(snap: Any) -> Callable[[UUID], Any]:
    async def read(page_id: UUID) -> PageText:
        assert page_id == snap[PAGE].id
        return PageText(page_id=page_id, version_id=VERSION, markdown=MARKDOWN)

    return read


async def _text(snap: Any, decider: FakeDecider, writer: FakeWriter, thresholds: Thresholds) -> Any:
    return await file_text(FACT, snap.tree, _reader(snap), decider, writer, thresholds, [])


async def test_below_place_min_asks_with_the_top_3(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {
        "descent:": {"Bradesco (pasta)": 0.4, "Itaú (pasta)": 0.35, "nova página aqui": 0.25},
        "descent:Bradesco": {"nova página aqui": 1.0},
        "descent:Itaú": {"nova página aqui": 1.0},
    }
    log: list[Decision] = []

    filed = await file_text(FACT, snap.tree, _reader(snap), fake_decider, fake_writer, thresholds, log)

    assert filed == NotSure(
        options=[
            Placement(node_id=snap["Bradesco"].id, path="Bradesco", landing="new_page", probability=0.4),
            Placement(node_id=snap["Itaú"].id, path="Itaú", landing="new_page", probability=0.35),
            Placement(node_id=None, path="", landing="new_page", probability=0.25),
        ],
        # What waits in "Sem lugar definido", under the likeliest place, from the one card written.
        payload=CreatePagePayload(
            parent_id=snap["Bradesco"].id, parent_path="Bradesco", title="Nota", markdown="# Nota\n\n- Uma nota\n"
        ),
    )
    assert (log[-1].threshold, log[-1].action) == (thresholds.place_min, "ask_top_3")
    assert fake_writer.inputs["card"] == [FACT]


async def test_covered_is_already_written(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {**TO_PAGE, **_page_check(covered=0.85)}

    filed = await _text(snap, fake_decider, fake_writer, thresholds)

    assert filed == AlreadyWritten(
        page_id=snap[PAGE].id, path=PAGE.removesuffix(".md"), anchor="prazos", heading="Prazos"
    )
    assert "patch" not in fake_writer.inputs


async def test_contradicts_is_a_conflict(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {**TO_PAGE, **_page_check(contradicts=0.7, line="- Emissão leva 3 dias úteis")}
    fake_writer.patch_output = WrittenPatch(
        lines=["- Emissão leva 5 dias úteis"], replaces="- Emissão leva 3 dias úteis"
    )

    filed = await _text(snap, fake_decider, fake_writer, thresholds)

    assert filed == Propose(
        payload=ConflictPayload(
            page_id=snap[PAGE].id,
            path="Bradesco/Residencial/Emissão de apólice",
            base_version_id=VERSION,
            anchor="prazos",
            heading="Prazos",
            current="- Emissão leva 3 dias úteis",
            new="- Emissão leva 5 dias úteis",
        )
    )


async def test_a_conflict_with_no_line_keeps_the_title_and_the_other_lines(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    markdown = "# Emissão de apólice\n\nEmissão leva 3 dias úteis.\nVale para todo o Brasil.\n"
    fake_decider.table = {**TO_PAGE, "covered": 0.1, "contradicts": 0.7, "line": {"nenhuma linha": 0.9}}
    fake_writer.patch_output = WrittenPatch(lines=["Emissão leva 5 dias úteis."])

    async def read(page_id: UUID) -> PageText:
        return PageText(page_id=page_id, version_id=VERSION, markdown=markdown)

    filed = await file_text(FACT, snap.tree, read, fake_decider, fake_writer, thresholds, [])

    assert isinstance(filed, Propose) and isinstance(filed.payload, ConflictPayload)
    payload = filed.payload
    assert (payload.anchor, payload.current, fake_writer.inputs["patch"][0].action) == ("", "", "append")
    # As ProposalService applies a conflict.
    change = Patch(payload.anchor, "replace", payload.new.splitlines(), payload.current)
    assert apply(markdown, change, "<!-- origem -->") == f"{markdown}Emissão leva 5 dias úteis. <!-- origem -->\n"


async def test_on_a_page_it_appends_to_the_section(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {**TO_PAGE, **_page_check()}
    fake_writer.patch_output = WrittenPatch(lines=["- Endosso leva 2 dias úteis"])

    filed = await _text(snap, fake_decider, fake_writer, thresholds)

    assert isinstance(filed, Propose) and isinstance(filed.payload, PatchPayload)
    assert (filed.payload.kind, filed.payload.op, filed.payload.anchor) == ("append", "append", "prazos")
    assert filed.payload.lines == ["- Endosso leva 2 dias úteis"]
    assert fake_writer.inputs["patch"][0].section_markdown == "## Prazos\n- Emissão leva 3 dias úteis\n"
    # The page check is one call: covered, contradicts, section and line together.
    assert [q.id for q in fake_decider.calls[-1][1]] == ["covered", "contradicts", "section", "line"]


async def test_on_a_page_a_line_about_the_same_thing_is_edited(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {**TO_PAGE, **_page_check(line="- RG e CPF")}

    filed = await _text(snap, fake_decider, fake_writer, thresholds)

    assert isinstance(filed, Propose) and isinstance(filed.payload, PatchPayload)
    assert (filed.payload.kind, filed.payload.op, filed.payload.line) == ("edit", "replace", "- RG e CPF")
    assert filed.payload.anchor == "documentos"


async def test_a_line_below_same_line_is_appended_to_not_edited(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {**TO_PAGE, **_page_check(line="- RG e CPF", p_line=thresholds.same_line - 0.1)}

    filed = await _text(snap, fake_decider, fake_writer, thresholds)

    assert isinstance(filed, Propose) and isinstance(filed.payload, PatchPayload)
    assert (filed.payload.kind, filed.payload.op) == ("append", "append")


async def test_on_a_folder_it_creates_a_page(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {**TO_FOLDER, "descent:Bradesco/Residencial": {"nova página aqui": 1.0}}
    fake_writer.card_output = Card(title="Endosso", subject="Prazo de endosso")
    fake_writer.patch_output = WrittenPatch(lines=["- Endosso leva 2 dias úteis"])

    filed = await _text(snap, fake_decider, fake_writer, thresholds)

    assert filed == Propose(
        payload=CreatePagePayload(
            parent_id=snap["Bradesco/Residencial"].id,
            parent_path="Bradesco/Residencial",
            title="Endosso",
            markdown="# Endosso\n\n- Endosso leva 2 dias úteis\n",
        )
    )


async def test_a_pdf_that_is_a_new_version_replaces_it(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    pdf = "Bradesco/Residencial/CG 2026.pdf"
    fake_decider.table = {**TO_FOLDER, "descent:Bradesco/Residencial": {"salvar aqui": 1.0}, f"new_version:{pdf}": 0.75}

    filed = await file_pdf(PDF, snap.tree, fake_decider, fake_writer, thresholds, [])

    assert filed == Propose(payload=ReplacePdfPayload(node_id=snap[pdf].id, path=pdf))
    assert fake_writer.inputs["card"] == [PDF]


async def test_a_pdf_otherwise_is_saved_with_the_suggested_name(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    pdf = "Bradesco/Residencial/CG 2026.pdf"
    fake_decider.table = {**TO_FOLDER, "descent:Bradesco/Residencial": {"salvar aqui": 1.0}, f"new_version:{pdf}": 0.7}
    fake_writer.card_output = Card(title="CG", subject="Condições gerais", file_name="CG Residencial 2027.pdf")

    filed = await file_pdf(PDF, snap.tree, fake_decider, fake_writer, thresholds, [])

    assert filed == Propose(
        payload=SavePdfPayload(
            parent_id=snap["Bradesco/Residencial"].id,
            parent_path="Bradesco/Residencial",
            name="CG Residencial 2027.pdf",
        )
    )


async def test_below_place_show_second_the_second_path_comes_along(
    make_snapshot: Make, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {
        "descent:": {"Bradesco (pasta)": 0.8, "Itaú (pasta)": 0.2},
        "descent:Bradesco": {"nova página aqui": 1.0},
        "descent:Itaú": {"nova página aqui": 1.0},
    }

    filed = await _text(snap, fake_decider, fake_writer, thresholds)

    assert isinstance(filed, Propose) and isinstance(filed.payload, CreatePagePayload)
    assert filed.payload.parent_id == snap["Bradesco"].id
    assert filed.alternatives == [Placement(node_id=snap["Itaú"].id, path="Itaú", landing="new_page", probability=0.2)]
