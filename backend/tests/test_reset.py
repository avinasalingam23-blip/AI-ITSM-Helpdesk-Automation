from types import SimpleNamespace

from helpdesk.domain import DEMO_USER
from helpdesk.store import COLLECTIONS, MongoStore


class ResetCollection:
    def __init__(self):
        self.rows = [{"_id": "legacy", "title": "Must survive"}, {"_id": "demo", "is_demo": True}]

    async def delete_many(self, query):
        assert query == {"is_demo": True}
        deleted = sum(r.get("is_demo") is True for r in self.rows)
        self.rows = [r for r in self.rows if r.get("is_demo") is not True]
        return SimpleNamespace(deleted_count=deleted)

    async def update_one(self, query, update, upsert=False):
        assert upsert is True
        if not any(r["_id"] == query["_id"] for r in self.rows):
            self.rows.append({**query, **update["$setOnInsert"]})


async def test_reset_preserves_unlabelled_records_and_knowledge():
    db = {name: ResetCollection() for name in COLLECTIONS.values()}
    await MongoStore(db).reset_demo()
    assert db["tickets"].rows == [{"_id": "legacy", "title": "Must survive"}]
    assert len(db["demo_knowledge"].rows) == 2
    user = next(r for r in db["demo_users"].rows if r["_id"] == DEMO_USER)
    assert user["password_expired"] is True and user["locked"] is True
