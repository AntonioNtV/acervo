import asyncio
import smtplib
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from acervo.core import signing
from acervo.core.settings import Settings
from acervo.schemas.account import Language
from acervo.services.mail_templates import render
from acervo.services.mailer import MailTemplate, Unsubscribe

# Accounts have no time zone yet; the "email changed" notice says when in Brazil's.
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
# An unsubscribe link never expires.
UNSUBSCRIBE_EXPIRES = int(datetime(9999, 12, 31, tzinfo=UTC).timestamp())


def _now() -> datetime:
    return datetime.now(SAO_PAULO)


class SmtpMailer:
    """Sends the account emails through the SMTP server in the settings."""

    def __init__(self, settings: Settings, now: Callable[[], datetime] = _now) -> None:
        self._settings = settings
        self._now = now

    async def send(
        self,
        to: str,
        template: MailTemplate,
        language: Language,
        values: Mapping[str, str],
        *,
        unsubscribe: Unsubscribe | None = None,
    ) -> None:
        public_url = self._settings.public_url.rstrip("/")
        token = (
            signing.seal(
                self._settings.session_secret.get_secret_value(),
                "unsubscribe",
                UNSUBSCRIBE_EXPIRES,
                account=str(unsubscribe.account_id),
                notification=unsubscribe.notification,
            )
            if unsubscribe
            else None
        )
        link = f"{public_url}/descadastro/{token}" if token else None
        mail = render(template, language, to, values, self._settings.public_url, self._now(), link)
        # Lines up to RFC 5322's 998: the one-click URL is longer than 78, and folding would MIME-encode it, which
        # mail providers do not read as a List-Unsubscribe URL.
        message = EmailMessage(policy=policy.SMTP.clone(max_line_length=998))
        message["From"] = self._settings.mail_from
        message["To"] = to
        message["Subject"] = mail.subject
        if token:
            # Through the web app's /v1 proxy, like every other call the app makes to the API.
            message["List-Unsubscribe"] = f"<{public_url}/v1/auth/unsubscribe/{token}>"
            message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
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
