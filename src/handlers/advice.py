from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from config.constants import *
from src.bot.fsm import AdviceStates
from src.services.audit import log_action
from src.services.openrouter import get_ai_advice

router = Router()

MENU_BUTTONS = {
    MENU_ANON_MESSAGE,
    MENU_GET_ADVICE,
    MENU_SIGNUP_MEETING,
    MENU_UPDATE_PATH,
    MENU_VIEW_PROFILE
}


@router.message(lambda msg: msg.text == MENU_GET_ADVICE)
async def menu_advice(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await log_action(user_id, "request_advice", {})

    advice = await get_ai_advice("Привет! Я хочу получить поддержку.")
    await message.answer(advice)
    await state.set_state(AdviceStates.in_advice_mode)
    await message.answer("💬 Напишите своё сообщение, и я отвечу. Чтобы выйти — нажмите любую кнопку меню или /cancel.")


@router.message(AdviceStates.in_advice_mode, lambda msg: msg.text not in MENU_BUTTONS)
async def process_advice_message(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    user_id = message.from_user.id
    user_message = message.text

    await log_action(user_id, "advice_followup", {"message": user_message})
    advice = await get_ai_advice(user_message)
    await message.answer(advice)


def register_handlers(dp):
    dp.include_router(router)
