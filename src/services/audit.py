import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from .db import get_db

_LOG_QUEUE_MAX_SIZE = 1000
_log_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=_LOG_QUEUE_MAX_SIZE)
_batch_size = 50
_flush_interval = 2.0
_flush_task: Optional[asyncio.Task] = None
_logs_dropped = 0

logger = logging.getLogger(__name__)

_audit_logs: Optional[AsyncIOMotorCollection] = None


def get_audit_logs() -> AsyncIOMotorCollection:
    """Возвращает коллекцию audit_logs (ленивая инициализация)."""
    global _audit_logs
    if _audit_logs is None:
        db = get_db()
        if db is None:
            raise RuntimeError("Database not initialized. Call init_mongo() first.")
        _audit_logs = db.audit_logs
    return _audit_logs


async def init_audit_ttl_index():
    try:
        audit_logs = get_audit_logs()
        await audit_logs.create_index("timestamp", expireAfterSeconds=24 * 3600)
        logger.info("Audit TTL index created successfully.")
    except Exception as e:
        if "already exists" not in str(e).lower():
            logger.error(f"Failed to create audit TTL index: {e}", exc_info=True)
            raise


async def _flush_logs():
    batch = []
    retry_count = 0
    max_retries = 3

    while True:
        try:
            try:
                log_entry = await asyncio.wait_for(
                    _log_queue.get(),
                    timeout=_flush_interval
                )
                batch.append(log_entry)
                _log_queue.task_done()
            except asyncio.TimeoutError:
                pass

            if len(batch) >= _batch_size or (batch and _log_queue.empty()):
                if batch:
                    for attempt in range(max_retries):
                        try:
                            audit_logs = get_audit_logs()
                            await asyncio.wait_for(
                                audit_logs.insert_many(batch, ordered=False),
                                timeout=10.0
                            )
                            logger.debug(f"Flushed {len(batch)} audit logs.")
                            batch.clear()
                            retry_count = 0
                            break
                        except (PyMongoError, ServerSelectionTimeoutError) as e:
                            retry_count += 1
                            if attempt < max_retries - 1:
                                delay = 1 * (2 ** attempt)
                                logger.warning(
                                    f"Audit flush failed (attempt {attempt + 1}/{max_retries}), "
                                    f"retrying in {delay}s: {e}"
                                )
                                await asyncio.sleep(delay)
                            else:
                                logger.error(
                                    f"Audit flush failed after {max_retries} attempts: {e}",
                                    exc_info=True
                                )
                                batch.clear()
                    await asyncio.sleep(0)

        except asyncio.CancelledError:
            if batch:
                try:
                    audit_logs = get_audit_logs()
                    await asyncio.wait_for(
                        audit_logs.insert_many(batch, ordered=False),
                        timeout=10.0
                    )
                    logger.info(f"Flushed remaining {len(batch)} audit logs on shutdown.")
                except Exception as e:
                    logger.error(f"Failed to flush remaining audit logs: {e}", exc_info=True)
            break
        except Exception as e:
            logger.error(f"Unexpected error in _flush_logs: {e}", exc_info=True)
            await asyncio.sleep(1)


async def log_action(tg_id: int, action_type: str, payload: Dict[str, Any]):
    global _flush_task, _logs_dropped

    if _flush_task is None or _flush_task.done():
        _flush_task = asyncio.create_task(_flush_logs())

    if not isinstance(tg_id, int) or tg_id <= 0:
        logger.warning(f"Invalid tg_id in log_action: {tg_id}")
        return

    if not isinstance(action_type, str) or len(action_type) > 100:
        logger.warning(f"Invalid action_type in log_action: {action_type}")
        return

    if not isinstance(payload, dict):
        logger.warning(f"Invalid payload type in log_action: {type(payload)}")
        payload = {}

    if len(str(payload)) > 10000:
        logger.warning(f"Payload too large for log_action, truncating: {len(str(payload))} bytes")
        payload = {"truncated": True, "reason": "payload_too_large"}

    entry = {
        "tg_id": tg_id,
        "action": action_type,
        "timestamp": datetime.now(timezone.utc),
        "payload": payload
    }

    try:
        _log_queue.put_nowait(entry)
    except asyncio.QueueFull:
        _logs_dropped += 1
        if _logs_dropped % 100 == 0:
            logger.error(f"Audit log queue full, dropped {_logs_dropped} logs total.")


async def close_audit_logger():
    global _flush_task
    if _flush_task and not _flush_task.done():
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
    logger.info("Audit logger closed.")


def get_audit_stats() -> Dict[str, int]:
    return {
        "queue_size": _log_queue.qsize(),
        "logs_dropped": _logs_dropped,
        "max_queue_size": _LOG_QUEUE_MAX_SIZE
    }
