import asyncio
import logging
from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config.constants import MAIN_MENU_BUTTONS

logger = logging.getLogger(__name__)
MESSAGE_TIMEOUT = 10


async def send_main_menu(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=btn[0])] for btn in MAIN_MENU_BUTTONS],
        resize_keyboard=True
    )

    try:
        await asyncio.wait_for(
            message.answer("Выберите действие:", reply_markup=kb),
            timeout=MESSAGE_TIMEOUT
        )
        logger.debug(f"Main menu sent to user {message.from_user.id}")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout sending main menu to user {message.from_user.id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Failed to send main menu: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Не удалось загрузить меню. Попробуйте позже.")