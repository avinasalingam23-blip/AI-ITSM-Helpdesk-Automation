"""Reset only records explicitly marked is_demo=True. Stop the backend first."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymongo import AsyncMongoClient

from helpdesk.config import Settings
from helpdesk.domain import ServiceError
from helpdesk.store import MongoStore


async def reset():
    cfg = Settings.load()
    if cfg.servicenow_mode != "mock":
        raise ServiceError("Demo reset is available only in mock ServiceNow mode.")
    client = AsyncMongoClient(cfg.mongo_uri, serverSelectionTimeoutMS=8000)
    try:
        store = MongoStore(client[cfg.database])
        await store.ping()
        result = await store.reset_demo()
        for name, count in result.items():
            print(f"{name}: removed {count} labelled demo records")
        print("Demo account is expired + locked; device inventory is empty. Existing manual tickets and knowledge were preserved.")
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-demo-reset", action="store_true", required=True)
    parser.parse_args()
    try:
        asyncio.run(reset())
    except ServiceError as exc:
        print(exc.message, file=sys.stderr)
        sys.exit(1)
