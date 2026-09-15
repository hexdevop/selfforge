from datetime import timedelta
from email.message import EmailMessage

from app.core.config import settings
from app.core.security import TokenType, create_action_token, password_fingerprint
from app.models.user import User

VERIFY_TTL = timedelta(days=2)
RESET_TTL = timedelta(hours=1)


def _message(to: str, subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message


def verification_email(user: User) -> EmailMessage:
    token = create_action_token(user.id, TokenType.EMAIL_VERIFY, VERIFY_TTL, email=user.email)
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    return _message(
        user.email,
        "Подтверди почту в Self Forge",
        f"Привет!\n\n"
        f"Чтобы подтвердить адрес, открой ссылку:\n{link}\n\n"
        f"Ссылка действует двое суток. Если письмо пришло по ошибке, просто удали его.\n",
    )


def password_reset_email(user: User) -> EmailMessage:
    token = create_action_token(
        user.id,
        TokenType.PASSWORD_RESET,
        RESET_TTL,
        pwd=password_fingerprint(user.hashed_password),
    )
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    return _message(
        user.email,
        "Сброс пароля в Self Forge",
        f"Привет!\n\n"
        f"Чтобы задать новый пароль, открой ссылку:\n{link}\n\n"
        f"Ссылка действует час и срабатывает один раз. Если это не твой запрос, "
        f"ничего не делай — пароль останется прежним.\n",
    )
