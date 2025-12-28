from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from src.bot.fsm import AnonymousStates
from src.services.audit import log_action
from src.services.email_sender import send_anonymous_email

router = Router()


@router.message(AnonymousStates.waiting_for_message)
async def process_anonymous_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text or "Без текста"

    await send_anonymous_email(text)
    await log_action(user_id, "anonymous_message", {"message": text})

    await state.clear()
    await message.answer("Ваше сообщение отправлено анонимно руководителю. Спасибо!")
    from src.handlers.common import send_main_menu
    await send_main_menu(message)


def register_handlers(dp):
    dp.include_router(router)
