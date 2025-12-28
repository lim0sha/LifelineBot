import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.bot.bot import create_bot
from src.handlers import register_all_handlers
from src.services.audit import init_audit_ttl_index


async def main():
    logging.basicConfig(level=logging.INFO)
    dp = Dispatcher(storage=MemoryStorage())
    bot = create_bot()

    register_all_handlers(dp)

    await init_audit_ttl_index()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
