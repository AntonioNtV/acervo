from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import NotRequired, TypedDict

from acervo.schemas.account import Language
from acervo.services.mailer import MailTemplate


class Copy(TypedDict):
    subject: str
    pre: str
    title: str
    body: list[str]
    button: NotRequired[str]
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
BUTTON_PATH = {MailTemplate.RESET_LINK: "/redefinir-senha/{link}", MailTemplate.ORG_INVITE: "/convite/{link}"}

OR_OPEN = {"pt-BR": "Ou abra", "en": "Or open"}
FOOTER = {
    "pt-BR": "Emails da sua conta, como este, não se desligam.",
    "en": "Account emails like this one cannot be turned off.",
}
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


def _bases(names: str, language: Language) -> str:
    """ "3 bases: A, B e C" from one name per line."""
    listed = [name for name in names.split("\n") if name]
    if not listed:
        return NO_BASES[language]
    joined = listed[0] if len(listed) == 1 else f"{', '.join(listed[:-1])} {AND[language]} {listed[-1]}"
    return f"{len(listed)} base{'s' if len(listed) > 1 else ''}: {joined}"


def render(
    template: MailTemplate,
    language: Language,
    to: str,
    values: Mapping[str, str],
    public_url: str,
    now: datetime,
) -> RenderedMail:
    """Fills one template; a value the template needs and `values` lacks raises KeyError."""
    copy = COPY[template][language]
    fill = {**values, "email": to, "first": values.get("name", "").split(" ")[0], **_when(now, language)}
    for key in ("role", "old_role"):
        if key in values:
            fill[key] = ROLES[language][values[key]]
    if template in CAN:
        fill |= CAN[template][language][values["role"]]
    if "bases" in values:
        fill["bases"] = _bases(values["bases"], language)
    if "expires_at" in values:
        fill["until"] = _when(datetime.fromisoformat(values["expires_at"]), language)["date"]
    subject, pre, title = (copy["subject"].format(**fill), copy["pre"].format(**fill), copy["title"].format(**fill))
    body = [p.format(**fill) for p in copy["body"]]
    after = [p.format(**fill) for p in copy["after"]]
    code = values["code"] if template in (MailTemplate.VERIFY_CODE, MailTemplate.CHANGE_EMAIL_CODE) else None
    button = copy["button"].format(**fill) if "button" in copy else None
    path = BUTTON_PATH.get(template, "{link}").format(link=values["link"]) if button else ""
    link = f"{public_url.rstrip('/')}{path}" if button else None

    text = [title, "", *body, ""]
    if code:
        text += [code, ""]
    if button:
        text += [f"{button}: {link}", ""]
    text += [*after, "", "--", FOOTER[language], "Acervo · por Segura"]

    p = f"margin:0 0 12px;font:400 15px/24px {SANS};color:#5c5c58"
    small = f"margin:0 0 12px;font:400 13px/20px {SANS};color:#72726d"
    html = [
        f'<!doctype html><html lang="{language}"><head><meta charset="utf-8"><title>{escape(subject)}</title></head>',
        f'<body style="margin:0;padding:24px 0;background:#ffffff;font-family:{SANS}">',
        f'<div style="display:none;max-height:0;overflow:hidden">{escape(pre)}</div>',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">',
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">',
        '<tr><td style="padding:40px 48px 32px">',
        f'<p style="margin:0 0 32px;font:500 15px/20px {SANS};color:#0a0a0a">acervo '
        '<span style="font-weight:400;color:#959590">por segura</span></p>',
        f'<h1 style="margin:0 0 20px;font:500 20px/28px {SANS};letter-spacing:-.01em;color:#0a0a0a">'
        f"{escape(title)}</h1>",
        *(f'<p style="{p}">{escape(x)}</p>' for x in body),
    ]
    if code:
        html.append(
            '<p style="margin:8px 0 20px"><span style="display:inline-block;padding:16px 24px;border-radius:8px;'
            f'background:#f5f5f4;font:500 28px/36px {MONO};letter-spacing:.2em;color:#0a0a0a">{escape(code)}</span></p>'
        )
    if button and link:
        html += [
            f'<p style="margin:8px 0 8px"><a href="{escape(link)}" style="display:inline-block;padding:10px 18px;'
            f'border-radius:7px;background:#002311;color:#ffffff;font:500 14px/20px {SANS};text-decoration:none">'
            f"{escape(button)}</a></p>",
            f'<p style="margin:0 0 20px;font:400 12px/18px {SANS};color:#959590">{OR_OPEN[language]}: '
            f'<a href="{escape(link)}" style="color:#72726d">{escape(link)}</a></p>',
        ]
    html += [
        *(f'<p style="{small}">{escape(x)}</p>' for x in after),
        f'<p style="margin:24px 0 0;padding-top:16px;border-top:1px solid #ededeb;font:400 12px/18px {SANS};'
        f'color:#959590">{FOOTER[language]}<br>Acervo · por Segura</p>',
        "</td></tr></table></td></tr></table></body></html>",
    ]
    return RenderedMail(subject, "\n".join(text), "".join(html))
