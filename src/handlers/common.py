import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict

from aiogram import types, Router
from aiogram.fsm.context import FSMContext

from src.bot.fsm import MeetingStates
from src.services.audit import log_action
from src.services.email_sender import send_meeting_request_email
from src.services.google_sheets import get_user_profile
from src.services.rate_limiter import rate_limiter
from src.utils.menu_utils import send_main_menu

router = Router()
logger = logging.getLogger(__name__)

MENTORS_FILE = Path(__file__).parent.parent.parent / "config" / "mentors.json"
MENTORS_CACHE: Optional[Dict[str, str]] = None
MENTORS_CACHE_MAX_SIZE = 100

EMAIL_TIMEOUT = 30
MAX_MESSAGE_LENGTH = 2000


def get_mentors() -> Dict[str, str]:
    global MENTORS_CACHE
    if MENTORS_CACHE is None:
        try:
            with open(MENTORS_FILE, "r", encoding="utf-8") as f:
                MENTORS_CACHE = json.load(f)
            logger.info(f"Loaded {len(MENTORS_CACHE)} mentors from config")
        except FileNotFoundError:
            logger.error(f"Mentors file not found: {MENTORS_FILE}")
            MENTORS_CACHE = {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in mentors file: {e}")
            MENTORS_CACHE = {}
    return MENTORS_CACHE


MENTORS = get_mentors()


def rate_limit_middleware(handler):
    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = str(message.from_user.id)
        try:
            await rate_limiter.acquire(user_id)
            return await handler(message, *args, **kwargs)
        except asyncio.TimeoutError:
            logger.warning(f"Rate limit timeout for user {user_id} in meeting handler")
            await message.answer("⏱️ Слишком много запросов. Пожалуйста, подождите немного.")
            return None
        except Exception as e:
            logger.error(f"Error in handler {handler.__name__}: {type(e).__name__}: {e}", exc_info=True)
            await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
            return None

    return wrapper


@router.message(MeetingStates.selecting_mentor)
@rate_limit_middleware
async def select_mentor(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if message.text not in MENTORS:
        logger.warning(f"Invalid mentor selection by user {user_id}: {message.text}")
        await message.answer("Пожалуйста, выберите руководителя из списка.")
        await show_mentor_buttons(message)
        return

    await state.update_data(selected_mentor=message.text)
    await state.set_state(MeetingStates.waiting_for_message)
    logger.info(f"User {user_id} selected mentor: {message.text}")
    await message.answer(f"Напишите, что вы хотите обсудить с {message.text}:")


@router.message(MeetingStates.waiting_for_message)
@rate_limit_middleware
async def process_meeting_message(message: types.Message, state: FSMContext):
    user = message.from_user.id
    user_id = user.id

    data = await state.get_data()
    mentor = data.get("selected_mentor")

    if not mentor or mentor not in MENTORS:
        logger.error(f"Invalid mentor in state for user {user_id}: {mentor}")
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, начните запрос заново.")
        await state.clear()
        await send_main_menu(message)
        return

    text = message.text.strip() if message.text else ""

    if not text:
        await message.answer("⚠️ Пожалуйста, введите текст сообщения.")
        return

    if len(text) > MAX_MESSAGE_LENGTH:
        logger.warning(f"Message too long from user {user_id}: {len(text)} chars")
        await message.answer(
            f"⚠️ Сообщение слишком длинное (максимум {MAX_MESSAGE_LENGTH} символов). Пожалуйста, сократите.")
        return

    email = MENTORS[mentor]

    try:
        profile = await asyncio.wait_for(get_user_profile(user_id), timeout=10.0)
        display_name = profile.get("profile_name", "Пользователь") if profile else "Пользователь"

        if display_name == "Пользователь":
            if user.first_name and user.last_name:
                display_name = f"{user.first_name} {user.last_name}"
            elif user.first_name:
                display_name = user.first_name

        if user.username:
            display_name = f"{display_name} (@{user.username})"

        success = await asyncio.wait_for(
            send_meeting_request_email(mentor, email, display_name, text),
            timeout=EMAIL_TIMEOUT
        )

        if success:
            await log_action(user_id, "meeting_request", {"mentor": mentor, "message_length": len(text)})
            logger.info(f"Meeting request sent by user {user_id} to mentor {mentor}")
            await message.answer(f"✅ Ваш запрос отправлен {mentor}!")
        else:
            logger.error(f"Failed to send meeting request for user {user_id} to mentor {mentor}")
            await message.answer(
                "⚠️ Не удалось отправить письмо. Попробуйте позже или обратитесь к руководителю напрямую.")

    except asyncio.TimeoutError:
        logger.error(f"Timeout processing meeting request for user {user_id}")
        await message.answer("⏱️ Время ожидания истекло. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Unexpected error in process_meeting_message: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
    finally:
        await state.clear()
        await send_main_menu(message)


async def show_mentor_buttons(message: types.Message):
    try:
        buttons = [types.KeyboardButton(text=name) for name in MENTORS.keys()]
        kb = types.ReplyKeyboardMarkup(
            keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)],
            resize_keyboard=True
        )
        await message.answer("Выберите руководителя:", reply_markup=kb)
    except Exception as e:
        logger.error(f"Error showing mentor buttons: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Не удалось загрузить список руководителей. Попробуйте позже.")


async def start_meeting_selection(message: types.Message, state: FSMContext):
    await state.set_state(MeetingStates.selecting_mentor)
    await show_mentor_buttons(message)


def register_handlers(dp):
    dp.include_router(router)
