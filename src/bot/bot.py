import logging
import os
import re

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TOKEN_PATTERN = re.compile(r"^\d{8,10}:[A-Za-z0-9_-]{35}$")

BOT_TIMEOUT = 60


def validate_token_format(token: str) -> bool:
    return bool(TOKEN_PATTERN.match(token))


def create_bot() -> Bot:
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set in environment variables")
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

    if not validate_token_format(token):
        logger.error("Invalid Telegram bot token format")
        raise ValueError("Invalid Telegram bot token format")

    session = AiohttpSession(
        timeout=BOT_TIMEOUT,
    )

    bot = Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            protect_content=False,
        ),
    )

    logger.info(f"Bot initialized successfully (id={bot.id})")

    return bot


async def close_bot(bot: Bot):
    await bot.session.close()
    logger.info("Bot session closed.")
