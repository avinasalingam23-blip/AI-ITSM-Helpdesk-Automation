import re

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .domain import ServiceError, identifier, now, redact


class MockRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    short_description: str = Field(min_length=3, max_length=150)
    description: str = Field(default="", max_length=5000)
    category: str = "Other"
    subcategory: str = "Unclassified"
    priority: str = Field(default="3", pattern=r"^[1-4]$")
    impact: str = Field(default="3", pattern=r"^[1-3]$")
    urgency: str = Field(default="2", pattern=r"^[1-3]$")
    assignment_group: str = "Service Desk"
    state: str = "open"
    work_notes: str = Field(default="Demo record; no real ServiceNow operation.", max_length=6000)


class MockRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str = Field(pattern=r"^(open|in_progress|resolved|completed|failed|awaiting_review|escalated)$")
    work_notes: str = Field(min_length=3, max_length=6000)


class ServiceNowAdapter:
    def __init__(self, settings, client):
        self.settings, self.client = settings, client
        self.mode = settings.servicenow_mode

    async def _call(self, method, path, payload=None):
        try:
            response = await self.client.request(method, path, json=payload)
            response.raise_for_status()
            result = response.json()["result"]
            if not isinstance(result, dict):
                raise ValueError("Invalid integration response")
            return result
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            # Never include upstream body/URL/auth in errors or logs. No automatic POST retries.
            raise ServiceError("ServiceNow integration failed. Remote success is unconfirmed; review before retrying.") from None

    async def create(self, ticket, kind="incident"):
        a = ticket["analysis"]
        fields = dict(short_description=ticket["title"], description=redact(ticket["description"]),
                      category=a["category"], subcategory=a["subcategory"],
                      priority=a["priority"][1:], impact="2" if a["impact"] == "Multiple users" else "3",
                      urgency="1" if a["urgency"] == "High" else "2", assignment_group=a["assignment_group"])
        table = "incident" if kind == "incident" else "sc_request"
        if self.mode == "real":
            groups = {"Network Support": self.settings.network_group_id,
                      "Identity Support": self.settings.identity_group_id,
                      "Desktop Support": self.settings.desktop_group_id,
                      "Service Desk": self.settings.helpdesk_group_id}
            group_id = groups.get(a["assignment_group"], "")
            if not re.fullmatch(r"[a-fA-F0-9]{32}", group_id):
                raise ServiceError("Configure real ServiceNow assignment group sys_ids before creating records.")
            fields["assignment_group"] = group_id
            # Choice values must match the target instance's configured dictionary.
            fields["category"] = {"Network": "network", "Software": "software", "Hardware": "hardware"}.get(a["category"], "inquiry")
            fields["subcategory"] = ""
        if kind == "request" and self.mode == "real":
            if ticket.get("software_id") != "vscode":
                raise ServiceError("This request is outside the configured real software catalogue; human review is required.")
            if not re.fullmatch(r"[a-fA-F0-9]{32}", self.settings.request_item_id):
                raise ServiceError("Configure a real approved ServiceNow catalogue item before submitting software requests.")
            if a["topic"] != "software":
                raise ServiceError("Real application-access catalogue routing is not configured; human review is required.")
            result = await self._call("POST", f"/api/sn_sc/servicecatalog/items/{self.settings.request_item_id}/order_now",
                                      {"sysparm_quantity": "1", "variables": {"business_justification": ticket["description"]}})
            sys_id = result.get("request_id")
            number = result.get("request_number")
        else:
            result = await self._call("POST", f"/api/now/table/{table}", fields)
            sys_id, number = result.get("sys_id"), result.get("number")
        if not isinstance(sys_id, str) or not isinstance(number, str) or not sys_id or not number:
            raise ServiceError("ServiceNow returned an incomplete reference; record creation needs reconciliation.")
        return dict(sys_id=sys_id, number=number, mode=self.mode, table=table, status="open")

    async def get(self, reference):
        return await self._call("GET", f"/api/now/table/{reference['table']}/{reference['sys_id']}")

    async def update(self, reference, status, note):
        payload = {"state": status, "work_notes": redact(note)}
        if self.mode == "real":
            # Mock account changes never resolve real incidents or fulfil real software.
            payload["state"] = "2"
            payload["work_notes"] = "DEMO SIMULATION ONLY; no real account or software changed. " + redact(note)
        result = await self._call("PATCH", f"/api/now/table/{reference['table']}/{reference['sys_id']}", payload)
        if result.get("sys_id") != reference["sys_id"] or str(result.get("state")) != str(payload["state"]):
            raise ServiceError("ServiceNow update validation failed; resolution is unconfirmed.")
        return {**reference, "status": status if self.mode == "mock" else "awaiting_review"}


async def create_mock_record(store, table, payload):
    if table not in {"incident", "sc_request"}:
        raise ServiceError("Unsupported mock ServiceNow table.", 404)
    sys_id = identifier("MOCK")
    record = dict(_id=sys_id, sys_id=sys_id, number=identifier("MOCK-INC" if table == "incident" else "MOCK-REQ"),
                  table=table, **{k: redact(v) if isinstance(v, str) else v for k, v in payload.model_dump().items()},
                  mode="mock", is_demo=True, created_at=now())
    return await store.insert("servicenow", record)
