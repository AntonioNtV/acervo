from dataclasses import dataclass, field
from typing import Protocol

import httpx

GRAPH_URL = "https://graph.facebook.com/v21.0"


class WhatsAppSender(Protocol):
    async def send_code(self, phone: str, code: str, language: str) -> None:
        """Sends `code` to `phone` (E.164) with the authentication template in `language`, Meta's code of the
        template's language (`pt_BR`)."""
        ...


class CloudApiSender:
    """Meta's WhatsApp Cloud API: the authentication template, its body and its Copiar código button carry the code."""

    def __init__(self, token: str, phone_number_id: str, template: str) -> None:
        self._token = token
        self._url = f"{GRAPH_URL}/{phone_number_id}/messages"
        self._template = template

    async def send_code(self, phone: str, code: str, language: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": self._template,
                "language": {"code": language},
                "components": [
                    {"type": "body", "parameters": [{"type": "text", "text": code}]},
                    {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": code}]},
                ],
            },
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(self._url, json=payload, headers={"Authorization": f"Bearer {self._token}"})
            response.raise_for_status()


@dataclass(frozen=True)
class SentCode:
    phone: str
    code: str
    language: str


@dataclass
class FakeWhatsApp:
    """Keeps what it would send, for the tests and for running without a Meta account."""

    sent: list[SentCode] = field(default_factory=list)

    async def send_code(self, phone: str, code: str, language: str) -> None:
        self.sent.append(SentCode(phone, code, language))
