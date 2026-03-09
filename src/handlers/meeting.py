import json
import logging
from pathlib import Path
from typing import Optional

from aiogram import types, Router
from aiogram.fsm.context import FSMContext

from src.bot.fsm import MeetingStates
from src.services.audit import log_action
from src.services.email_sender import send_meeting_request
from src.services.google_sheets import get_user_profile
from src.services.rate_limiter import rate_limiter

router = Router()

MENTORS_FILE = Path(__file__).parent.parent.parent / "config" / "mentors.json"
MENTORS_CACHE: Optional[dict] = None


def get_mentors() -> dict:
    global MENTORS_CACHE
    if MENTORS_CACHE is None:
        with open(MENTORS_FILE, "r", encoding="utf-8") as f:
            MENTORS_CACHE = json.load(f)
    return MENTORS_CACHE


MENTORS = get_mentors()


def rate_limit_middleware(handler):
    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = str(message.from_user.id)
        await rate_limiter.acquire(user_id)
        try:
            return await handler(message, *args, **kwargs)
        except Exception as e:
            logging.error(f"Error in handler: {e}")
            await message.answer("Произошла ошибка. Попробуйте позже.")
            return None

    return wrapper


@router.message(MeetingStates.selecting_mentor)
@rate_limit_middleware
async def select_mentor(message: types.Message, state: FSMContext, **kwargs):
    if message.text not in MENTORS:
        await message.answer("Пожалуйста, выберите руководителя из списка.")
        await show_mentor_buttons(message)
        return

    await state.update_data(selected_mentor=message.text)
    await state.set_state(MeetingStates.waiting_for_message)
    await message.answer(f"Напишите, что вы хотите обсудить с {message.text}:")


@router.message(MeetingStates.waiting_for_message)
@rate_limit_middleware
async def process_meeting_message(message: types.Message, state: FSMContext, **kwargs):
    user = message.from_user
    data = await state.get_data()
    mentor = data["selected_mentor"]
    email = MENTORS[mentor]
    text = message.text or "Без сообщения"

    profile = await get_user_profile(user.id)
    display_name = profile.get("profile_name", "Пользователь")

    if display_name == "Пользователь":
        if user.first_name and user.last_name:
            display_name = f"{user.first_name} {user.last_name}"
        elif user.first_name:
            display_name = user.first_name

    if user.username:
        display_name = f"{display_name} (@{user.username})"

    success = await send_meeting_request(mentor, email, display_name, text)
    if not success:
        await message.answer("⚠️ Не удалось отправить письмо. Попробуйте позже.")
    else:
        await message.answer("✅ Письмо отправлено!")

    await log_action(user.id, "meeting_request", {"mentor": mentor, "message": text})

    await state.clear()
    await message.answer(f"Ваш запрос отправлен {mentor}!")
    from src.handlers.common import send_main_menu
    await send_main_menu(message)


async def show_mentor_buttons(message: types.Message, **kwargs):
    buttons = [types.KeyboardButton(text=name) for name in MENTORS.keys()]
    kb = types.ReplyKeyboardMarkup(
        keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)],
        resize_keyboard=True
    )
    await message.answer("Выберите руководителя:", reply_markup=kb)


async def start_meeting_selection(message: types.Message, state: FSMContext, **kwargs):
    await state.set_state(MeetingStates.selecting_mentor)
    await show_mentor_buttons(message)


def register_handlers(dp):
    dp.include_router(router)
