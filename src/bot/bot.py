import os

from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()


def create_bot() -> Bot:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")
    return Bot(token=token)
