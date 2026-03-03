import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

MONGO_URI = f"mongodb://{os.getenv('MONGO_HOST', 'localhost')}:{os.getenv('MONGO_PORT', 27017)}"
_client = None
_db = None


async def init_mongo():
    """Инициализирует MongoDB соединение при старте бота."""
    global _client, _db
    _client = AsyncIOMotorClient(
        MONGO_URI,
        maxPoolSize=10,
        minPoolSize=2,
        maxIdleTimeMS=30000,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=10000,
        waitQueueTimeoutMS=5000,
        retryWrites=True,
        retryReads=True,
        appname="art_bot_low_resource"
    )
    _db = _client[os.getenv("MONGO_DB_NAME", "art_bot")]
    try:
        await _client.admin.command('ping')
        logger.info("MongoDB connection initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
        raise


def get_db():
    """Возвращает базу данных (ленивая инициализация)."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_mongo() first.")
    return _db


async def close_mongo():
    """Корректно закрывает MongoDB соединение при остановке бота."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


async def ensure_user_exists(user):
    tg_id = user.id

    db = get_db()
    existing = await db.users.find_one({"tg_id": tg_id})
    if not existing:
        await db.users.insert_one({
            "tg_id": tg_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "created_at": int(__import__('time').time())
        })
    else:
        await db.users.update_one(
            {"tg_id": tg_id},
            {"$set": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username
            }}
        )