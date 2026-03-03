import asyncio
import logging

from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold

from config.constants import ALL_PROFILE_FIELDS, EDITABLE_FIELDS, MENU_VIEW_PROFILE
from src.bot.fsm import ProfileStates
from src.services.google_sheets import get_user_profile, update_user_field
from src.services.rate_limiter import rate_limiter
from src.utils.menu_utils import send_main_menu

router = Router()
logger = logging.getLogger(__name__)

PROFILE_TIMEOUT = 30
MAX_FIELD_VALUE_LENGTH = 5000


def rate_limit_middleware(handler):
    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = str(message.from_user.id)
        try:
            await rate_limiter.acquire(user_id)
            return await handler(message, *args, **kwargs)
        except asyncio.TimeoutError:
            logger.warning(f"Rate limit timeout for user {user_id} in profile handler")
            await message.answer("⏱️ Слишком много запросов. Пожалуйста, подождите немного.")
            return None
        except Exception as e:
            logger.error(f"Error in handler {handler.__name__}: {type(e).__name__}: {e}", exc_info=True)
            await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
            return None

    return wrapper


@router.message(lambda msg: msg.text == MENU_VIEW_PROFILE)
@rate_limit_middleware
async def show_profile(message: types.Message, **kwargs):
    user_id = message.from_user.id

    try:
        profile = await asyncio.wait_for(get_user_profile(user_id), timeout=PROFILE_TIMEOUT)

        if not profile:
            logger.warning(f"Profile not found for user {user_id}")
            await message.answer("Ваша анкета ещё не создана. Обратитесь к руководителю.")
            return

        text = "📄 Ваша анкета:\n\n"
        for field in ALL_PROFILE_FIELDS:
            value = profile.get(field, "—")
            text += f"📍 {hbold(f'{field}:')}\n{value}\n\n"

        await asyncio.wait_for(
            message.answer(text, parse_mode=ParseMode.HTML),
            timeout=10.0
        )
        logger.info(f"User {user_id} viewed their profile")

    except asyncio.TimeoutError:
        logger.error(f"Timeout loading profile for user {user_id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Error in show_profile: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Не удалось загрузить анкету. Попробуйте позже.")


async def start_profile_edit(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    try:
        buttons = [[types.KeyboardButton(text=field)] for field in EDITABLE_FIELDS]
        kb = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

        await asyncio.wait_for(
            message.answer("Какой блок вы хотите изменить?", reply_markup=kb),
            timeout=10.0
        )
        await state.set_state(ProfileStates.selecting_field)
        logger.info(f"User {user_id} entered profile edit mode")

    except asyncio.TimeoutError:
        logger.warning(f"Timeout in start_profile_edit for user {user_id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in start_profile_edit: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.message(ProfileStates.selecting_field)
@rate_limit_middleware
async def process_field_selection(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id

    logger.debug(f"process_field_selection called for user {user_id} with text = {message.text}")

    if message.text not in EDITABLE_FIELDS:
        logger.warning(f"Invalid field selection by user {user_id}: {message.text}")
        await message.answer("Пожалуйста, выберите поле из списка.")
        return

    try:
        await state.update_data(editing_field=message.text)
        await state.set_state(ProfileStates.editing_field)

        await asyncio.wait_for(
            message.answer(f"Введите новое значение для блока '{message.text}':"),
            timeout=10.0
        )
        logger.info(f"User {user_id} selected field to edit: {message.text}")

    except asyncio.TimeoutError:
        logger.warning(f"Timeout in process_field_selection for user {user_id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in process_field_selection: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.message(ProfileStates.editing_field)
@rate_limit_middleware
async def process_field_edit(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id
    user_text = message.text.strip() if message.text else ""

    data = await state.get_data()
    field = data.get("editing_field")

    if not field:
        logger.error(f"No editing_field in state for user {user_id}")
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, начните редактирование заново.")
        await state.clear()
        await send_main_menu(message)
        return

    if not user_text:
        await message.answer("⚠️ Пожалуйста, введите значение поля.")
        return

    if len(user_text) > MAX_FIELD_VALUE_LENGTH:
        logger.warning(f"Field value too long for user {user_id}: {len(user_text)} chars")
        await message.answer(
            f"⚠️ Значение слишком длинное (максимум {MAX_FIELD_VALUE_LENGTH} символов). Пожалуйста, сократите.")
        return

    try:
        success = await asyncio.wait_for(
            update_user_field(user_id, field, user_text),
            timeout=PROFILE_TIMEOUT
        )

        if success:
            logger.info(f"User {user_id} updated field '{field}' successfully")
            await message.answer("✅ Анкета обновлена!")
        else:
            logger.error(f"Failed to update field '{field}' for user {user_id}")
            await message.answer("❌ Не удалось обновить анкету. Обратитесь к руководителю.")

        await state.clear()
        await send_main_menu(message)

    except asyncio.TimeoutError:
        logger.error(f"Timeout updating field '{field}' for user {user_id}")
        await message.answer("⏱️ Превышено время ожидания. Попробуйте позже.")
        await state.clear()
        await send_main_menu(message)
    except Exception as e:
        logger.error(f"Error in process_field_edit: {type(e).__name__}: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
        await state.clear()
        await send_main_menu(message)


def register_handlers(dp):
    dp.include_router(router)