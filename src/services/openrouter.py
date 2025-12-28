import asyncio
import os

import aiohttp

from config.system_prompts import ADVICE_SYSTEM_PROMPT


async def get_ai_advice(prompt: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free")

    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": ADVICE_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ]
                    }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    return "Извините, сейчас не могу дать совет. Попробуйте позже."
        except asyncio.TimeoutError:
            return "Время ожидания ответа от сервиса советов истекло. Попробуйте позже."
        except Exception as e:
            return "Ошибка при получении совета. Попробуйте позже."
