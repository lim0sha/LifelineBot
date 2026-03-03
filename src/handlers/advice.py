import asyncio
import logging

from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from config.constants import (
    MENU_ANON_MESSAGE,
    MENU_GET_ADVICE,
    MENU_SIGNUP_MEETING,
    MENU_UPDATE_PATH,
    MENU_VIEW_PROFILE
)
from src.bot.fsm import AdviceStates
from src.services.audit import log_action
from src.services.openrouter import get_ai_advice
from src.services.rate_limiter import rate_limiter

router = Router()
logger = logging.getLogger(__name__)

MENU_BUTTONS = frozenset({
    MENU_ANON_MESSAGE,
    MENU_GET_ADVICE,
    MENU_SIGNUP_MEETING,
    MENU_UPDATE_PATH,
    MENU_VIEW_PROFILE
})

MAX_MESSAGE_LENGTH = 2000
ADVICE_TIMEOUT = 90


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


@router.message(lambda msg: msg.text == MENU_GET_ADVICE)
@rate_limit_middleware
async def menu_advice(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    try:
        await log_action(user_id, "request_advice", {})
        logger.info(f"User {user_id} requested AI advice")

        advice = await asyncio.wait_for(get_ai_advice("Привет! Я хочу получить поддержку."), timeout=ADVICE_TIMEOUT)
        await message.answer(advice)

        await state.set_state(AdviceStates.in_advice_mode)
        await message.answer(
            "💬 Напишите своё сообщение, и я отвечу. Чтобы выйти — нажмите любую кнопку меню или /cancel.")

    except asyncio.TimeoutError:
        logger.error(f"Timeout getting initial advice for user {user_id}")
        await message.answer("⏱️ Сервис временно перегружен. Попробуйте через минуту.")
    except Exception as e:
        logger.error(f"Error in menu_advice: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Не удалось получить совет. Попробуйте позже.")


@router.message(AdviceStates.in_advice_mode, lambda msg: msg.text not in MENU_BUTTONS)
@rate_limit_middleware
async def process_advice_message(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    user_message = message.text.strip()
    if not user_message:
        await message.answer("Пожалуйста, введите текст сообщения.")
        return

    if len(user_message) > MAX_MESSAGE_LENGTH:
        logger.warning(f"Message too long from user {user_id}: {len(user_message)} chars")
        await message.answer(
            f"⚠️ Сообщение слишком длинное (максимум {MAX_MESSAGE_LENGTH} символов). Пожалуйста, сократите.")
        return

    try:
        await log_action(user_id, "advice_followup", {"message_length": len(user_message)})
        logger.info(f"User {user_id} sent advice message ({len(user_message)} chars)")

        advice = await asyncio.wait_for(get_ai_advice(user_message), timeout=ADVICE_TIMEOUT)
        await message.answer(advice)

    except asyncio.TimeoutError:
        logger.error(f"Timeout getting advice for user {user_id}")
        await message.answer("⏱️ Время ожидания ответа истекло. Попробуйте ещё раз.")
    except Exception as e:
        logger.error(f"Error in process_advice_message: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Не удалось получить ответ. Попробуйте позже.")


@router.message(AdviceStates.in_advice_mode, lambda msg: msg.text in MENU_BUTTONS)
async def exit_advice_mode_on_menu(message: types.Message, state: FSMContext, **kwargs):
    """Обработчик для выхода из режима совета при нажатии кнопки меню"""
    user_id = message.from_user.id
    logger.info(f"User {user_id} exited advice mode via menu button: {message.text}")

    await state.clear()

    if message.text == MENU_ANON_MESSAGE:
        from src.handlers.anonymous import menu_anonymous
        await menu_anonymous(message, state, **kwargs)
    elif message.text == MENU_GET_ADVICE:
        await menu_advice(message, state, **kwargs)
    elif message.text == MENU_SIGNUP_MEETING:
        from src.handlers.meeting import start_meeting_selection
        await start_meeting_selection(message, state, **kwargs)
    elif message.text == MENU_VIEW_PROFILE:
        from src.handlers.profile import show_profile
        await show_profile(message, **kwargs)
    elif message.text == MENU_UPDATE_PATH:
        from src.handlers.profile import menu_profile_edit
        await menu_profile_edit(message, state, **kwargs)


def register_handlers(dp):
    dp.include_router(router)