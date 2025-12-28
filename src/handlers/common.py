import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ErrorEvent

router = Router()
logger = logging.getLogger(__name__)


@router.error()
async def error_handler(event: ErrorEvent):
    logger.error(f"Произошла ошибка: {event.exception}", exc_info=True)
    if hasattr(event.update, 'message') and event.update.message:
        try:
            await event.update.message.answer("Произошла ошибка. Попробуйте позже.")
        except:
            pass


async def send_main_menu(message: types.Message):
    from config.constants import (
        MENU_ANON_MESSAGE,
        MENU_GET_ADVICE,
        MENU_SIGNUP_MEETING,
        MENU_UPDATE_PATH,
        MENU_VIEW_PROFILE
    )

    MAIN_MENU = [
        [MENU_ANON_MESSAGE],
        [MENU_GET_ADVICE],
        [MENU_SIGNUP_MEETING],
        [MENU_UPDATE_PATH],
        [MENU_VIEW_PROFILE],
    ]

    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=btn[0])] for btn in MAIN_MENU],
        resize_keyboard=True
    )
    await message.answer("Выберите действие:", reply_markup=kb)


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state):
    await state.clear()
    await message.answer("Операция отменена.")
    await send_main_menu(message)


@router.message()
async def fallback_handler(message: types.Message):
    if message.text:
        await message.answer(
            "Я не понимаю это сообщение. 😕\n"
            "Пожалуйста, используй кнопки меню или выбери действие из списка."
        )


def register_handlers(dp):
    dp.include_router(router)
