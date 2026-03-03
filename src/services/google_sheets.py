import asyncio
import functools
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.constants import ALL_PROFILE_FIELDS

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOCAL_CREDENTIALS = PROJECT_ROOT / "google_credentials.json"
CREDS_PATH_FROM_ENV = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")

_PROFILE_CACHE: Dict[int, Tuple[float, dict]] = {}
CACHE_TTL = 300
CACHE_MAX_SIZE = 1000
_GOOGLE_API_SEMAPHORE = asyncio.Semaphore(2)
_GOOGLE_API_TIMEOUT = 30
logger = logging.getLogger(__name__)


def _get_creds_path() -> Path:
    if CREDS_PATH_FROM_ENV:
        creds_path = Path(CREDS_PATH_FROM_ENV)
        if creds_path.exists():
            return creds_path
    if LOCAL_CREDENTIALS.exists():
        return LOCAL_CREDENTIALS
    raise FileNotFoundError(
        f"Google credentials not found at {CREDS_PATH_FROM_ENV or 'N/A'} "
        f"or {LOCAL_CREDENTIALS}"
    )


def _get_sheets_service_sync():
    creds_path = _get_creds_path()
    creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _sync_get_user_profile(tg_id: int) -> Optional[dict]:
    service = _get_sheets_service_sync()
    sheet = service.spreadsheets()

    result = sheet.values().get(
        spreadsheetId=SHEET_ID, range="A1:Z1000"
    ).execute()
    values = result.get("values", [])

    if not values:
        logger.warning(f"No data found in sheet for tg_id={tg_id}")
        return None

    headers = values[0]
    if "telegram_id" not in headers:
        logger.error("Column 'telegram_id' not found in sheet headers")
        return None

    tg_id_col = headers.index("telegram_id")
    for i, row in enumerate(values[1:], start=2):
        if len(row) > tg_id_col and str(row[tg_id_col]) == str(tg_id):
            profile = {}
            for j, header in enumerate(headers):
                profile[header] = row[j] if j < len(row) else ""
            profile["_row_index"] = i
            logger.debug(f"Found profile for tg_id={tg_id} at row {i}")
            return profile

    logger.info(f"Profile not found for tg_id={tg_id}")
    return None


async def get_user_profile(tg_id: int) -> Optional[dict]:
    if tg_id in _PROFILE_CACHE:
        cache_time, cached_data = _PROFILE_CACHE[tg_id]
        if time.time() - cache_time < CACHE_TTL:
            logger.debug(f"Cache hit for tg_id={tg_id}")
            return cached_data

    async with _GOOGLE_API_SEMAPHORE:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_running_loop()
                profile = await asyncio.wait_for(
                    loop.run_in_executor(None, _sync_get_user_profile, tg_id),
                    timeout=_GOOGLE_API_TIMEOUT
                )
                if profile:
                    _PROFILE_CACHE[tg_id] = (time.time(), profile)
                    if len(_PROFILE_CACHE) > CACHE_MAX_SIZE:
                        oldest_key = min(_PROFILE_CACHE, key=lambda k: _PROFILE_CACHE[k][0])
                        del _PROFILE_CACHE[oldest_key]
                        logger.debug(f"Evicted oldest cache entry for tg_id={oldest_key}")
                    logger.debug(f"Cached profile for tg_id={tg_id}")
                return profile

            except asyncio.TimeoutError:
                logger.warning(f"Google Sheets timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (2 ** attempt))
                    continue
                return None

            except HttpError as e:
                if e.resp.status in [429, 500, 503]:
                    if attempt < max_retries - 1:
                        delay = 1 * (2 ** attempt)
                        logger.warning(
                            f"Retryable error, attempt {attempt + 1}/{max_retries}, "
                            f"waiting {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)
                        continue
                logger.error(f"HTTP error in get_user_profile: {e}", exc_info=True)
                return None
            except Exception as e:
                logger.error(
                    f"Unexpected error in get_user_profile, attempt {attempt + 1}: {e}",
                    exc_info=True,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                return None

    return None


def _sync_update_user_field(tg_id: int, field_name: str, new_value: str) -> bool:
    profile = _sync_get_user_profile(tg_id)
    if not profile:
        logger.warning(f"Cannot update: profile not found for tg_id={tg_id}")
        return False

    row_index = profile["_row_index"]
    headers = [k for k in profile.keys() if k != "_row_index"]

    try:
        col_index = headers.index(field_name)
    except ValueError:
        logger.error(f"Field '{field_name}' not found in headers: {headers}")
        return False

    col_letter = _index_to_column_letter(col_index)
    range_name = f"{col_letter}{row_index}"

    service = _get_sheets_service_sync()
    body = {"values": [[new_value]]}

    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=range_name,
        valueInputOption="RAW",
        body=body,
    ).execute()

    if tg_id in _PROFILE_CACHE:
        del _PROFILE_CACHE[tg_id]
        logger.debug(f"Invalidated cache for tg_id={tg_id}")

    logger.info(
        f"Updated field '{field_name}' for tg_id={tg_id} at {range_name}"
    )
    return True


async def update_user_field(tg_id: int, field_name: str, new_value: str) -> bool:
    async with _GOOGLE_API_SEMAPHORE:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, _sync_update_user_field, tg_id, field_name, new_value
                    ),
                    timeout=_GOOGLE_API_TIMEOUT
                )
                return result

            except asyncio.TimeoutError:
                logger.warning(f"Google Sheets timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (2 ** attempt))
                    continue
                return False

            except HttpError as e:
                if e.resp.status in [429, 500, 503]:
                    if attempt < max_retries - 1:
                        delay = 1 * (2 ** attempt)
                        logger.warning(
                            f"Retryable error, attempt {attempt + 1}/{max_retries}, "
                            f"waiting {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)
                        continue
                logger.error(f"HTTP error in update_user_field: {e}", exc_info=True)
                return False
            except Exception as e:
                logger.error(
                    f"Unexpected error in update_user_field, attempt {attempt + 1}: {e}",
                    exc_info=True,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                return False

    return False


def _sync_create_user_profile(
        tg_id: int, profile_name: str = "", username: str = ""
) -> bool:
    service = _get_sheets_service_sync()
    sheet = service.spreadsheets()

    result = sheet.values().get(
        spreadsheetId=SHEET_ID, range="A1:Z1000"
    ).execute()
    values = result.get("values", [])

    expected_headers = ["telegram_id"] + ALL_PROFILE_FIELDS

    if not values:
        logger.info("Sheet is empty, creating headers...")
        sheet.values().update(
            spreadsheetId=SHEET_ID,
            range="A1",
            valueInputOption="RAW",
            body={"values": [expected_headers]},
        ).execute()
        next_row = 2
    else:
        headers = values[0]
        if headers != expected_headers:
            error_msg = (
                f"Headers mismatch!\nExpected: {expected_headers}\n"
                f"Actual: {headers}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        next_row = len(values) + 1

    new_row = [str(tg_id)] + [""] * len(ALL_PROFILE_FIELDS)

    if username:
        if "username" in ALL_PROFILE_FIELDS:
            idx = ALL_PROFILE_FIELDS.index("username") + 1
            new_row[idx] = username

    if profile_name and "profile_name" in ALL_PROFILE_FIELDS:
        idx = ALL_PROFILE_FIELDS.index("profile_name") + 1
        new_row[idx] = profile_name

    sheet.values().update(
        spreadsheetId=SHEET_ID,
        range=f"A{next_row}",
        valueInputOption="RAW",
        body={"values": [new_row]},
    ).execute()

    logger.info(f"Created profile for tg_id={tg_id} at row {next_row}")
    return True


async def create_user_profile(
        tg_id: int, profile_name: str = "", username: str = ""
) -> bool:
    async with _GOOGLE_API_SEMAPHORE:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        _sync_create_user_profile,
                        tg_id,
                        profile_name,
                        username,
                    ),
                    timeout=_GOOGLE_API_TIMEOUT
                )
                return result

            except asyncio.TimeoutError:
                logger.warning(f"Google Sheets timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (2 ** attempt))
                    continue
                return False

            except HttpError as e:
                if e.resp.status in [429, 500, 503]:
                    if attempt < max_retries - 1:
                        delay = 1 * (2 ** attempt)
                        logger.warning(
                            f"Retryable error, attempt {attempt + 1}/{max_retries}, "
                            f"waiting {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)
                        continue
                logger.error(f"HTTP error in create_user_profile: {e}", exc_info=True)
                return False
            except Exception as e:
                logger.error(
                    f"Unexpected error in create_user_profile, attempt {attempt + 1}: {e}",
                    exc_info=True,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                return False

    return False


@functools.lru_cache(maxsize=128)
def _index_to_column_letter(index: int) -> str:
    letters = []
    while index >= 0:
        letters.append(chr(ord("A") + (index % 26)))
        index = index // 26 - 1
    return "".join(reversed(letters))


def close_google_sheets_service():
    """Очищает кэш при остановке бота."""
    global _PROFILE_CACHE
    cache_size = len(_PROFILE_CACHE)
    _PROFILE_CACHE.clear()
    logger.info(f"Google Sheets service closed, cleared {cache_size} cache entries.")


def get_google_sheets_stats() -> Dict[str, Any]:
    """Возвращает статистику по кэшу Google Sheets."""
    return {
        "cache_size": len(_PROFILE_CACHE),
        "cache_max_size": CACHE_MAX_SIZE,
        "cache_ttl": CACHE_TTL,
        "semaphore_limit": _GOOGLE_API_SEMAPHORE._value,
    }