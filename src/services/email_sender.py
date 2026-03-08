import asyncio
import json
import logging
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Tuple

import aiosmtplib
from dotenv import load_dotenv
from jinja2 import Template

load_dotenv()

CURRENT_FILE_DIR = Path(__file__).parent
SRC_DIR = CURRENT_FILE_DIR.parent
TEMPLATE_DIR = SRC_DIR / "templates" / "email"
CONFIG_DIR = SRC_DIR.parent / "config"

GMAIL_USER = os.getenv("GMAIL_EMAIL")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")

SMTP_TIMEOUT = 30
MAX_RETRIES = 3
EMAIL_RATE_LIMIT = 10
_rate_limit_semaphore = asyncio.Semaphore(EMAIL_RATE_LIMIT)

logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def _validate_email(email: str) -> bool:
    return bool(_EMAIL_PATTERN.match(email))


async def _read_file_async(file_path: Path) -> str:
    loop = asyncio.get_running_loop()

    def read_file():
        with open(file_path, encoding="utf-8") as f:
            return f.read()

    return await loop.run_in_executor(None, read_file)


async def _load_template_async(name: str) -> Tuple[Template, Template]:
    html_path = TEMPLATE_DIR / f"{name}.html"
    txt_path = TEMPLATE_DIR / f"{name}.txt"

    if not html_path.exists():
        logger.error(f"HTML template not found: {html_path}")
        raise FileNotFoundError(f"HTML template not found: {html_path}")
    if not txt_path.exists():
        logger.error(f"Text template not found: {txt_path}")
        raise FileNotFoundError(f"Text template not found: {txt_path}")

    html_content, text_content = await asyncio.gather(
        _read_file_async(html_path),
        _read_file_async(txt_path)
    )

    loop = asyncio.get_running_loop()
    html_tmpl, text_tmpl = await loop.run_in_executor(
        None,
        lambda: (Template(html_content), Template(text_content))
    )
    return html_tmpl, text_tmpl


_MEETING_TEMPLATES: Optional[Tuple[Template, Template]] = None
_ANON_TEMPLATES: Optional[Tuple[Template, Template]] = None


async def _get_meeting_templates() -> Tuple[Template, Template]:
    global _MEETING_TEMPLATES
    if _MEETING_TEMPLATES is None:
        _MEETING_TEMPLATES = await _load_template_async("meeting_request")
    return _MEETING_TEMPLATES


async def _get_anon_templates() -> Tuple[Template, Template]:
    global _ANON_TEMPLATES
    if _ANON_TEMPLATES is None:
        _ANON_TEMPLATES = await _load_template_async("anonymous_message")
    return _ANON_TEMPLATES


async def send_email(to: str, subject: str, html: str, text: str) -> bool:
    if not _validate_email(to):
        logger.error(f"Invalid email address: {to}")
        return False

    if not GMAIL_USER or not GMAIL_PASS:
        logger.error("GMAIL_EMAIL or GMAIL_APP_PASSWORD not configured")
        return False

    if len(subject) > 200:
        logger.warning(f"Email subject too long, truncating: {len(subject)} chars")
        subject = subject[:200]

    logger.info(f"Starting to send email to {to}...")

    async with _rate_limit_semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = GMAIL_USER
                msg["To"] = to

                msg.attach(MIMEText(text, "plain", "utf-8"))
                msg.attach(MIMEText(html, "html", "utf-8"))

                logger.debug(f"Connecting to smtp.gmail.com:465...")

                await aiosmtplib.send(
                    msg,
                    hostname="smtp.gmail.com",
                    port=465,
                    use_tls=True,
                    username=GMAIL_USER,
                    password=GMAIL_PASS,
                    timeout=SMTP_TIMEOUT
                )

                logger.info(f"Email sent successfully to {to}")
                return True

            except aiosmtplib.SMTPTimeoutError as e:
                logger.warning(f"SMTP timeout (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (2 ** attempt))
                    continue
                return False

            except aiosmtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP authentication failed: {e}")
                return False

            except aiosmtplib.SMTPRecipientsRefused as e:
                logger.error(f"Email recipient refused: {e}")
                return False

            except Exception as e:
                logger.error(f"Unexpected error sending email: {type(e).__name__}: {e}", exc_info=True)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                return False

    return False


async def send_meeting_request_email(mentor_name: str, to: str, display_name: str, message: str) -> bool:
    if not message or len(message.strip()) == 0:
        logger.warning("Empty message in send_meeting_request_email")
        message = "Без сообщения"

    if len(message) > 5000:
        logger.warning(f"Message too long, truncating: {len(message)} chars")
        message = message[:5000]

    try:
        html_tmpl, text_tmpl = await _get_meeting_templates()

        loop = asyncio.get_running_loop()
        html, text = await loop.run_in_executor(
            None,
            lambda: (
                html_tmpl.render(mentor=mentor_name, name=display_name, message=message),
                text_tmpl.render(mentor=mentor_name, name=display_name, message=message)
            )
        )

        success = await send_email(to, f"Запрос на встречу от {display_name}", html, text)
        return success

    except Exception as e:
        logger.error(f"Error in send_meeting_request_email: {type(e).__name__}: {e}", exc_info=True)
        return False


async def send_anonymous_email(message: str) -> bool:
    if not message or len(message.strip()) == 0:
        logger.warning("Empty message in send_anonymous_email")
        return False

    if len(message) > 5000:
        logger.warning(f"Anonymous message too long, truncating: {len(message)} chars")
        message = message[:5000]

    try:
        mentors_path = CONFIG_DIR / "mentors.json"

        loop = asyncio.get_running_loop()
        mentors = await loop.run_in_executor(
            None,
            lambda: json.loads(open(mentors_path, "r", encoding="utf-8").read())
        )

        to = mentors.get("Настя")
        if not to:
            logger.error("Mentor 'Настя' not found in mentors.json")
            return False

        html_tmpl, text_tmpl = await _get_anon_templates()

        html, text = await loop.run_in_executor(
            None,
            lambda: (
                html_tmpl.render(message=message),
                text_tmpl.render(message=message)
            )
        )

        success = await send_email(to, "Анонимное сообщение в АРТе", html, text)
        return success

    except FileNotFoundError as e:
        logger.error(f"mentors.json not found: {e}", exc_info=True)
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in mentors.json: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Error in send_anonymous_email: {type(e).__name__}: {e}", exc_info=True)
        return False