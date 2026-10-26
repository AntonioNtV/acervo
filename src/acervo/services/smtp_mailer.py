import asyncio
import smtplib
from collections.abc import Callable, Mapping
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from acervo.core.settings import Settings
from acervo.schemas.account import Language
from acervo.services.mail_templates import render
from acervo.services.mailer import MailTemplate

# Accounts have no time zone yet; the "email changed" notice says when in Brazil's.
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def _now() -> datetime:
    return datetime.now(SAO_PAULO)


class SmtpMailer:
    """Sends the account emails through the SMTP server in the settings."""

    def __init__(self, settings: Settings, now: Callable[[], datetime] = _now) -> None:
        self._settings = settings
        self._now = now

    async def send(self, to: str, template: MailTemplate, language: Language, values: Mapping[str, str]) -> None:
        mail = render(template, language, to, values, self._settings.public_url, self._now())
        message = EmailMessage()
        message["From"] = self._settings.mail_from
        message["To"] = to
        message["Subject"] = mail.subject
        message.set_content(mail.text)
        message.add_alternative(mail.html, subtype="html")
        await asyncio.to_thread(self._deliver, message)

    def _deliver(self, message: EmailMessage) -> None:
        s = self._settings
        with smtplib.SMTP(s.smtp_host or "", s.smtp_port, timeout=30) as smtp:
            if s.smtp_tls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password.get_secret_value() if s.smtp_password else "")
            smtp.send_message(message)
