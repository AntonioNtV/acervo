from datetime import datetime
from html.parser import HTMLParser
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from acervo.core.settings import Settings
from acervo.schemas.account import Language
from acervo.services.mail_templates import render
from acervo.services.mailer import MailTemplate
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
}


@pytest.mark.parametrize("language", ["pt-BR", "en"])
@pytest.mark.parametrize("template", list(MailTemplate))
def test_every_template_renders_with_no_missing_value(template: MailTemplate, language: Language) -> None:
    mail = render(template, language, "antonio@segura.com.br", VALUES, "https://acervo.app/", NOW)

    for part in (mail.subject, mail.text, mail.html):
        assert "{" not in part
        assert "}" not in part
    assert "<img" not in mail.html
    if template is MailTemplate.RESET_LINK:
        assert "https://acervo.app/redefinir-senha/tok3n" in mail.text
    if template is MailTemplate.EMAIL_CHANGED:
        assert ("26 de outubro, às 14:02" if language == "pt-BR" else "October 26 at 2:02 PM") in mail.text


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
