import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from dotenv import load_dotenv
from jinja2 import Template
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

CURRENT_FILE_DIR = Path(__file__).parent
SRC_DIR = CURRENT_FILE_DIR.parent
TEMPLATE_DIR = SRC_DIR / "templates" / "email"
CONFIG_DIR = SRC_DIR.parent / "config"

GMAIL_USER = os.getenv("GMAIL_EMAIL")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def send_email(to: str, subject: str, html: str, text: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = to

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname="smtp.gmail.com",
        port=465,
        use_tls=True,
        username=GMAIL_USER,
        password=GMAIL_PASS
    )


def _load_template(name):
    html_path = TEMPLATE_DIR / f"{name}.html"
    txt_path = TEMPLATE_DIR / f"{name}.txt"

    if not html_path.exists():
        raise FileNotFoundError(f"HTML template not found: {html_path}")
    if not txt_path.exists():
        raise FileNotFoundError(f"Text template not found: {txt_path}")

    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    with open(txt_path, encoding="utf-8") as f:
        text = f.read()
    return Template(html), Template(text)


MEETING_TEMPLATES = _load_template("meeting_request")
ANON_TEMPLATES = _load_template("anonymous_message")


async def send_meeting_request_email(mentor_name: str, to: str, display_name: str, message: str):
    html_tmpl, text_tmpl = MEETING_TEMPLATES
    html = html_tmpl.render(mentor=mentor_name, name=display_name, message=message)
    text = text_tmpl.render(mentor=mentor_name, name=display_name, message=message)
    await send_email(to, f"Запрос на встречу от {display_name}", html, text)


async def send_anonymous_email(message: str):
    mentors_path = CONFIG_DIR / "mentors.json"
    with open(mentors_path, "r", encoding="utf-8") as f:
        mentors = json.load(f)
    to = mentors["Настя"]
    html_tmpl, text_tmpl = ANON_TEMPLATES
    html = html_tmpl.render(message=message)
    text = text_tmpl.render(message=message)
    await send_email(to, "Анонимное сообщение в АРТе", html, text)
