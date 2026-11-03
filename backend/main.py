import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from pymongo import AsyncMongoClient

from helpdesk.automations import DemoAutomation
from helpdesk.config import Settings
from helpdesk.domain import CATALOGUE, DEMO_DEVICE, DEMO_USER, ChatInput, ServiceError, TicketCreate, identifier, now, redact
from helpdesk.integrations import MockRecordCreate, MockRecordUpdate, ServiceNowAdapter, create_mock_record
from helpdesk.logging import configure_safe_access_logs
from helpdesk.rag import LocalAI
from helpdesk.service import HelpdeskService
from helpdesk.store import MongoStore


class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: str = Field(pattern=r"^(INC|REQ)-[A-F0-9]{12}$")


def create_app(settings=None, store=None, ai=None):
    configure_safe_access_logs()
    @asynccontextmanager
    async def lifespan(app):
        cfg = settings or Settings.load()
        mongo_client = None
        if store is None:
            mongo_client = AsyncMongoClient(cfg.mongo_uri, serverSelectionTimeoutMS=8000, tz_aware=True)
            app.state.store = MongoStore(mongo_client[cfg.database])
        else:
            app.state.store = store
        app.state.settings = cfg
        app.state.ai = ai or LocalAI(cfg)
        try:
            await app.state.store.ping()
            await app.state.store.seed()
            app.state.startup_database_error = None
        except ServiceError as exc:
            app.state.startup_database_error = exc.message
        if ai is None:
            await asyncio.to_thread(app.state.ai.initialise)
        for article in app.state.ai.articles:
            try:
                if not await app.state.store.get("knowledge", article["id"]):
                    await app.state.store.insert("knowledge", dict(_id=article["id"], **article, is_demo=True, created_at=now()))
                else:
                    await app.state.store.update("knowledge", article["id"], article)
            except ServiceError:
                break
        app.state.automation = DemoAutomation(app.state.store, cfg.retrieval_threshold)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://demo-local", timeout=30) as mock_client:
            if cfg.servicenow_mode == "real":
                integration_client = httpx.AsyncClient(base_url=cfg.servicenow_url, timeout=20,
                    auth=(cfg.servicenow_user, cfg.servicenow_password), follow_redirects=False)
            else:
                integration_client = httpx.AsyncClient(transport=transport, base_url="http://demo-local/mock/servicenow/", timeout=30)
            async with integration_client:
                integration = ServiceNowAdapter(cfg, integration_client)
                app.state.service = HelpdeskService(app.state.store, app.state.ai, integration,
                    app.state.automation, mock_client, cfg)
                try:
                    yield
                finally:
                    if mongo_client:
                        await mongo_client.close()

    app = FastAPI(title="Avinash / AI ITSM Helpdesk", version="1.0.0",
                  description="Local assessment prototype. Demo identity, mock automation and labelled ServiceNow adapter.",
                  lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])

    @app.exception_handler(ServiceError)
    async def service_error(_request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, exc):
        # FastAPI's default error body can echo invalid input, including credentials.
        return JSONResponse(status_code=422, content={"detail": "Invalid input. Check required fields and length limits.",
            "fields": [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()]})

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "ok", "message": "Helpdesk backend is running"}

    @app.get("/health/database", tags=["Health"])
    async def database_health(request: Request):
        await request.app.state.store.ping()
        return {"status": "ok", "database": request.app.state.settings.database, "connection": "connected"}

    @app.get("/api/system", tags=["Health"])
    async def system(request: Request):
        try:
            await request.app.state.store.ping()
            db = "connected"
        except ServiceError:
            db = "unavailable"
        return {"database": db, "ai": request.app.state.ai.info(),
                "servicenow_mode": request.app.state.settings.servicenow_mode,
                "identity": {"name": "Avinash", "user_id": DEMO_USER, "mode": "demo; no authentication"},
                "automation_mode": "mock only", "version": "1.0.0"}

    @app.post("/api/tickets", status_code=201, tags=["Tickets"])
    async def create_ticket(payload: TicketCreate, request: Request):
        # Preserve the original endpoint and original ticket fields.
        ticket_id = identifier("INC")
        return await request.app.state.store.insert("tickets", dict(_id=ticket_id, ticket_id=ticket_id,
            title=redact(payload.title), description=redact(payload.description), status="open", created_at=now()))

    @app.get("/api/tickets", tags=["Tickets"])
    async def list_tickets(request: Request):
        return await request.app.state.store.list("tickets", limit=50)

    @app.get("/api/tickets/{ticket_id}", tags=["Tickets"])
    async def get_ticket(ticket_id: str, request: Request):
        record = await request.app.state.store.get("tickets", ticket_id)
        if not record:
            raise ServiceError("Ticket not found.", 404)
        return record

    @app.post("/api/chat", tags=["AI workflows"])
    async def chat(payload: ChatInput, request: Request):
        return await request.app.state.service.chat(payload)

    @app.get("/api/chat/history", tags=["AI workflows"])
    async def history(request: Request):
        return await request.app.state.store.list("chats", {"is_demo": True}, limit=30)

    @app.get("/api/analysis", tags=["AI workflows"])
    async def analysis(request: Request):
        records = await request.app.state.store.list("chats", {"is_demo": True}, limit=30)
        return [r["response"] for r in records if r.get("response")]

    @app.get("/api/audit", tags=["AI workflows"])
    async def audit(request: Request, ticket_id: str | None = None):
        return await request.app.state.store.list("audit", {"ticket_id": ticket_id} if ticket_id else {"is_demo": True}, limit=200)

    @app.get("/api/catalogue", tags=["Provisioning"])
    def catalogue():
        return CATALOGUE

    @app.get("/api/requests", tags=["Provisioning"])
    async def requests(request: Request):
        return await request.app.state.store.list("requests", {"is_demo": True})

    @app.get("/api/demo/state", tags=["Demo"])
    async def demo_state(request: Request):
        return {"user": await request.app.state.store.get("users", DEMO_USER),
                "device": await request.app.state.store.get("devices", DEMO_DEVICE), "mode": "mock"}

    @app.get("/api/dashboard", tags=["Dashboard"])
    async def dashboard(request: Request):
        repo = request.app.state.store
        queries = [("tickets", {}), ("tickets", {"status": "open"}), ("tickets", {"ai_resolved": True}),
                   ("tickets", {"escalated": True}), ("requests", {"is_demo": True}),
                   ("audit", {"stage": "validate", "outcome": "passed"}), ("tickets", {"status": "failed"})]
        values = await asyncio.gather(*(repo.count(c, q) for c, q in queries))
        return dict(zip(["total", "open", "ai_resolved", "escalated", "software_requests", "validated_automations", "failed"], values))

    @app.get("/api/knowledge", tags=["Knowledge"])
    async def knowledge(request: Request, q: str = Query(default="", max_length=500), category: str = ""):
        ai_service = request.app.state.ai
        articles = [a for a in ai_service.articles if not category or a["category"] == category]
        try:
            sources = await asyncio.to_thread(ai_service.search, redact(q), 6) if q.strip() else []
        except Exception:
            raise ServiceError("Semantic retrieval is unavailable. Try again or escalate to the helpdesk.") from None
        if category:
            sources = [s for s in sources if s["category"] == category]
        return {"articles": articles, "results": sources, "threshold": request.app.state.settings.retrieval_threshold,
                "search_type": "MiniLM semantic retrieval / Chroma cosine"}

    @app.post("/mock/servicenow/api/now/table/{table}", status_code=201, tags=["MOCK ServiceNow"])
    async def mock_create(table: str, payload: MockRecordCreate, request: Request):
        return {"result": await create_mock_record(request.app.state.store, table, payload)}

    async def mock_get_record(request, table, sys_id):
        record = await request.app.state.store.get("servicenow", sys_id)
        if not record or record["table"] != table:
            raise ServiceError("Mock ServiceNow record not found.", 404)
        return record

    @app.get("/mock/servicenow/api/now/table/{table}/{sys_id}", tags=["MOCK ServiceNow"])
    async def mock_get(table: str, sys_id: str, request: Request):
        return {"result": await mock_get_record(request, table, sys_id)}

    @app.patch("/mock/servicenow/api/now/table/{table}/{sys_id}", tags=["MOCK ServiceNow"])
    async def mock_update(table: str, sys_id: str, payload: MockRecordUpdate, request: Request):
        await mock_get_record(request, table, sys_id)
        return {"result": await request.app.state.store.update("servicenow", sys_id,
                       {k: redact(v) for k, v in payload.model_dump().items()})}

    @app.post("/mock/automation/{action}", tags=["MOCK automation"])
    async def mock_action(action: str, payload: ActionInput, request: Request):
        return await request.app.state.automation.execute(action, payload.ticket_id)

    @app.post("/mock/provisioning/vscode", tags=["MOCK automation"])
    async def mock_provision(payload: ActionInput, request: Request):
        return await request.app.state.automation.execute("provision_vscode", payload.ticket_id)

    return app


app = create_app()
