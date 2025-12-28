from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from src.handlers.menu import send_main_menu
from src.services.db import ensure_user_exists
from src.services.google_sheets import get_user_profile, create_user_profile

router = Router()


class RegistrationStates(StatesGroup):
    waiting_for_full_name = State()


@router.message(lambda msg: msg.text and msg.text.startswith("/start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = message.from_user
    tg_id = user.id

    await ensure_user_exists(user)
    profile = await get_user_profile(tg_id)

    if profile:
        await message.answer(
            f"Привет, {user.first_name}! 👋\nРады видеть тебя снова!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await send_main_menu(message)
    else:
        full_name = ""
        if user.first_name and user.last_name:
            full_name = f"{user.first_name} {user.last_name}"
        elif user.first_name:
            full_name = user.first_name

        if full_name:
            await create_user_profile(tg_id, full_name, user.username or "")
            await message.answer(
                f"Привет, {full_name}! 👋\nТвоя анкета создана. Добро пожаловать в проект «АРТ. Путь.»!",
                reply_markup=types.ReplyKeyboardRemove()
            )
            await send_main_menu(message)
        else:
            await state.set_state(RegistrationStates.waiting_for_full_name)
            await message.answer(
                "Привет! 👋\nПожалуйста, напиши своё **имя и фамилию** (например, Иван Иванов)."
            )


@router.message(RegistrationStates.waiting_for_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name.split()) < 1:
        await message.answer("Пожалуйста, введите хотя бы имя.")
        return

    await create_user_profile(message.from_user.id, full_name, message.from_user.username or "")

    await state.clear()
    await message.answer(
        f"Спасибо, {full_name}! ✨\nТеперь ты в регистре проекта «АРТ. Путь.»!",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await send_main_menu(message)


def register_handlers(dp):
    dp.include_router(router)
