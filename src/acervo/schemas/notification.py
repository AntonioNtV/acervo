from enum import StrEnum


class Notification(StrEnum):
    """An email toggle in Conta › Notificações."""

    INVITES = "invites"
    FOLLOWED = "followed"
