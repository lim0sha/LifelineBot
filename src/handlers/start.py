import asyncio
import logging

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from src.services.db import ensure_user_exists
from src.services.google_sheets import get_user_profile, create_user_profile
from src.services.rate_limiter import rate_limiter
from src.utils.menu_utils import send_main_menu

router = Router()
logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 100
MESSAGE_TIMEOUT = 10


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


class RegistrationStates(StatesGroup):
    waiting_for_full_name = State()


@router.message(lambda msg: msg.text and msg.text.startswith("/start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Обработчик команды /start.
    """
    user = message.from_user
    tg_id = user.id

    try:
        await asyncio.wait_for(ensure_user_exists(user), timeout=10.0)
        profile = await asyncio.wait_for(get_user_profile(tg_id), timeout=10.0)

        if profile:
            logger.info(f"Existing user logged in: tg_id={tg_id}")
            await asyncio.wait_for(
                message.answer(
                    f"Привет, {user.first_name}! 👋\nРады видеть тебя снова!",
                    reply_markup=types.ReplyKeyboardRemove()
                ),
                timeout=MESSAGE_TIMEOUT
            )
            await send_main_menu(message)
        else:
            full_name = ""
            if user.first_name and user.last_name:
                full_name = f"{user.first_name} {user.last_name}"
            elif user.first_name:
                full_name = user.first_name

            if full_name:
                if len(full_name) > MAX_NAME_LENGTH:
                    logger.warning(f"Name too long for user {tg_id}: {len(full_name)} chars")
                    full_name = full_name[:MAX_NAME_LENGTH]

                success = await asyncio.wait_for(
                    create_user_profile(tg_id, full_name, user.username or ""),
                    timeout=10.0
                )
                if success:
                    logger.info(f"New user registered: tg_id={tg_id}, name={full_name}")
                    await asyncio.wait_for(
                        message.answer(
                            f"Привет, {full_name}! 👋\nТвоя анкета создана. Добро пожаловать в проект «АРТ. Путь.»!",
                            reply_markup=types.ReplyKeyboardRemove()
                        ),
                        timeout=MESSAGE_TIMEOUT
                    )
                    await send_main_menu(message)
                else:
                    logger.error(f"Failed to create profile for tg_id={tg_id}")
                    await asyncio.wait_for(
                        message.answer(
                            "⚠️ Не удалось создать анкету. Попробуйте позже или обратитесь к руководителю.",
                            reply_markup=types.ReplyKeyboardRemove()
                        ),
                        timeout=MESSAGE_TIMEOUT
                    )
            else:
                await state.set_state(RegistrationStates.waiting_for_full_name)
                logger.info(f"User {tg_id} prompted for full name")
                await asyncio.wait_for(
                    message.answer(
                        "Привет! 👋\nПожалуйста, напиши своё **имя и фамилию** (например, Иван Иванов)."
                    ),
                    timeout=MESSAGE_TIMEOUT
                )

    except asyncio.TimeoutError:
        logger.error(f"Timeout in cmd_start for user {tg_id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Unexpected error in cmd_start: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.message(RegistrationStates.waiting_for_full_name)
@rate_limit_middleware
async def process_full_name(message: types.Message, state: FSMContext):
    full_name = message.text.strip()

    if not full_name:
        await message.answer("⚠️ Пожалуйста, введите хотя бы имя.")
        return

    if len(full_name) > MAX_NAME_LENGTH:
        logger.warning(f"Name too long from user {message.from_user.id}: {len(full_name)} chars")
        await message.answer(f"⚠️ Имя слишком длинное (максимум {MAX_NAME_LENGTH} символов). Пожалуйста, сократите.")
        return

    try:
        success = await asyncio.wait_for(
            create_user_profile(message.from_user.id, full_name, message.from_user.username or ""),
            timeout=10.0
        )

        if success:
            logger.info(f"Profile created for user {message.from_user.id}: {full_name}")
            await state.clear()
            await asyncio.wait_for(
                message.answer(
                    f"Спасибо, {full_name}! ✨\nТеперь ты в регистре проекта «АРТ. Путь.»!",
                    reply_markup=types.ReplyKeyboardRemove()
                ),
                timeout=MESSAGE_TIMEOUT
            )
            await send_main_menu(message)
        else:
            logger.error(f"Failed to create profile for user {message.from_user.id}")
            await message.answer("⚠️ Не удалось создать анкету. Попробуйте позже.")

    except asyncio.TimeoutError:
        logger.error(f"Timeout in process_full_name for user {message.from_user.id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Unexpected error in process_full_name: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


def register_handlers(dp):
    dp.include_router(router)
