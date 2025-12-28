import os

from aiogram.types import User
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = f"mongodb://{os.getenv('MONGO_HOST', 'localhost')}:{os.getenv('MONGO_PORT', 27017)}"
client = AsyncIOMotorClient(
    MONGO_URI,
    maxPoolSize=100,
    minPoolSize=10,
    maxIdleTimeMS=30000,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000
)
db = client[os.getenv("MONGO_DB_NAME", "art_bot")]


async def ensure_user_exists(user: User):
    existing = await db.users.find_one({"tg_id": user.id})
    if not existing:
        await db.users.insert_one({
            "tg_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "created_at": user.id
        })
    else:
        await db.users.update_one(
            {"tg_id": user.id},
            {"$set": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username
            }}
        )
