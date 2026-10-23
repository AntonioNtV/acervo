from acervo.core.settings import RetrievalLimits
from acervo.domain.sections import sections
from acervo.pipeline.index.markdown import index_markdown

PAGE = """# Emissão de apólice

Guia da corretora.

## Prazos
- Emissão leva 3 dias úteis

```
## não é um título
```

## Prazos

| Seguradora | Dias |
| --- | --- |
| Bradesco | 3 |

## ✅
Feito.
"""


def test_markdown_sections_use_the_anchors_of_the_page_view() -> None:
    index = index_markdown(PAGE, RetrievalLimits())

    assert [section.id for section in index.sections] == ["", *(found.anchor for found in sections(PAGE))]
    assert [section.id for section in index.sections] == ["", "prazos", "prazos-2", "secao"]
    assert [section.title for section in index.sections] == ["Emissão de apólice", "Prazos", "Prazos", "✅"]
    kinds = {block.id: block.kind for block in index.blocks}
    assert [kinds[block_id] for block_id in index.sections[1].block_ids] == ["heading", "list", "paragraph"]
    assert [kinds[block_id] for block_id in index.sections[2].block_ids] == ["heading", "table"]
    assert all(block.page is None for block in index.blocks)
