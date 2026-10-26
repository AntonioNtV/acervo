import uuid
from dataclasses import dataclass, field

from acervo.domain.links import normalize, resolve, rewrite, targets, unlink

BRADESCO, PORTO = uuid.uuid4(), uuid.uuid4()


@dataclass(frozen=True)
class Page:
    title: str
    parent_id: uuid.UUID | None
    id: uuid.UUID = field(default_factory=uuid.uuid4)


def test_normalize_collapses_spaces_and_case() -> None:
    assert normalize("  Tabela  de\tPrazos ") == "tabela de prazos"


def test_targets_are_normalized_and_unique() -> None:
    markdown = "Ver [[Renovação]], [[ renovação ]], [[Tabela  de   prazos]], [[ ]] e [Sinistro]."

    assert targets(markdown) == {"renovação", "tabela de prazos"}


def test_targets_ignore_the_section() -> None:
    markdown = "Ver [[Renovação#Documentos]], ![[ renovação # Prazos ]], ![[Sinistro]] e [[#Topo]]."

    assert targets(markdown) == {"renovação", "sinistro"}


def test_resolve_missing_ambiguous_and_same_folder() -> None:
    renewal = Page("Renovação", BRADESCO)
    porto_claim, bradesco_claim = Page("Sinistro", PORTO), Page("Sinistro", BRADESCO)
    candidates = [renewal, porto_claim, bradesco_claim]
    wanted = ["renovação", "sinistro", "cancelamento"]

    assert resolve(wanted, candidates, None) == {
        "renovação": renewal.id,
        "sinistro": "ambiguous",
        "cancelamento": "missing",
    }
    assert resolve(["sinistro"], candidates, PORTO) == {"sinistro": porto_claim.id}


def test_resolve_titles_with_repeated_spaces() -> None:
    page = Page("Tabela  de   prazos", PORTO)

    assert resolve([normalize("Tabela de  prazos")], [page], None) == {"tabela de prazos": page.id}


def test_rewrite_whatever_the_case_and_spacing() -> None:
    markdown = "Antes da [[Renovação]], ver [[ renovação ]] e [[Renovação anual antiga]].\n"

    assert rewrite(markdown, "Renovação", "Renovação anual") == (
        "Antes da [[Renovação anual]], ver [[Renovação anual]] e [[Renovação anual antiga]].\n"
    )


def test_unlink_turns_the_given_targets_into_text() -> None:
    markdown = "Ver [[Renovação]] e [[ renovação  anual ]], [[Sinistro]] e [[Renovação]].\n[[Vistoria]]\n"

    assert unlink(markdown, {"renovação", "renovação anual", "vistoria"}) == (
        "Ver Renovação e renovação  anual, [[Sinistro]] e Renovação.\nVistoria\n"
    )


def test_rewrite_keeps_the_section() -> None:
    markdown = "![[Renovação#Documentos]]\n\nVer [[ renovação #Prazos ]] e [[Renovação]].\n"

    assert rewrite(markdown, "Renovação", "Novo") == "![[Novo#Documentos]]\n\nVer [[Novo#Prazos ]] e [[Novo]].\n"
