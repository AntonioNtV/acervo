"""The retrieval eval's PDFs, written with PyMuPDF on each run: a long one with bookmarks, one whose sections are only
headings in a larger font, and one of tables. `base.json` names them by the keys of `BUILDERS`; the facts the cases
ask about sit on the pages listed here."""

from collections.abc import Callable

import pymupdf

BODY = pymupdf.Rect(72, 110, 523, 770)

ALLIANZ_CHAPTERS = [
    "Disposições preliminares",
    "Coberturas básicas",
    "Coberturas adicionais",
    "Assistência 24 horas",
    "Vidros",
    "Franquias",
    "Riscos excluídos",
    "Âmbito geográfico",
    "Indenização integral",
    "Indenização parcial",
    "Salvados",
    "Sub-rogação",
    "Obrigações do segurado",
    "Aviso de sinistro",
    "Documentação do sinistro",
    "Eventos da natureza",
    "Bônus",
    "Pagamento do prêmio",
    "Cancelamento e rescisão",
    "Disposições finais",
]
ALLIANZ_FACTS = {
    12: "Carro reserva: o plano Premium dá direito a 15 dias de carro reserva por sinistro coberto.",
    47: "A franquia para troca de para-brisa é de R$ 450 por evento; faróis e retrovisores têm franquia de R$ 220.",
    88: "Caracteriza-se a perda total quando os prejuízos atingem 75% do valor do veículo na tabela FIPE.",
    137: "O segurado tem 7 dias corridos, contados do registro do boletim de ocorrência, para comunicar o roubo ou o "
    "furto do veículo à Allianz.",
    156: "Danos por enchente ou alagamento só são indenizados se o veículo não estava estacionado em área de risco "
    "sinalizada pela Defesa Civil.",
    184: "No cancelamento a pedido do segurado, a devolução do prêmio segue a tabela de prazo curto da SUSEP.",
    199: "Fica eleito o foro do domicílio do segurado para dirimir qualquer questão deste contrato.",
}

PORTO_SECTIONS = [
    "Apresentação",
    "Coberturas",
    "Assistência residencial",
    "Aceitação de riscos",
    "Sinistros",
    "Comissões e repasses",
]
PORTO_FACTS = {
    6: "A cobertura de danos elétricos tem limite máximo de R$ 30.000 por evento.",
    10: "A assistência residencial inclui até 3 atendimentos de encanador por vigência, sem custo para o cliente.",
    14: "Imóveis construídos em madeira ou taipa não são aceitos no Porto Residencial.",
    18: "O cliente tem 15 dias, contados do aviso de sinistro, para enviar o orçamento do reparo.",
    23: "A comissão do corretor no Porto Residencial é de 30% do prêmio líquido, repassada até o dia 10 do mês "
    "seguinte.",
}

BRADESCO_TABLES = [
    (
        "Tabela 1 · Franquias por categoria (R$)",
        ["Categoria", "Normal", "Reduzida", "Majorada"],
        [
            ["Passeio nacional", "3.500", "1.750", "7.000"],
            ["Passeio importado", "5.200", "2.600", "10.400"],
            ["Utilitário", "4.100", "2.050", "8.200"],
            ["Motocicleta", "1.900", "950", "3.800"],
        ],
    ),
    (
        "Tabela 2 · Desconto por classe de bônus",
        ["Classe", "Desconto"],
        [[str(level), f"{discount}%"] for level, discount in enumerate([5, 10, 13, 16, 19, 22, 25, 28, 31, 35], 1)],
    ),
    (
        "Tabela 3 · Coberturas adicionais (prêmio anual)",
        ["Cobertura", "Prêmio anual"],
        [
            ["Vidros", "R$ 290"],
            ["Carro reserva 15 dias", "R$ 380"],
            ["Martelinho de ouro", "R$ 160"],
            ["Acidentes pessoais de passageiros", "R$ 120"],
        ],
    ),
    (
        "Tabela 4 · Guincho por plano de assistência",
        ["Plano", "Guincho"],
        [["Básico", "200 km"], ["Intermediário", "400 km"], ["Completo", "sem limite de km"]],
    ),
]


def _filler(title: str, number: int) -> str:
    return (
        f"Esta página trata de {title.lower()} e se aplica a todas as apólices do produto. "
        f"Item {number}.1: as disposições seguem as condições contratadas e a legislação vigente. "
        f"Item {number}.2: os valores e prazos constam da apólice e de seus anexos."
    )


def allianz_auto() -> bytes:
    """200 pages, 10 per chapter, each chapter a bookmark."""
    document = pymupdf.open()
    for number in range(1, 201):
        chapter = (number - 1) // 10
        title = ALLIANZ_CHAPTERS[chapter]
        page = document.new_page()
        header = f"Allianz Auto · Condições Gerais 2026 · Capítulo {chapter + 1} · {title}"
        page.insert_text((72, 80), header, fontsize=9)
        body = _filler(title, number)
        if number in ALLIANZ_FACTS:
            body += "\n\n" + ALLIANZ_FACTS[number]
        page.insert_textbox(BODY, body, fontsize=11)
    document.set_toc([[1, f"{i + 1}. {title}", i * 10 + 1] for i, title in enumerate(ALLIANZ_CHAPTERS)])
    return _bytes(document)


def porto_residencial() -> bytes:
    """24 pages, 4 per section, without bookmarks: each section opens with a heading in 18 pt."""
    document = pymupdf.open()
    for number in range(1, 25):
        title = PORTO_SECTIONS[(number - 1) // 4]
        page = document.new_page()
        if (number - 1) % 4 == 0:
            page.insert_text((72, 90), title, fontsize=18)
        body = _filler(title, number)
        if number in PORTO_FACTS:
            body += "\n\n" + PORTO_FACTS[number]
        page.insert_textbox(BODY, body, fontsize=11)
    return _bytes(document)


def bradesco_tabela_auto() -> bytes:
    """One ruled table per page, with its title above it."""
    document = pymupdf.open()
    for title, header, rows in BRADESCO_TABLES:
        page = document.new_page()
        page.insert_text((72, 80), "Bradesco Auto · Tabela auto 2026", fontsize=9)
        page.insert_text((72, 110), title, fontsize=14)
        width = (BODY.x1 - BODY.x0) / len(header)
        for row_index, row in enumerate([header, *rows]):
            top = 130 + row_index * 24
            for column, cell in enumerate(row):
                box = pymupdf.Rect(BODY.x0 + column * width, top, BODY.x0 + (column + 1) * width, top + 24)
                page.draw_rect(box, width=0.5)
                page.insert_text((box.x0 + 4, box.y1 - 8), cell, fontsize=10)
    return _bytes(document)


def _bytes(document: pymupdf.Document) -> bytes:
    data: bytes = document.tobytes()
    document.close()
    return data


BUILDERS: dict[str, Callable[[], bytes]] = {
    "allianz_auto": allianz_auto,
    "porto_residencial": porto_residencial,
    "bradesco_tabela_auto": bradesco_tabela_auto,
}
