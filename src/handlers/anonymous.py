import asyncio
import logging

from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from src.bot.fsm import AnonymousStates
from src.services.audit import log_action
from src.services.email_sender import send_anonymous_email
from src.handlers.menu import send_main_menu_local
from src.services.rate_limiter import rate_limiter

router = Router()
logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 2000
EMAIL_TIMEOUT = 30


def rate_limit_middleware(handler):
    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = str(message.from_user.id)
        try:
            await rate_limiter.acquire(user_id)
            return await handler(message, *args, **kwargs)
        except asyncio.TimeoutError:
            logger.warning(f"Rate limit timeout for user {user_id} in anonymous handler")
            await message.answer("⏱️ Слишком много запросов. Пожалуйста, подождите немного.")
            return None
        except Exception as e:
            logger.error(f"Error in handler {handler.__name__}: {type(e).__name__}: {e}", exc_info=True)
            await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
            return None

    return wrapper


@router.message(AnonymousStates.waiting_for_message)
@rate_limit_middleware
async def process_anonymous_message(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    if not message.text or not message.text.strip():
        await message.answer("⚠️ Пожалуйста, введите текст сообщения.")
        return

    text = message.text.strip()

    if len(text) > MAX_MESSAGE_LENGTH:
        logger.warning(f"Anonymous message too long from user {user_id}: {len(text)} chars")
        await message.answer(
            f"⚠️ Сообщение слишком длинное (максимум {MAX_MESSAGE_LENGTH} символов). Пожалуйста, сократите.")
        return

    try:
        success = await asyncio.wait_for(
            send_anonymous_email(text),
            timeout=EMAIL_TIMEOUT
        )

        if success:
            await log_action(user_id, "anonymous_message", {"message_length": len(text)})
            logger.info(f"Anonymous message sent by user {user_id}")
            await state.clear()
            await message.answer("✅ Ваше сообщение отправлено анонимно руководителю. Спасибо!")
            await send_main_menu_local(message)
        else:
            logger.error(f"Failed to send anonymous message for user {user_id}")
            await state.clear()
            await message.answer("⚠️ Не удалось отправить сообщение. Попробуйте позже или обратитесь к руководителю.")
            await send_main_menu_local(message)

    except asyncio.TimeoutError:
        logger.error(f"Timeout sending anonymous message for user {user_id}")
        await state.clear()
        await message.answer("⏱️ Время ожидания истекло. Попробуйте позже.")
        await send_main_menu_local(message)

    except Exception as e:
        logger.error(f"Unexpected error in process_anonymous_message: {type(e).__name__}: {e}", exc_info=True)
        await state.clear()
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
        await send_main_menu_local(message)


def register_handlers(dp):
    dp.include_router(router)