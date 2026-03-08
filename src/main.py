import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.bot.bot import create_bot, close_bot
from src.handlers import register_all_handlers
from src.services.audit import get_audit_stats, init_audit_ttl_index, close_audit_logger
from src.services.db import init_mongo, close_mongo
from src.services.google_sheets import get_google_sheets_stats
from src.services.openrouter import (
    init_openrouter_session,
    close_openrouter_session,
    get_openrouter_stats,
    health_check_openrouter
)


async def on_startup(bot: Bot):
    """Вызывается один раз при старте бота."""
    logging.info("Bot starting up...")

    bot_me = await bot.get_me()
    logging.info(f"Bot started: @{bot_me.username}")

    await init_mongo()
    await init_audit_ttl_index()
    await init_openrouter_session()

    audit_stats = get_audit_stats()
    google_sheets_stats = get_google_sheets_stats()
    openrouter_stats = get_openrouter_stats()
    is_healthy = await health_check_openrouter()

    logging.info(
        f"Audit queue: {audit_stats['queue_size']}/{audit_stats['max_queue_size']}, "
        f"dropped: {audit_stats['logs_dropped']}"
    )
    logging.info(
        f"Google Sheets cache: {google_sheets_stats['cache_size']}/"
        f"{google_sheets_stats['cache_max_size']}"
    )
    logging.info(
        f"OpenRouter: {openrouter_stats['requests_success']}/"
        f"{openrouter_stats['requests_total']} успешных, "
        f"{openrouter_stats['retries_total']} ретраев"
    )
    logging.info(f"OpenRouter health: {'OK' if is_healthy else 'FAILED'}")


async def on_shutdown(bot: Bot):
    """Вызывается один раз при остановке бота."""
    await close_audit_logger()
    await close_openrouter_session()
    await close_mongo()
    await close_bot(bot)
    logging.info("Bot stopped successfully.")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    dp = Dispatcher(storage=MemoryStorage())
    bot = create_bot()

    register_all_handlers(dp)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(
        bot,
        skip_updates=True,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    asyncio.run(main())
