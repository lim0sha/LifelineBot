import asyncio
import os
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config.constants import ALL_PROFILE_FIELDS

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOCAL_CREDENTIALS = PROJECT_ROOT / "google_credentials.json"
CREDS_PATH_FROM_ENV = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")

if CREDS_PATH_FROM_ENV:
    creds_path = Path(CREDS_PATH_FROM_ENV)
else:
    creds_path = LOCAL_CREDENTIALS

if not creds_path.exists():
    if LOCAL_CREDENTIALS.exists():
        creds_path = LOCAL_CREDENTIALS
    else:
        raise FileNotFoundError(f"Google credentials not found at {creds_path} or {LOCAL_CREDENTIALS}")


def get_sheets_service():
    creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    return service


async def get_user_profile(tg_id: int):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_get_user_profile, tg_id)


async def update_user_field(tg_id: int, field_name: str, new_value: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_update_user_field, tg_id, field_name, new_value)


def _sync_get_user_profile(tg_id: int):
    service = get_sheets_service()
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId=SHEET_ID, range="A1:Z1000").execute()
    values = result.get("values", [])

    if not values:
        return None

    headers = values[0]
    if "telegram_id" not in headers:
        return None

    tg_id_col = headers.index("telegram_id")
    for i, row in enumerate(values[1:], start=2):
        if len(row) > tg_id_col and str(row[tg_id_col]) == str(tg_id):
            profile = {}
            for j, header in enumerate(headers):
                profile[header] = row[j] if j < len(row) else ""
            profile["_row_index"] = i
            return profile

    return None


def _sync_update_user_field(tg_id: int, field_name: str, new_value: str):
    profile = _sync_get_user_profile(tg_id)
    if not profile:
        return False

    row_index = profile["_row_index"]
    headers = list(profile.keys())
    if "_row_index" in headers:
        headers.remove("_row_index")

    try:
        col_index = headers.index(field_name)
    except ValueError:
        return False

    col_letter = _index_to_column_letter(col_index)

    service = get_sheets_service()
    range_name = f"{col_letter}{row_index}"

    body = {
        "values": [[new_value]]
    }
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=range_name,
        valueInputOption="RAW",
        body=body
    ).execute()

    return True


def _sync_create_user_profile(tg_id: int, profile_name: str = "", username: str = ""):
    service = get_sheets_service()
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId=SHEET_ID, range="A1:Z1000").execute()
    values = result.get("values", [])

    expected_headers = ["telegram_id"] + ALL_PROFILE_FIELDS

    if not values:
        sheet.values().update(
            spreadsheetId=SHEET_ID,
            range="A1",
            valueInputOption="RAW",
            body={"values": [expected_headers]}
        ).execute()
        next_row = 2
    else:
        headers = values[0]
        if headers != expected_headers:
            raise ValueError(
                f"Заголовки таблицы не совпадают!\n"
                f"Ожидались: {expected_headers}\n"
                f"Фактические: {headers}"
            )
        next_row = len(values) + 1

    new_row = [str(tg_id)] + [""] * len(ALL_PROFILE_FIELDS)

    if username:
        new_row[1] = username

    if profile_name and "profile_name" in ALL_PROFILE_FIELDS:
        profile_name_index = ALL_PROFILE_FIELDS.index("profile_name") + 1
        new_row[profile_name_index] = profile_name

    sheet.values().update(
        spreadsheetId=SHEET_ID,
        range=f"A{next_row}",
        valueInputOption="RAW",
        body={"values": [new_row]}
    ).execute()

    return True


async def create_user_profile(tg_id: int, profile_name: str = "", username: str = ""):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_create_user_profile, tg_id, profile_name, username)


def _index_to_column_letter(index: int) -> str:
    letters = []
    while index >= 0:
        letters.append(chr(ord('A') + (index % 26)))
        index = index // 26 - 1
    return ''.join(reversed(letters))
