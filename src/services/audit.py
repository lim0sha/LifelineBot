from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorCollection

from .db import db

audit_logs: AsyncIOMotorCollection = db.audit_logs


async def init_audit_ttl_index():
    await audit_logs.create_index("timestamp", expireAfterSeconds=30 * 24 * 3600)


async def log_action(tg_id: int, action_type: str, payload: dict):
    await audit_logs.insert_one({
        "tg_id": tg_id,
        "action": action_type,
        "timestamp": datetime.utcnow(),
        "payload": payload
    })
