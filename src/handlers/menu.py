import asyncio
import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config.constants import MAIN_MENU_BUTTONS as MAIN_MENU
from config.constants import (
    MENU_ANON_MESSAGE,
    MENU_SIGNUP_MEETING,
    MENU_UPDATE_PATH,
    MENU_VIEW_PROFILE
)
from src.bot.fsm import AnonymousStates
from src.handlers.meeting import start_meeting_selection
from src.handlers.profile import show_profile, start_profile_edit
from src.services.rate_limiter import rate_limiter

router = Router()
logger = logging.getLogger(__name__)

MESSAGE_TIMEOUT = 10


def rate_limit_middleware(handler):
    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = str(message.from_user.id)
        try:
            await rate_limiter.acquire(user_id)
            return await handler(message, *args, **kwargs)
        except asyncio.TimeoutError:
            logger.warning(f"Rate limit timeout for user {user_id} in {handler.__name__}")
            await message.answer("⏱️ Слишком много запросов. Пожалуйста, подождите немного.")
            return None
        except Exception as e:
            logger.error(f"Error in handler {handler.__name__}: {type(e).__name__}: {e}", exc_info=True)
            await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
            return None

    return wrapper


async def send_main_menu_local(message: types.Message):
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=btn[0])] for btn in MAIN_MENU],
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


@router.message(lambda msg: msg.text == MENU_ANON_MESSAGE)
@rate_limit_middleware
async def menu_anonymous(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    try:
        await state.clear()
        await state.set_state(AnonymousStates.waiting_for_message)
        await asyncio.wait_for(
            message.answer("Напишите анонимное сообщение для Насти:"),
            timeout=MESSAGE_TIMEOUT
        )
        logger.info(f"User {user_id} entered anonymous message mode")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout in menu_anonymous for user {user_id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in menu_anonymous: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.message(lambda msg: msg.text == MENU_SIGNUP_MEETING)
@rate_limit_middleware
async def menu_meeting(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    try:
        await state.clear()
        await start_meeting_selection(message, state)
        logger.info(f"User {user_id} entered meeting selection mode")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout in menu_meeting for user {user_id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in menu_meeting: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.message(lambda msg: msg.text == MENU_VIEW_PROFILE)
@rate_limit_middleware
async def menu_profile_view(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    try:
        await state.clear()
        await show_profile(message)
        logger.info(f"User {user_id} viewed their profile")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout in menu_profile_view for user {user_id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in menu_profile_view: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.message(lambda msg: msg.text == MENU_UPDATE_PATH)
@rate_limit_middleware
async def menu_profile_edit(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    try:
        await state.clear()
        await start_profile_edit(message, state)
        logger.info(f"User {user_id} entered profile edit mode")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout in menu_profile_edit for user {user_id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in menu_profile_edit: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    try:
        await state.clear()
        await asyncio.wait_for(
            message.answer("Операция отменена."),
            timeout=MESSAGE_TIMEOUT
        )
        await send_main_menu_local(message)
        logger.info(f"User {user_id} cancelled operation")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout in cmd_cancel for user {user_id}")
        await message.answer("⏱️ Превышено время ожидания.")
    except Exception as e:
        logger.error(f"Error in cmd_cancel: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


def register_menu_handlers(dp):
    dp.include_router(router)
