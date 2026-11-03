from pymongo.errors import PyMongoError

from .domain import ServiceError, now

# Existing tickets remain in their original collection. New prototype data is separate.
COLLECTIONS = {"tickets": "tickets", **{k: f"demo_{k}" for k in
               ["users", "devices", "requests", "audit", "chats", "knowledge", "servicenow"]}}


class MongoStore:
    def __init__(self, database):
        self.db = database

    async def ping(self):
        try:
            await self.db.command("ping")
        except PyMongoError:
            raise ServiceError("MongoDB is unavailable. No successful save can be confirmed.") from None

    async def insert(self, collection, document):
        try:
            await self.db[COLLECTIONS[collection]].insert_one(dict(document))
        except PyMongoError:
            raise ServiceError("Database write failed. Check MongoDB connectivity; do not assume this operation succeeded.") from None
        return {k: v for k, v in document.items() if k != "_id"}

    async def get(self, collection, key):
        try:
            return await self.db[COLLECTIONS[collection]].find_one({"_id": key}, {"_id": 0})
        except PyMongoError:
            raise ServiceError("Database record could not be retrieved.") from None

    async def update(self, collection, key, values):
        try:
            result = await self.db[COLLECTIONS[collection]].update_one(
                {"_id": key}, {"$set": {**values, "updated_at": now()}})
            if result.matched_count != 1:
                raise ServiceError("Record to update was not found.", 404)
        except PyMongoError:
            raise ServiceError("Database update could not be confirmed.") from None
        return await self.get(collection, key)

    async def list(self, collection, query=None, limit=100):
        try:
            cursor = self.db[COLLECTIONS[collection]].find(query or {}, {"_id": 0}).sort("created_at", -1).limit(limit)
            return [record async for record in cursor]
        except PyMongoError:
            raise ServiceError("Database records could not be listed.") from None

    async def count(self, collection, query=None):
        try:
            return await self.db[COLLECTIONS[collection]].count_documents(query or {})
        except PyMongoError:
            raise ServiceError("Database metrics could not be read.") from None

    async def seed(self):
        from .domain import DEMO_DEVICE, DEMO_USER
        # $setOnInsert keeps existing demo state across restarts.
        for collection, key, data in [
            ("users", DEMO_USER, {"user_id": DEMO_USER, "name": "Avinash (demo)",
                                 "password_expired": True, "locked": True, "reset_count": 0}),
            ("devices", DEMO_DEVICE, {"device_id": DEMO_DEVICE, "installed_software": [], "owner": DEMO_USER}),
        ]:
            try:
                await self.db[COLLECTIONS[collection]].update_one(
                    {"_id": key}, {"$setOnInsert": {**data, "is_demo": True, "created_at": now()}}, upsert=True)
            except PyMongoError:
                raise ServiceError("Demo identity could not be initialised.") from None

    async def reset_demo(self):
        # Fixed collection names and a fixed predicate: never delete legacy tickets.
        counts = {}
        try:
            for key, name in COLLECTIONS.items():
                if key == "knowledge":
                    continue
                result = await self.db[name].delete_many({"is_demo": True})
                counts[name] = result.deleted_count
        except PyMongoError:
            raise ServiceError("Demo reset was interrupted; run it again after restoring the database.") from None
        await self.seed()
        return counts
