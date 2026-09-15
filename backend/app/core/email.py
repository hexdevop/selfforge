import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(message: EmailMessage) -> None:
    """Deliver via SMTP. Sync on purpose: meant to run as a FastAPI background task
    (Starlette runs sync tasks in a threadpool). Failures are logged, not raised —
    the user can always request the email again.
    """
    message["From"] = settings.EMAIL_FROM
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send email %r to %s", message["Subject"], message["To"])
