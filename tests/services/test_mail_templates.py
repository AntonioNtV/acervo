from datetime import datetime
from html import escape
from html.parser import HTMLParser
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic import SecretStr

from acervo.core import signing
from acervo.core.settings import Settings
from acervo.schemas.account import Language
from acervo.schemas.notification import Notification
from acervo.services.mail_templates import RenderedMail, render
from acervo.services.mailer import MailTemplate, Unsubscribe
from acervo.services.smtp_mailer import SAO_PAULO, SmtpMailer

NOW = datetime(2026, 10, 26, 14, 2, tzinfo=SAO_PAULO)
VALUES = {
    "code": "482913",
    "link": "tok3n",
    "name": "Antonio Bertino",
    "new_email": "antonio.b@segura.com.br",
    "inviter": "Marina Costa",
    "actor": "Antonio Bertino",
    "organization": "Seguros SA",
    "base": "Sinistros",
    "member_email": "julia@corretora.com",
    # A role of the organization and of a base, so one set of values fills every template.
    "role": "admin",
    "old_role": "member",
    "bases": "Seguros · Operação\nSinistros\nJurídico",
    "expires_at": "2026-11-02T14:02:00-03:00",
    "browser": "Chrome",
    "system": "macOS",
    "method": "passkey",
    "change": "passkey_added",
    "passkey": "1Password",
}
# Where a template reads a value differently: `bases` is a count for the deletion emails.
OVERRIDES: dict[MailTemplate, dict[str, str]] = {
    MailTemplate.DIGEST: {
        "count": "3",
        "pages": "Renovação\tMarina Costa\tSeguros · Operação\n"
        "Emissão de apólice\tRafael Nunes\tSeguros · Operação\n"
        "Glossário\tVocê e Marina Costa\tJurídico",
    },
    MailTemplate.ACCOUNT_DELETED: {"bases": "2"},
    MailTemplate.ORG_DELETED: {"bases": "4"},
}


def _render(template: MailTemplate, language: Language = "pt-BR", **kwargs: Any) -> RenderedMail:
    values = VALUES | OVERRIDES.get(template, {})
    return render(template, language, "antonio@segura.com.br", values, "https://acervo.app/", NOW, **kwargs)


@pytest.mark.parametrize("language", ["pt-BR", "en"])
@pytest.mark.parametrize("template", list(MailTemplate))
def test_every_template_renders_with_no_missing_value(template: MailTemplate, language: Language) -> None:
    mail = _render(template, language)

    for part in (mail.subject, mail.text, mail.html):
        assert "{" not in part
        assert "}" not in part
    assert "<img" not in mail.html
    if template is MailTemplate.RESET_LINK:
        assert "https://acervo.app/redefinir-senha/tok3n" in mail.text
    if template is MailTemplate.EMAIL_CHANGED:
        assert ("26 de outubro, às 14:02" if language == "pt-BR" else "October 26 at 2:02 PM") in mail.text


@pytest.mark.parametrize(
    ("template", "subject", "pre", "lines"),
    [
        (
            MailTemplate.DIGEST,
            "3 páginas que você segue mudaram",
            "Renovação, Emissão de apólice e Glossário.",
            [
                "3 páginas mudaram ontem",
                "Renovação: Marina Costa · Seguros · Operação",
                "Glossário: Você e Marina Costa · Jurídico",
                "Abrir o Acervo: https://acervo.app/",
            ],
        ),
        (
            MailTemplate.ACCOUNT_DELETED,
            "Sua conta do Acervo foi excluída",
            "Esta é a última mensagem.",
            [
                "Sua conta foi excluída",
                "Excluímos sua conta, seu espaço Pessoal e as 2 bases dele, como você pediu em 26 de outubro.",
                'O que você escreveu em bases de outras pessoas ficou lá, com o autor "Conta excluída".',
                "Esta é a última mensagem que enviamos para este email.",
            ],
        ),
        (
            MailTemplate.ORG_DELETED,
            "A Seguros SA foi excluída",
            "As 4 bases dela saíram do Acervo.",
            [
                "A Seguros SA foi excluída",
                "Antonio Bertino excluiu a organização Seguros SA e as 4 bases dela em 26 de outubro.",
                "Seu espaço Pessoal e as outras organizações não mudam.",
            ],
        ),
    ],
)
def test_new_emails_say_what_the_design_says(template: MailTemplate, subject: str, pre: str, lines: list[str]) -> None:
    mail = _render(template)

    assert mail.subject == subject
    assert escape(pre, quote=False) in mail.html
    assert all(line in mail.text.split("\n") for line in lines)


def test_footer_links_to_unsubscribe_only_when_given_a_link() -> None:
    link = "https://acervo.app/descadastro/t0k"

    turned_off = _render(MailTemplate.ROLE_CHANGED, unsubscribe_link=link)
    always = _render(MailTemplate.ROLE_CHANGED)

    why = 'Você recebe porque "Convites e acessos" está ligado em Notificações.'
    assert why in turned_off.text
    assert f"Parar de receber: {link}" in turned_off.text
    assert escape(why) in turned_off.html
    assert f'<a href="{link}"' in turned_off.html
    assert "Emails da sua conta, como este, não se desligam." in always.text
    assert "descadastro" not in always.text + always.html
    assert "Mudanças nas páginas que você segue" in _render(MailTemplate.DIGEST, "pt-BR", unsubscribe_link=link).text


class _Styles(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.styles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.styles += [value or "" for name, value in attrs if name == "style"]


def test_every_style_keeps_its_whole_font_stack() -> None:
    # A double quote inside style="..." ends the attribute early, and clients fall back to a serif font.
    mail = render(MailTemplate.RESET_LINK, "pt-BR", "antonio@segura.com.br", VALUES, "https://acervo.app/", NOW)
    parser = _Styles()
    parser.feed(mail.html)

    fonts = [style for style in parser.styles if "font-family" in style or "font:" in style]
    assert fonts
    assert all("sans-serif" in style or "monospace" in style for style in fonts)


async def test_sends_one_message_with_to_from_and_subject() -> None:
    settings = Settings(session_secret=SecretStr("s"), smtp_host="mail.test", mail_from="Acervo <acervo@test>")

    with patch("smtplib.SMTP") as smtp:
        await SmtpMailer(settings, lambda: NOW).send("ana@test.com", MailTemplate.VERIFY_CODE, "en", VALUES)

    client = smtp.return_value.__enter__.return_value
    client.send_message.assert_called_once()
    client.starttls.assert_not_called()
    client.login.assert_not_called()
    message = client.send_message.call_args.args[0]
    assert message["To"] == "ana@test.com"
    assert message["From"] == "Acervo <acervo@test>"
    assert message["Subject"] == "482913 is your Acervo code"
    assert message["List-Unsubscribe"] is None
    assert message["List-Unsubscribe-Post"] is None


async def test_an_email_that_can_be_turned_off_carries_the_one_click_headers() -> None:
    settings = Settings(session_secret=SecretStr("s"), smtp_host="mail.test", public_url="https://acervo.app/")
    account_id = uuid4()

    with patch("smtplib.SMTP") as smtp:
        await SmtpMailer(settings, lambda: NOW).send(
            "ana@test.com",
            MailTemplate.ROLE_CHANGED,
            "pt-BR",
            VALUES,
            unsubscribe=Unsubscribe(account_id, Notification.INVITES),
        )

    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    token = message["List-Unsubscribe"].removeprefix("<https://acervo.app/v1/auth/unsubscribe/").removesuffix(">")
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert f"https://acervo.app/descadastro/{token}" in message.get_body(("plain",)).get_content()
    sealed = signing.unseal("s", "unsubscribe", token, datetime(9000, 1, 1).timestamp())
    assert sealed is not None
    assert (sealed["account"], sealed["notification"]) == (str(account_id), "invites")
