import pytest

from acervo.pipeline.link_preview import PageMeta, is_public, parse

PAGE = "https://example.com/blog/post"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (
            '<head><title>Ignored</title><meta property="og:title" content="Apólice 2026">'
            '<meta property="og:description" content="Tudo sobre a apólice">'
            '<meta property="og:image" content="https://cdn.example.com/a.png"></head>',
            PageMeta("Apólice 2026", "Tudo sobre a apólice", "https://cdn.example.com/a.png"),
        ),
        ("<title>\n  Só o   título </title>", PageMeta("Só o título", None, None)),
        (
            '<meta name="description" content="Resumo"><meta property="og:image" content="/img/capa.jpg">',
            PageMeta(None, "Resumo", "https://example.com/img/capa.jpg"),
        ),
        ('<meta property="og:image" content="javascript:alert(1)">', PageMeta(None, None, None)),
        ('<meta property="og:image" content="data:image/png;base64,AAAA">', PageMeta(None, None, None)),
        ("<p>nada aqui</p>", PageMeta(None, None, None)),
    ],
)
def test_parse(html: str, expected: PageMeta) -> None:
    assert parse(html, PAGE) == expected


@pytest.mark.parametrize(
    ("address", "public"),
    [
        ("93.184.215.14", True),
        ("2606:4700::6810:84e5", True),
        ("127.0.0.1", False),
        ("10.0.0.1", False),
        ("172.16.0.1", False),
        ("192.168.1.1", False),
        ("169.254.169.254", False),
        ("100.64.0.1", False),
        ("0.0.0.0", False),
        ("224.0.0.1", False),
        ("240.0.0.1", False),
        ("::1", False),
        ("fe80::1", False),
        ("fc00::1", False),
        ("ff02::1", False),
        ("::ffff:127.0.0.1", False),
    ],
)
def test_is_public(address: str, public: bool) -> None:
    assert is_public(address) is public
