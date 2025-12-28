import json
from pathlib import Path

from aiogram import types, Router
from aiogram.fsm.context import FSMContext

from src.bot.fsm import MeetingStates
from src.services.audit import log_action
from src.services.email_sender import send_meeting_request_email
from src.services.google_sheets import get_user_profile

router = Router()

MENTORS_FILE = Path(__file__).parent.parent.parent / "config" / "mentors.json"

with open(MENTORS_FILE, "r", encoding="utf-8") as f:
    MENTORS = json.load(f)


@router.message(MeetingStates.selecting_mentor)
async def select_mentor(message: types.Message, state: FSMContext):
    if message.text not in MENTORS:
        await message.answer("Пожалуйста, выберите руководителя из списка.")
        await show_mentor_buttons(message)
        return

    await state.update_data(selected_mentor=message.text)
    await state.set_state(MeetingStates.waiting_for_message)
    await message.answer(f"Напишите, что вы хотите обсудить с {message.text}:")


@router.message(MeetingStates.waiting_for_message)
async def process_meeting_message(message: types.Message, state: FSMContext):
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

    await send_meeting_request_email(mentor, email, display_name, text)
    await log_action(user.id, "meeting_request", {"mentor": mentor, "message": text})

    await state.clear()
    await message.answer(f"Ваш запрос отправлен {mentor}!")
    from src.handlers.common import send_main_menu
    await send_main_menu(message)


async def show_mentor_buttons(message: types.Message):
    buttons = [types.KeyboardButton(text=name) for name in MENTORS.keys()]
    kb = types.ReplyKeyboardMarkup(
        keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)],
        resize_keyboard=True
    )
    await message.answer("Выберите руководителя:", reply_markup=kb)


async def start_meeting_selection(message: types.Message, state: FSMContext):
    await state.set_state(MeetingStates.selecting_mentor)
    await show_mentor_buttons(message)


def register_handlers(dp):
    dp.include_router(router)
