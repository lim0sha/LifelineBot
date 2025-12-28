from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config.constants import *
from src.bot.fsm import AnonymousStates
from src.handlers.meeting import start_meeting_selection
from src.handlers.profile import start_profile_edit

router = Router()

MAIN_MENU = [
    [MENU_ANON_MESSAGE],
    [MENU_GET_ADVICE],
    [MENU_SIGNUP_MEETING],
    [MENU_UPDATE_PATH],
    [MENU_VIEW_PROFILE],
]


async def send_main_menu(message: types.Message):
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=btn[0])] for btn in MAIN_MENU],
        resize_keyboard=True
    )
    await message.answer("Выберите действие:", reply_markup=kb)


@router.message(lambda msg: msg.text == MENU_ANON_MESSAGE)
async def menu_anonymous(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(AnonymousStates.waiting_for_message)
    await message.answer("Напишите анонимное сообщение для Насти:")


@router.message(lambda msg: msg.text == MENU_SIGNUP_MEETING)
async def menu_meeting(message: types.Message, state: FSMContext):
    await state.clear()
    await start_meeting_selection(message, state)


@router.message(lambda msg: msg.text == MENU_VIEW_PROFILE)
async def menu_profile_view(message: types.Message, state: FSMContext):
    await state.clear()
    from src.handlers.profile import show_profile
    await show_profile(message)


@router.message(lambda msg: msg.text == MENU_UPDATE_PATH)
async def menu_profile_edit(message: types.Message, state: FSMContext):
    await state.clear()
    await start_profile_edit(message, state)


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state):
    await state.clear()
    await message.answer("Операция отменена.")
    await send_main_menu(message)


def register_menu_handlers(dp):
    dp.include_router(router)
