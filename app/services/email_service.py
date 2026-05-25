from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings


logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def is_configured() -> bool:
        return bool(settings.EMAIL_USERNAME and settings.EMAIL_PASSWORD and settings.EMAIL_FROM)

    @staticmethod
    def _describe_smtp_mode() -> str:
        if settings.EMAIL_USE_SSL:
            return "ssl"
        if settings.EMAIL_USE_TLS:
            return "starttls"
        return "plain"

    @staticmethod
    def _send_message(to_email: str, subject: str, body: str) -> bool:
        if not EmailService.is_configured():
            logger.warning(
                "Email delivery skipped because SMTP is not configured (host=%s, port=%s, from=%s, username_set=%s)",
                settings.EMAIL_HOST,
                settings.EMAIL_PORT,
                settings.EMAIL_FROM,
                bool(settings.EMAIL_USERNAME),
            )
            return False

        logger.info(
            "Preparing SMTP email send (to=%s, subject=%s, host=%s, port=%s, mode=%s)",
            to_email,
            subject,
            settings.EMAIL_HOST,
            settings.EMAIL_PORT,
            EmailService._describe_smtp_mode(),
        )

        message = EmailMessage()
        message["From"] = settings.EMAIL_FROM
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            if settings.EMAIL_USE_SSL:
                logger.info("Opening SMTP SSL connection to %s:%s", settings.EMAIL_HOST, settings.EMAIL_PORT)
                with smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=15) as client:
                    logger.info("Authenticating SMTP user %s", settings.EMAIL_USERNAME)
                    client.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
                    logger.info("Sending email to %s", to_email)
                    client.send_message(message)
            else:
                logger.info("Opening SMTP connection to %s:%s", settings.EMAIL_HOST, settings.EMAIL_PORT)
                with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=15) as client:
                    if settings.EMAIL_USE_TLS:
                        logger.info("Starting TLS for SMTP email delivery")
                        client.starttls()
                    logger.info("Authenticating SMTP user %s", settings.EMAIL_USERNAME)
                    client.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
                    logger.info("Sending email to %s", to_email)
                    client.send_message(message)
            logger.info("Email sent successfully to %s with subject %s", to_email, subject)
            return True
        except (OSError, smtplib.SMTPException) as exc:
            logger.exception(
                "Failed to send email to %s via %s:%s in %s mode",
                to_email,
                settings.EMAIL_HOST,
                settings.EMAIL_PORT,
                EmailService._describe_smtp_mode(),
            )
            raise RuntimeError("Email delivery failed") from exc

    @staticmethod
    def send_password_reset_email(to_email: str, reset_token: str, expires_at) -> bool:
        body = (
            "You requested a password reset for your MoveMate account.\n\n"
            f"Reset token: {reset_token}\n"
            f"Expires at: {expires_at.isoformat()}\n\n"
            "Use this token with the password reset form to choose a new password."
        )
        return EmailService._send_message(to_email, "MoveMate password reset", body)

    @staticmethod
    def send_driver_temporary_password_email(to_email: str, temporary_password: str) -> bool:
        body = (
            "Your MoveMate driver account has been created.\n\n"
            f"Temporary password: {temporary_password}\n\n"
            "Sign in with this password, then reset it immediately after logging in."
        )
        return EmailService._send_message(to_email, "MoveMate driver account access", body)

    @staticmethod
    def send_welcome_email(to_email: str, full_name: str | None = None) -> bool:
        name = full_name or "",
        body = (
            f"Welcome to MoveMate {name}!\n\n"
            "Your account has been created successfully. You can sign in using your email and the password you chose during registration.\n\n"
            "If you did not create this account, please contact support."
        )
        return EmailService._send_message(to_email, "Welcome to MoveMate", body)