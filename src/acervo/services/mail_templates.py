from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import NotRequired, TypedDict

from acervo.schemas.account import Language
from acervo.schemas.notification import Notification
from acervo.services.mailer import MailTemplate


class Copy(TypedDict):
    subject: str
    pre: str
    title: str
    body: list[str]
    button: NotRequired[str]
    # Label and value rows under the body, such as the device and when.
    details: NotRequired[list[tuple[str, str]]]
    after: list[str]


# Copy from the Design System, "Emails · Contas". `{first}` is the first word of `name`, `{email}` the recipient.
COPY: dict[MailTemplate, dict[Language, Copy]] = {
    MailTemplate.VERIFY_CODE: {
        "pt-BR": {
            "subject": "{code} é seu código do Acervo",
            "pre": "Confirme seu email para começar.",
            "title": "Confirme seu email",
            "body": ["Olá, {first}. Use este código para confirmar seu email e entrar no Acervo:"],
            "after": [
                "O código vale por 10 minutos.",
                "Se não foi você que criou a conta, ignore este email: sem a confirmação, ela é apagada em 7 dias.",
            ],
        },
        "en": {
            "subject": "{code} is your Acervo code",
            "pre": "Confirm your email to get started.",
            "title": "Confirm your email",
            "body": ["Hi, {first}. Use this code to confirm your email and sign in to Acervo:"],
            "after": [
                "The code is valid for 10 minutes.",
                "If you did not create this account, ignore this email: without confirmation it is deleted in 7 days.",
            ],
        },
    },
    MailTemplate.RESET_LINK: {
        "pt-BR": {
            "subject": "Redefinir sua senha do Acervo",
            "pre": "O link vale por 1 hora.",
            "title": "Redefinir senha",
            "body": ["Recebemos um pedido para redefinir a senha da conta {email}."],
            "button": "Criar uma senha nova",
            "after": [
                "O link vale por 1 hora e funciona uma vez. Ao salvar a senha nova, saímos de todas as outras sessões.",
                "Se não foi você, ignore este email: sua senha continua a mesma.",
            ],
        },
        "en": {
            "subject": "Reset your Acervo password",
            "pre": "The link is valid for 1 hour.",
            "title": "Reset password",
            "body": ["We received a request to reset the password of {email}."],
            "button": "Create a new password",
            "after": [
                "The link is valid for 1 hour and works once. Saving the new password signs out every other session.",
                "If it was not you, ignore this email: your password stays the same.",
            ],
        },
    },
    MailTemplate.CHANGE_EMAIL_CODE: {
        "pt-BR": {
            "subject": "{code} confirma seu novo email no Acervo",
            "pre": "Digite o código no Acervo.",
            "title": "Confirme o novo email",
            "body": [
                "{first}, você pediu para trocar o email da sua conta para {new_email}. Digite este código no Acervo:"
            ],
            "after": ["O código vale por 10 minutos. Se não foi você, ignore: nada muda."],
        },
        "en": {
            "subject": "{code} confirms your new Acervo email",
            "pre": "Type the code in Acervo.",
            "title": "Confirm your new email",
            "body": ["{first}, you asked to change your account email to {new_email}. Type this code in Acervo:"],
            "after": ["The code is valid for 10 minutes. If it was not you, ignore it: nothing changes."],
        },
    },
    MailTemplate.EMAIL_CHANGED: {
        "pt-BR": {
            "subject": "O email da sua conta do Acervo mudou",
            "pre": "Agora os emails vão para o endereço novo.",
            "title": "Seu email mudou",
            "body": [
                "O email da sua conta mudou de {email} para {new_email} em {date}, às {time}.",
                "A partir de agora, os emails do Acervo vão para o endereço novo.",
            ],
            "after": ["Se não foi você, redefina a senha pelo email novo ou peça ajuda ao admin da sua organização."],
        },
        "en": {
            "subject": "Your Acervo account email changed",
            "pre": "Emails now go to the new address.",
            "title": "Your email changed",
            "body": [
                "Your account email changed from {email} to {new_email} on {date} at {time}.",
                "From now on, Acervo emails go to the new address.",
            ],
            "after": [
                "If it was not you, reset the password from the new email or ask your organization's admin for help."
            ],
        },
    },
    # Copy from the Design System, "Comunicação · Organizações"; the English is ours, the design has none yet.
    MailTemplate.ORG_INVITE: {
        "pt-BR": {
            "subject": "{inviter} convidou você para a {organization}",
            "pre": "Você vai entrar como {role}.",
            "title": "{inviter} convidou você para a {organization}",
            "body": ["Você vai entrar como {role} e terá acesso a {bases}."],
            "button": "Aceitar convite",
            "after": [
                "O convite é para {email} e vale até {until}. Se você não conhece a {organization}, ignore este email."
            ],
        },
        "en": {
            "subject": "{inviter} invited you to {organization}",
            "pre": "You will join as {role}.",
            "title": "{inviter} invited you to {organization}",
            "body": ["You will join as {role} and have access to {bases}."],
            "button": "Accept invite",
            "after": [
                "The invite is for {email} and is valid until {until}. If you do not know {organization}, "
                "ignore this email."
            ],
        },
    },
    MailTemplate.INVITE_ACCEPTED: {
        "pt-BR": {
            "subject": "{first} entrou na {organization}",
            "pre": "Já pode acessar as bases da organização.",
            "title": "{first} entrou na {organization}",
            "body": ["{member_email} aceitou seu convite e entrou como {role}."],
            "button": "Ver membros",
            "after": [],
        },
        "en": {
            "subject": "{first} joined {organization}",
            "pre": "They can already reach the organization's bases.",
            "title": "{first} joined {organization}",
            "body": ["{member_email} accepted your invite and joined as {role}."],
            "button": "See members",
            "after": [],
        },
    },
    MailTemplate.BASE_SHARED: {
        "pt-BR": {
            "subject": "{inviter} compartilhou {base} com você",
            "pre": "{can_pre}",
            "title": "{inviter} compartilhou {base} com você",
            "body": ["Você entrou como {role}: {can}"],
            "button": "Abrir {base}",
            "after": [],
        },
        "en": {
            "subject": "{inviter} shared {base} with you",
            "pre": "{can_pre}",
            "title": "{inviter} shared {base} with you",
            "body": ["You joined as {role}: {can}"],
            "button": "Open {base}",
            "after": [],
        },
    },
    MailTemplate.ROLE_CHANGED: {
        "pt-BR": {
            "subject": "Agora você é {role} na {organization}",
            "pre": "{actor} mudou seu papel.",
            "title": "Agora você é {role} na {organization}",
            "body": ["{actor} mudou seu papel de {old_role} para {role}. {can}"],
            "button": "Abrir a {organization}",
            "after": [],
        },
        "en": {
            "subject": "You are now {role} at {organization}",
            "pre": "{actor} changed your role.",
            "title": "You are now {role} at {organization}",
            "body": ["{actor} changed your role from {old_role} to {role}. {can}"],
            "button": "Open {organization}",
            "after": [],
        },
    },
    MailTemplate.REMOVED: {
        "pt-BR": {
            "subject": "Você não faz mais parte da {organization}",
            "pre": "Suas bases pessoais continuam com você.",
            "title": "Você saiu da {organization}",
            "body": [
                "{actor} tirou seu acesso à {organization}. As páginas que você escreveu lá continuam na organização.",
                "Seu espaço Pessoal e as outras organizações não mudam.",
            ],
            "after": [],
        },
        "en": {
            "subject": "You are no longer part of {organization}",
            "pre": "Your personal bases stay with you.",
            "title": "You left {organization}",
            "body": [
                "{actor} removed your access to {organization}. The pages you wrote there stay in the organization.",
                "Your Personal space and your other organizations do not change.",
            ],
            "after": [],
        },
    },
}

# Copy from the Design System, "Comunicação · Segurança"; the English is ours. No location: there is no GeoIP.
WHEN = {"pt-BR": ("Quando", "{date}, {time}"), "en": ("When", "{date}, {time}")}
DEVICE = {"pt-BR": ("Aparelho", "{device}"), "en": ("Device", "{device}")}
COPY |= {
    MailTemplate.LOGIN_CODE: {
        "pt-BR": {
            "subject": "{code} é seu código para entrar no Acervo",
            "pre": "Alguém está entrando com a sua senha.",
            "title": "Seu código para entrar",
            "body": [
                "Alguém, provavelmente você, está entrando na sua conta com a senha certa. Para terminar, use este "
                "código:"
            ],
            "details": [DEVICE["pt-BR"], WHEN["pt-BR"]],
            "after": ["Se não foi você, troque a senha agora: ela já foi usada."],
        },
        "en": {
            "subject": "{code} is your code to sign in to Acervo",
            "pre": "Someone is signing in with your password.",
            "title": "Your sign-in code",
            "body": [
                "Someone, probably you, is signing in to your account with the right password. To finish, use "
                "this code:"
            ],
            "details": [DEVICE["en"], WHEN["en"]],
            "after": ["If it was not you, change your password now: it has already been used."],
        },
    },
    MailTemplate.NEW_SIGN_IN: {
        "pt-BR": {
            "subject": "Nova entrada na sua conta do Acervo",
            "pre": "{device}.",
            "title": "Nova entrada na sua conta",
            "body": ["Sua conta foi aberta num aparelho novo, {with_method}."],
            "details": [DEVICE["pt-BR"], WHEN["pt-BR"]],
            "button": "Ver sessões",
            "after": ["Se não foi você, encerre essa sessão e troque a senha."],
        },
        "en": {
            "subject": "New sign-in to your Acervo account",
            "pre": "{device}.",
            "title": "New sign-in to your account",
            "body": ["Your account was opened on a new device, {with_method}."],
            "details": [DEVICE["en"], WHEN["en"]],
            "button": "See sessions",
            "after": ["If it was not you, end that session and change your password."],
        },
    },
    MailTemplate.SECURITY_CHANGE: {
        "pt-BR": {
            "subject": "{change_subject}",
            "pre": "{change_pre}",
            "title": "{change_title}",
            "body": ["{change_body}"],
            "details": [DEVICE["pt-BR"], WHEN["pt-BR"]],
            "button": "Ver segurança",
            "after": [
                "O mesmo email avisa quando a senha muda, uma passkey sai, o 2FA é desligado ou o Google é vinculado.",
                "{change_if_not}",
            ],
        },
        "en": {
            "subject": "{change_subject}",
            "pre": "{change_pre}",
            "title": "{change_title}",
            "body": ["{change_body}"],
            "details": [DEVICE["en"], WHEN["en"]],
            "button": "See security",
            "after": [
                "The same email tells you when the password changes, a passkey is removed, two-step verification is "
                "turned off or Google is linked.",
                "{change_if_not}",
            ],
        },
    },
    MailTemplate.LOCKOUT: {
        "pt-BR": {
            "subject": "Bloqueamos as entradas na sua conta por 15 minutos",
            "pre": "Houve 5 senhas erradas.",
            "title": "Entradas bloqueadas por 15 minutos",
            "body": [
                "Alguém errou a senha da sua conta 5 vezes seguidas. Por segurança, ninguém entra com senha pelos "
                "próximos 15 minutos."
            ],
            "details": [("Última tentativa", "{device}"), WHEN["pt-BR"]],
            "button": "Redefinir senha",
            "after": ["Se foi você, espere ou redefina a senha. A passkey continua funcionando."],
        },
        "en": {
            "subject": "We blocked sign-ins to your account for 15 minutes",
            "pre": "There were 5 wrong passwords.",
            "title": "Sign-ins blocked for 15 minutes",
            "body": [
                "Someone got your account's password wrong 5 times in a row. For safety, no one signs in with a "
                "password for the next 15 minutes."
            ],
            "details": [("Last attempt", "{device}"), WHEN["en"]],
            "button": "Reset password",
            "after": ["If it was you, wait or reset your password. Your passkey still works."],
        },
    },
    MailTemplate.ORG_REQUIRES_2FA: {
        "pt-BR": {
            "subject": "A {organization} agora exige verificação em duas etapas",
            "pre": "Ative no seu próximo acesso.",
            "title": "A {organization} agora exige verificação em duas etapas",
            "body": [
                "{actor} ligou essa exigência. No seu próximo acesso às bases da {organization}, o Acervo vai pedir "
                "para você ativar uma passkey, um código por WhatsApp ou por email."
            ],
            "button": "Ativar agora",
            "after": ["Seu espaço Pessoal e as outras organizações não mudam."],
        },
        "en": {
            "subject": "{organization} now requires two-step verification",
            "pre": "Turn it on at your next visit.",
            "title": "{organization} now requires two-step verification",
            "body": [
                "{actor} turned this requirement on. The next time you open {organization}'s bases, Acervo will ask "
                "you to set up a passkey, or a code by WhatsApp or email."
            ],
            "button": "Turn on now",
            "after": ["Your Personal space and your other organizations do not change."],
        },
    },
}
# Copy from the Design System, "Comunicação · Notificações e exclusão"; the English is ours.
COPY |= {
    MailTemplate.DIGEST: {
        "pt-BR": {
            "subject": "{pages} que você segue {changed}",
            "pre": "{titles}.",
            "title": "{pages} {changed} ontem",
            "body": [],
            "button": "Abrir o Acervo",
            "after": [],
        },
        "en": {
            "subject": "{pages} you follow changed",
            "pre": "{titles}.",
            "title": "{pages} changed yesterday",
            "body": [],
            "button": "Open Acervo",
            "after": [],
        },
    },
    MailTemplate.ACCOUNT_DELETED: {
        "pt-BR": {
            "subject": "Sua conta do Acervo foi excluída",
            "pre": "Esta é a última mensagem.",
            "title": "Sua conta foi excluída",
            "body": [
                "Excluímos sua conta, seu espaço Pessoal e {bases} dele, como você pediu em {date}.",
                'O que você escreveu em bases de outras pessoas ficou lá, com o autor "Conta excluída".',
            ],
            "after": ["Esta é a última mensagem que enviamos para este email."],
        },
        "en": {
            "subject": "Your Acervo account was deleted",
            "pre": "This is the last message.",
            "title": "Your account was deleted",
            "body": [
                "We deleted your account, your Personal space and {bases}, as you asked on {date}.",
                'What you wrote in other people\'s bases stays there, with the author "Deleted account".',
            ],
            "after": ["This is the last message we send to this email."],
        },
    },
    MailTemplate.ORG_DELETED: {
        "pt-BR": {
            "subject": "A {organization} foi excluída",
            "pre": "{bases_left} do Acervo.",
            "title": "A {organization} foi excluída",
            "body": [
                "{actor} excluiu a organização {organization} e {bases} dela em {date}.",
                "Seu espaço Pessoal e as outras organizações não mudam.",
            ],
            "after": [],
        },
        "en": {
            "subject": "{organization} was deleted",
            "pre": "{bases_left} Acervo.",
            "title": "{organization} was deleted",
            "body": [
                "{actor} deleted the organization {organization} and {bases} on {date}.",
                "Your Personal space and your other organizations do not change.",
            ],
            "after": [],
        },
    },
}
# The words after a count (`count` for `digest`, `bases` for the others), by template, language and one or many.
PLURAL: dict[MailTemplate, dict[Language, dict[bool, dict[str, str]]]] = {
    MailTemplate.DIGEST: {
        "pt-BR": {
            False: {"pages": "1 página", "changed": "mudou"},
            True: {"pages": "{n} páginas", "changed": "mudaram"},
        },
        "en": {False: {"pages": "1 page"}, True: {"pages": "{n} pages"}},
    },
    MailTemplate.ACCOUNT_DELETED: {
        "pt-BR": {False: {"bases": "a base"}, True: {"bases": "as {n} bases"}},
        "en": {False: {"bases": "its base"}, True: {"bases": "its {n} bases"}},
    },
    MailTemplate.ORG_DELETED: {
        "pt-BR": {
            False: {"bases": "a base", "bases_left": "A base dela saiu"},
            True: {"bases": "as {n} bases", "bases_left": "As {n} bases dela saíram"},
        },
        "en": {
            False: {"bases": "its base", "bases_left": "Its base left"},
            True: {"bases": "its {n} bases", "bases_left": "Its {n} bases left"},
        },
    },
}
# `new_sign_in` by `method`; the design only words a passkey one.
METHODS: dict[Language, dict[str, str]] = {
    "pt-BR": {
        "password": "com senha",
        "google": "com Google",
        "passkey": "com passkey",
        "reset": "por um link de senha",
    },
    "en": {
        "password": "with a password",
        "google": "with Google",
        "passkey": "with a passkey",
        "reset": "through a password link",
    },
}
# `security_change` by `change`; the design words `passkey_added`, the others follow it.
CHANGES: dict[Language, dict[str, dict[str, str]]] = {
    "pt-BR": {
        "password_changed": {
            "subject": "A senha da sua conta do Acervo mudou",
            "pre": "No {device}.",
            "title": "Sua senha mudou",
            "body": "A senha da sua conta foi trocada.",
            "if_not": "Se não foi você, redefina a senha agora.",
        },
        "passkey_added": {
            "subject": "Uma passkey foi adicionada à sua conta",
            "pre": "{passkey}, no {device}.",
            "title": "Uma passkey foi adicionada",
            "body": "A passkey {passkey} foi adicionada à sua conta.",
            "if_not": "Se não foi você, troque a senha e remova a passkey.",
        },
        "passkey_removed": {
            "subject": "Uma passkey foi removida da sua conta",
            "pre": "{passkey}, no {device}.",
            "title": "Uma passkey foi removida",
            "body": "A passkey {passkey} foi removida da sua conta.",
            "if_not": "Se não foi você, troque a senha agora.",
        },
        "two_factor_on": {
            "subject": "A verificação em duas etapas foi ativada na sua conta",
            "pre": "No {device}.",
            "title": "Verificação em duas etapas ativada",
            "body": "A partir de agora, entrar com a senha também pede um código.",
            "if_not": "Se não foi você, troque a senha agora.",
        },
        "two_factor_off": {
            "subject": "A verificação em duas etapas foi desligada na sua conta",
            "pre": "No {device}.",
            "title": "Verificação em duas etapas desligada",
            "body": "A partir de agora, a senha basta para entrar na sua conta.",
            "if_not": "Se não foi você, troque a senha e ative a verificação de novo.",
        },
        "google_linked": {
            "subject": "Uma conta Google foi vinculada à sua conta",
            "pre": "No {device}.",
            "title": "Google vinculado",
            "body": "Agora sua conta também entra com o Google.",
            "if_not": "Se não foi você, troque a senha e desvincule o Google.",
        },
        "google_unlinked": {
            "subject": "O Google foi desvinculado da sua conta",
            "pre": "No {device}.",
            "title": "Google desvinculado",
            "body": "Sua conta não entra mais com o Google.",
            "if_not": "Se não foi você, troque a senha agora.",
        },
    },
    "en": {
        "password_changed": {
            "subject": "Your Acervo account password changed",
            "pre": "On {device}.",
            "title": "Your password changed",
            "body": "Your account's password was changed.",
            "if_not": "If it was not you, reset your password now.",
        },
        "passkey_added": {
            "subject": "A passkey was added to your account",
            "pre": "{passkey}, on {device}.",
            "title": "A passkey was added",
            "body": "The passkey {passkey} was added to your account.",
            "if_not": "If it was not you, change your password and remove the passkey.",
        },
        "passkey_removed": {
            "subject": "A passkey was removed from your account",
            "pre": "{passkey}, on {device}.",
            "title": "A passkey was removed",
            "body": "The passkey {passkey} was removed from your account.",
            "if_not": "If it was not you, change your password now.",
        },
        "two_factor_on": {
            "subject": "Two-step verification was turned on for your account",
            "pre": "On {device}.",
            "title": "Two-step verification on",
            "body": "From now on, signing in with the password also asks for a code.",
            "if_not": "If it was not you, change your password now.",
        },
        "two_factor_off": {
            "subject": "Two-step verification was turned off for your account",
            "pre": "On {device}.",
            "title": "Two-step verification off",
            "body": "From now on, the password alone signs in to your account.",
            "if_not": "If it was not you, change your password and turn verification on again.",
        },
        "google_linked": {
            "subject": "A Google account was linked to your account",
            "pre": "On {device}.",
            "title": "Google linked",
            "body": "Your account now also signs in with Google.",
            "if_not": "If it was not you, change your password and unlink Google.",
        },
        "google_unlinked": {
            "subject": "Google was unlinked from your account",
            "pre": "On {device}.",
            "title": "Google unlinked",
            "body": "Your account no longer signs in with Google.",
            "if_not": "If it was not you, change your password now.",
        },
    },
}

ROLES: dict[Language, dict[str, str]] = {
    "pt-BR": {"owner": "Owner", "admin": "Admin", "member": "Membro", "reader": "Leitor", "editor": "Editor"},
    "en": {"owner": "Owner", "admin": "Admin", "member": "Member", "reader": "Reader", "editor": "Editor"},
}
# What the new role allows, by role code: organization roles for `role_changed`, base roles for `base_shared`.
CAN: dict[MailTemplate, dict[Language, dict[str, dict[str, str]]]] = {
    MailTemplate.ROLE_CHANGED: {
        "pt-BR": {
            "owner": {"can": "Agora você pode fazer tudo o que um Admin faz e também gerenciar os Owners."},
            "admin": {"can": "Agora você pode convidar pessoas, criar bases e ver todas as bases da organização."},
            "member": {"can": "Agora você vê as bases que seu acesso permite e pode criar bases."},
        },
        "en": {
            "owner": {"can": "Now you can do everything an Admin does and also manage Owners."},
            "admin": {"can": "Now you can invite people, create bases and see every base of the organization."},
            "member": {"can": "Now you see the bases your access allows and can create bases."},
        },
    },
    MailTemplate.BASE_SHARED: {
        "pt-BR": {
            "reader": {
                "can_pre": "Você pode ler.",
                "can": "pode ler as páginas e os arquivos da base, baixá-los e buscar neles.",
            },
            "editor": {
                "can_pre": "Você pode editar.",
                "can": "pode criar, editar, mover e restaurar versões das páginas da base.",
            },
            "admin": {
                "can_pre": "Você pode editar e gerenciar o acesso.",
                "can": "pode editar as páginas da base e gerenciar quem a acessa.",
            },
        },
        "en": {
            "reader": {
                "can_pre": "You can read.",
                "can": "you can read, download and search the base's pages and files.",
            },
            "editor": {
                "can_pre": "You can edit.",
                "can": "you can create, edit, move and restore versions of the base's pages.",
            },
            "admin": {
                "can_pre": "You can edit and manage access.",
                "can": "you can edit the base's pages and manage who accesses it.",
            },
        },
    },
}
AND = {"pt-BR": "e", "en": "and"}
NO_BASES = {"pt-BR": "nenhuma base por enquanto", "en": "no bases yet"}
# Where each button goes; `link` is a token for these, and the app path for any other template with a button.
BUTTON_PATH = {
    MailTemplate.RESET_LINK: "/redefinir-senha/{link}",
    MailTemplate.ORG_INVITE: "/convite/{link}",
    MailTemplate.DIGEST: "/",
}

CODE_TEMPLATES = (MailTemplate.VERIFY_CODE, MailTemplate.CHANGE_EMAIL_CODE, MailTemplate.LOGIN_CODE)

ON = {"pt-BR": "no", "en": "on"}
UNKNOWN_DEVICE = {"pt-BR": "Navegador desconhecido", "en": "Unknown browser"}
OR_OPEN = {"pt-BR": "Ou abra", "en": "Or open"}
FOOTER = {
    "pt-BR": "Emails da sua conta, como este, não se desligam.",
    "en": "Account emails like this one cannot be turned off.",
}
# The emails a toggle in Conta › Notificações turns off, and the toggle's label there.
TOGGLE = {
    MailTemplate.DIGEST: Notification.FOLLOWED,
    MailTemplate.INVITE_ACCEPTED: Notification.INVITES,
    MailTemplate.BASE_SHARED: Notification.INVITES,
    MailTemplate.ROLE_CHANGED: Notification.INVITES,
}
TOGGLE_LABEL = {
    "pt-BR": {Notification.INVITES: "Convites e acessos", Notification.FOLLOWED: "Mudanças nas páginas que você segue"},
    "en": {Notification.INVITES: "Invites and access", Notification.FOLLOWED: "Changes to pages you follow"},
}
WHY = {
    "pt-BR": 'Você recebe porque "{toggle}" está ligado em Notificações.',
    "en": 'You get this because "{toggle}" is on in Notifications.',
}
STOP = {"pt-BR": "Parar de receber", "en": "Unsubscribe"}
MONTHS = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]  # fmt: skip

# Light-theme tokens inlined: email clients ignore CSS variables.
SANS = "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, Menlo, Consolas, 'Courier New', monospace"


@dataclass(frozen=True)
class RenderedMail:
    subject: str
    text: str
    html: str


def _when(now: datetime, language: Language) -> dict[str, str]:
    if language == "en":
        return {"date": f"{now:%B} {now.day}", "time": f"{now.hour % 12 or 12}:{now:%M %p}"}
    return {"date": f"{now.day} de {MONTHS[now.month - 1]}", "time": f"{now:%H:%M}"}


def _join(items: list[str], language: Language) -> str:
    """ "A, B e C"."""
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} {AND[language]} {items[-1]}"


def _bases(names: str, language: Language) -> str:
    """ "3 bases: A, B e C" from one name per line."""
    listed = [name for name in names.split("\n") if name]
    if not listed:
        return NO_BASES[language]
    return f"{len(listed)} base{'s' if len(listed) > 1 else ''}: {_join(listed, language)}"


def _device(browser: str, system: str, language: Language) -> str:
    """ "Chrome no macOS", from what the user agent told."""
    if browser and system:
        return f"{browser} {ON[language]} {system}"
    return browser or system or UNKNOWN_DEVICE[language]


def render(
    template: MailTemplate,
    language: Language,
    to: str,
    values: Mapping[str, str],
    public_url: str,
    now: datetime,
    unsubscribe_link: str | None = None,
) -> RenderedMail:
    """Fills one template; a value the template needs and `values` lacks raises KeyError. With `unsubscribe_link`,
    the footer names the template's toggle and links to turning it off."""
    copy = COPY[template][language]
    fill = {**values, "email": to, "first": values.get("name", "").split(" ")[0], **_when(now, language)}
    for key in ("role", "old_role"):
        if key in values:
            fill[key] = ROLES[language][values[key]]
    if template in CAN:
        fill |= CAN[template][language][values["role"]]
    if template in PLURAL:
        n = values["count" if template is MailTemplate.DIGEST else "bases"]
        fill |= {key: words.format(n=n) for key, words in PLURAL[template][language][n != "1"].items()}
    elif "bases" in values:
        fill["bases"] = _bases(values["bases"], language)
    # One page per line: title, authors and base; the list the digest shows.
    pages = [line.split("\t") for line in values.get("pages", "").split("\n") if line]
    if pages:
        fill["titles"] = _join([title for title, _, _ in pages], language)
    listed = [(title, " · ".join(x for x in (authors, base) if x)) for title, authors, base in pages]
    if "expires_at" in values:
        fill["until"] = _when(datetime.fromisoformat(values["expires_at"]), language)["date"]
    if "browser" in values:
        fill["device"] = _device(values["browser"], values.get("system", ""), language)
    if "method" in values:
        fill["with_method"] = METHODS[language][values["method"]]
    if "change" in values:
        fill |= {f"change_{key}": text.format(**fill) for key, text in CHANGES[language][values["change"]].items()}
    subject, pre, title = (copy["subject"].format(**fill), copy["pre"].format(**fill), copy["title"].format(**fill))
    body = [p.format(**fill) for p in copy["body"]]
    after = [p.format(**fill) for p in copy["after"]]
    code = values["code"] if template in CODE_TEMPLATES else None
    details = [(label, value.format(**fill)) for label, value in copy.get("details", [])]
    button = copy["button"].format(**fill) if "button" in copy else None
    path = BUTTON_PATH.get(template, "{link}").format_map(values) if button else ""
    link = f"{public_url.rstrip('/')}{path}" if button else None
    why = FOOTER[language]
    if unsubscribe_link:
        why = WHY[language].format(toggle=TOGGLE_LABEL[language][TOGGLE[template]])

    text = [title, "", *body, ""]
    if listed:
        text += [*(f"{name}: {who}" if who else name for name, who in listed), ""]
    if code:
        text += [code, ""]
    if details:
        text += [*(f"{label}: {value}" for label, value in details), ""]
    if button:
        text += [f"{button}: {link}", ""]
    text += [*after, "", "--", why]
    if unsubscribe_link:
        text.append(f"{STOP[language]}: {unsubscribe_link}")
    text.append("Acervo · por Segura")

    # Carta: a white card on grey, then why the email came and the wordmark under it.
    p = f"margin:0 0 12px;font:400 15px/24px {SANS};color:#5c5c58"
    small = f"margin:0 0 8px;font:400 13px/20px {SANS};color:#72726d"
    line = "border-bottom:1px solid #ededeb"
    html = [
        f'<!doctype html><html lang="{language}"><head><meta charset="utf-8"><title>{escape(subject)}</title></head>',
        f'<body style="margin:0;padding:40px 16px 28px;background:#f5f5f4;font-family:{SANS}">',
        f'<div style="display:none;max-height:0;overflow:hidden">{escape(pre)}</div>',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">',
        '<table role="presentation" width="520" cellpadding="0" cellspacing="0" style="max-width:520px;width:100%;'
        'background:#ffffff;border:1px solid #ededeb;border-radius:12px">',
        '<tr><td style="padding:36px 40px">',
        '<p style="margin:0 0 20px"><span style="display:inline-block;width:32px;height:32px;border-radius:8px;'
        f'background:#002311;color:#ffffff;font:600 16px/32px {SANS};letter-spacing:-.03em;text-align:center">a</span>'
        "</p>",
        f'<h1 style="margin:0 0 20px;font:500 22px/30px {SANS};letter-spacing:-.015em;color:#0a0a0a">'
        f"{escape(title)}</h1>",
        *(f'<p style="{p}">{escape(x)}</p>' for x in body),
    ]
    if listed:
        html += [
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin:0 0 20px;border-top:1px solid #ededeb">',
            *(
                f'<tr><td style="padding:12px 0;{line}">'
                f'<span style="display:block;font:500 15px/22px {SANS};color:#0a0a0a">{escape(name)}</span>'
                f'<span style="display:block;font:400 13px/20px {SANS};color:#72726d">{escape(who)}</span></td></tr>'
                for name, who in listed
            ),
            "</table>",
        ]
    if code:
        html.append(
            '<p style="margin:8px 0 20px"><span style="display:inline-block;padding:14px 24px;border-radius:8px;'
            f'background:#f5f5f4;font:500 28px/36px {MONO};letter-spacing:.24em;color:#0a0a0a">{escape(code)}'
            "</span></p>"
        )
    if button and link:
        html += [
            f'<p style="margin:8px 0 8px"><a href="{escape(link)}" style="display:inline-block;padding:12px 20px;'
            f'border-radius:8px;background:#002311;color:#ffffff;font:500 15px/20px {SANS};text-decoration:none">'
            f"{escape(button)}</a></p>",
            f'<p style="margin:0 0 20px;font:400 12px/18px {SANS};color:#959590">{OR_OPEN[language]}: '
            f'<a href="{escape(link)}" style="color:#72726d">{escape(link)}</a></p>',
        ]
    if details:
        cell = f"padding:8px 16px 8px 0;font:400 13px/20px {SANS};{line}"
        html += [
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin:0 0 20px;border-top:1px solid #ededeb">',
            *(
                f'<tr><td width="140" style="{cell};color:#72726d">{escape(label)}</td>'
                f'<td style="{cell};color:#0a0a0a">{escape(value)}</td></tr>'
                for label, value in details
            ),
            "</table>",
        ]
    stop = (
        f' <a href="{escape(unsubscribe_link)}" style="color:#959590;text-decoration:underline">{STOP[language]}</a>'
        if unsubscribe_link
        else ""
    )
    html += [
        *(f'<p style="{small}">{escape(x)}</p>' for x in after),
        "</td></tr></table>",
        f'<p style="margin:20px 0 0;font:400 12px/20px {SANS};color:#959590;text-align:center">{escape(why)}{stop}<br>'
        f'<b style="font:600 16px/20px {SANS};letter-spacing:-.02em;color:#72726d">acervo</b> '
        f'<span style="font:400 11px/16px {SANS};color:#959590">por segura</span></p>',
        "</td></tr></table></body></html>",
    ]
    return RenderedMail(subject, "\n".join(text), "".join(html))
