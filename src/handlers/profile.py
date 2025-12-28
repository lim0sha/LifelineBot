from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold

from config.constants import ALL_PROFILE_FIELDS, EDITABLE_FIELDS, MENU_VIEW_PROFILE
from src.bot.fsm import ProfileStates
from src.services.google_sheets import get_user_profile, update_user_field

router = Router()


@router.message(lambda msg: msg.text == MENU_VIEW_PROFILE)
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    if not profile:
        await message.answer("Ваша анкета ещё не создана. Обратитесь к руководителю.")
        return

    text = "📄 Ваша анкета:\n\n"
    for field in ALL_PROFILE_FIELDS:
        value = profile.get(field, "—")
        text += f"📍 {hbold(f'{field}:')}\n{value}\n\n"
    await message.answer(text, parse_mode=ParseMode.HTML)


async def start_profile_edit(message: types.Message, state: FSMContext):
    buttons = [[types.KeyboardButton(text=field)] for field in EDITABLE_FIELDS]
    kb = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("Какой блок вы хотите изменить?", reply_markup=kb)
    await state.set_state(ProfileStates.selecting_field)


@router.message(ProfileStates.selecting_field)
async def process_field_selection(message: types.Message, state: FSMContext):
    print("DEBUG: process_field_selection called with text =", message.text)
    if message.text not in EDITABLE_FIELDS:
        await message.answer("Пожалуйста, выберите поле из списка.")
        return

    await state.update_data(editing_field=message.text)
    await state.set_state(ProfileStates.editing_field)
    await message.answer(f"Введите новое значение для блока '{message.text}':")


@router.message(ProfileStates.editing_field)
async def process_field_edit(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    field = data["editing_field"]
    new_value = message.text

    success = await update_user_field(user_id, field, new_value)
    if success:
        await message.answer("✅ Анкета обновлена!")
    else:
        await message.answer("❌ Не удалось обновить анкету. Обратитесь к руководителю.")

    await state.clear()
    from src.handlers.menu import send_main_menu
    await send_main_menu(message)


def register_handlers(dp):
    dp.include_router(router)
