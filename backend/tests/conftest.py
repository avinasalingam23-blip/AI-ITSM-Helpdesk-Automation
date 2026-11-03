from copy import deepcopy
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from helpdesk.config import Settings
from helpdesk.domain import DEMO_DEVICE, DEMO_USER, ServiceError, classify, now
from helpdesk.rag import load_articles
from main import create_app


class MemoryStore:
    """Explicit test double. The deployed application never falls back to memory."""
    def __init__(self):
        self.data = {k: {} for k in ["tickets", "users", "devices", "audit", "requests", "chats", "knowledge", "servicenow"]}
        self.offline = False
        self.ignore_state_changes = False
        self.fail_mock_update = False
        self.fail_audit = False

    async def ping(self):
        if self.offline:
            raise ServiceError("Database unavailable.")

    async def insert(self, collection, doc):
        await self.ping()
        if collection == "audit" and self.fail_audit:
            raise ServiceError("Audit storage unavailable.")
        if doc["_id"] in self.data[collection]:
            raise ServiceError("Duplicate test record.")
        self.data[collection][doc["_id"]] = deepcopy(doc)
        return {k: v for k, v in deepcopy(doc).items() if k != "_id"}

    async def get(self, collection, key):
        await self.ping()
        doc = deepcopy(self.data[collection].get(key))
        return {k: v for k, v in doc.items() if k != "_id"} if doc else None

    async def update(self, collection, key, values):
        await self.ping()
        if collection == "servicenow" and self.fail_mock_update:
            raise ServiceError("Mock ServiceNow outage.")
        if key not in self.data[collection]:
            raise ServiceError("Not found.", 404)
        if not (self.ignore_state_changes and collection in {"users", "devices"}):
            self.data[collection][key].update(deepcopy(values), updated_at=now())
        return await self.get(collection, key)

    @staticmethod
    def matches(record, query):
        return all(record.get(k) == v for k, v in (query or {}).items())

    async def list(self, collection, query=None, limit=100):
        await self.ping()
        rows = [deepcopy(v) for v in self.data[collection].values() if self.matches(v, query)]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return [{k: v for k, v in row.items() if k != "_id"} for row in rows[:limit]]

    async def count(self, collection, query=None):
        await self.ping()
        return sum(self.matches(v, query) for v in self.data[collection].values())

    async def seed(self):
        await self.ping()
        self.data["users"].setdefault(DEMO_USER, dict(_id=DEMO_USER, user_id=DEMO_USER, name="Avinash (demo)", password_expired=True, locked=True, reset_count=0, is_demo=True))
        self.data["devices"].setdefault(DEMO_DEVICE, dict(_id=DEMO_DEVICE, device_id=DEMO_DEVICE, owner=DEMO_USER, installed_software=[], is_demo=True))


class FakeAI:
    def __init__(self):
        self.articles = load_articles()
        self.low_confidence = False
        self.unavailable = False
        self.invalid_proposal = False
        self.generation_failed = False

    def info(self):
        return {"status": "test_double", "chunks": 24}

    def propose(self, message):
        if self.unavailable:
            return None
        if self.invalid_proposal:
            return {"intent": "execute_shell", "topic": "vpn", "summary": "Unsafe"}
        a = classify(message)
        return dict(intent=a["intent"], topic=a["topic"], summary=a["summary"], impact=a["impact"], urgency=a["urgency"])

    def search(self, message, limit=4):
        if self.unavailable:
            raise ServiceError("Retrieval unavailable.")
        a = classify(message)
        article_id = a["article_id"] or "KB-VPN"
        article = next(v for v in self.articles if v["id"] == article_id)
        return [dict(chunk_id=f"{article_id}-test-0", article_id=article_id, title=article["title"],
                     category=article["category"], passage=article["content"][:800], similarity=0.20 if self.low_confidence else 0.78)]

    def answer(self, message, sources):
        if self.generation_failed:
            return "Retrieved passages only: " + sources[0]["passage"], "retrieved_passages_only"
        return "Test grounded guidance [" + sources[0]["article_id"] + "].", "qwen_grounded"


@pytest.fixture
def environment():
    store, ai = MemoryStore(), FakeAI()
    cfg = replace(Settings(mongo_uri="mongodb://test.invalid"), models_enabled=False)
    app = create_app(settings=cfg, store=store, ai=ai)
    with TestClient(app) as client:
        yield client, store, ai
