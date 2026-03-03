import asyncio
import logging
import os
from typing import Optional, Dict, Any

import aiohttp

from config.system_prompts import ADVICE_SYSTEM_PROMPT

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT = 60
MAX_RETRIES = 3
SEMAPHORE_LIMIT = 2
MAX_PROMPT_LENGTH = 4000

logger = logging.getLogger(__name__)
_session: Optional[aiohttp.ClientSession] = None
_semaphore: Optional[asyncio.Semaphore] = None
_init_lock: Optional[asyncio.Lock] = None
_stats: Dict[str, int] = {
    "requests_total": 0,
    "requests_success": 0,
    "requests_failed": 0,
    "retries_total": 0,
}


async def init_openrouter_session():
    global _session, _semaphore, _init_lock

    async with _get_init_lock():
        if _session is None or _session.closed:
            connector = aiohttp.TCPConnector(
                limit=SEMAPHORE_LIMIT * 2,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )

            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

            _session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "HTTP-Referer": "https://github.com/lim0sha/LifelineBot",
                    "X-Title": "ART Lifeline Bot"
                }
            )
            _semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
            logger.info("OpenRouter session initialized successfully.")


def _get_init_lock() -> asyncio.Lock:
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    return _init_lock


async def close_openrouter_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
        logger.info("OpenRouter session closed.")


def get_session() -> aiohttp.ClientSession:
    if _session is None or _session.closed:
        raise RuntimeError("OpenRouter session not initialized. Call init_openrouter_session() first.")
    return _session


def get_semaphore() -> asyncio.Semaphore:
    if _semaphore is None:
        raise RuntimeError("OpenRouter semaphore not initialized.")
    return _semaphore


def get_openrouter_stats() -> Dict[str, int]:
    return _stats.copy()


async def health_check_openrouter() -> bool:
    try:
        session = get_session()
        async with session.get("https://openrouter.ai/api/v1/models", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            return resp.status == 200
    except Exception as e:
        logger.warning(f"OpenRouter health check failed: {e}")
        return False


async def get_ai_advice(prompt: str, model: Optional[str] = None) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set in environment")
        return "Сервис советов временно недоступен. Попробуйте позже."

    if not prompt or not prompt.strip():
        logger.warning("Empty prompt received in get_ai_advice")
        return "Пожалуйста, задайте конкретный вопрос."

    if len(prompt) > MAX_PROMPT_LENGTH:
        logger.warning(f"Prompt too long: {len(prompt)} chars, truncating to {MAX_PROMPT_LENGTH}")
        prompt = prompt[:MAX_PROMPT_LENGTH]

    model_name = model or os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free")

    _stats["requests_total"] += 1

    async with get_semaphore():
        for attempt in range(MAX_RETRIES):
            try:
                session = get_session()
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                async with session.post(
                        url=OPENROUTER_URL,
                        headers=headers,
                        json={
                            "model": model_name,
                            "messages": [
                                {"role": "system", "content": ADVICE_SYSTEM_PROMPT},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 500
                        }
                ) as resp:
                    if resp.status == 200:
                        data = await asyncio.wait_for(resp.json(), timeout=10)
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        if content:
                            _stats["requests_success"] += 1
                            logger.debug(f"AI advice received for prompt: {prompt[:50]}...")
                            return content
                        else:
                            logger.warning("Empty response from OpenRouter API")
                            _stats["requests_failed"] += 1
                            return "Извините, не удалось сформировать ответ. Попробуйте перефразировать."

                    elif resp.status in [429, 502, 503, 504]:
                        _stats["retries_total"] += 1
                        if attempt < MAX_RETRIES - 1:
                            wait_time = 1 * (2 ** attempt)
                            logger.warning(
                                f"OpenRouter returned {resp.status}, retry {attempt + 1}/{MAX_RETRIES} in {wait_time}s"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"OpenRouter API error after {MAX_RETRIES} attempts: {resp.status}")
                            _stats["requests_failed"] += 1
                            return "Сервис перегружен. Попробуйте через минуту."

                    else:
                        error_text = await asyncio.wait_for(resp.text(), timeout=10)
                        logger.error(f"OpenRouter API error {resp.status}: {error_text[:200]}")
                        _stats["requests_failed"] += 1
                        return "Извините, сейчас не могу дать совет. Попробуйте позже."

            except asyncio.TimeoutError:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{MAX_RETRIES})")
                _stats["retries_total"] += 1
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (2 ** attempt))
                    continue
                _stats["requests_failed"] += 1
                return "Время ожидания ответа истекло. Попробуйте позже."

            except aiohttp.ClientError as e:
                logger.error(f"Network error: {e}")
                _stats["retries_total"] += 1
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                _stats["requests_failed"] += 1
                return "Ошибка соединения. Проверьте интернет и попробуйте снова."

            except Exception as e:
                logger.error(f"Unexpected error in get_ai_advice: {type(e).__name__}: {e}", exc_info=True)
                _stats["retries_total"] += 1
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                _stats["requests_failed"] += 1
                return "Произошла непредвиденная ошибка. Попробуйте позже."

    _stats["requests_failed"] += 1
    logger.error("All retry attempts failed for get_ai_advice")
    return "Сервис временно недоступен. Попробуйте позже."
