import asyncio

from .domain import DEMO_DEVICE, DEMO_USER, ServiceError, identifier, now

ALLOWLIST = {"password_reset": "KB-PASSWORD", "account_unlock": "KB-UNLOCK",
             "provision_vscode": "KB-SOFTWARE"}


class DemoAutomation:
    def __init__(self, store, threshold=0.40):
        self.store, self.threshold = store, threshold
        self.lock = asyncio.Lock()

    async def audit(self, ticket_id, action, stage, outcome, details):
        event_id = identifier("AUD")
        return await self.store.insert("audit", dict(_id=event_id, event_id=event_id,
            ticket_id=ticket_id, action=action, stage=stage, outcome=outcome,
            details=details, is_demo=True, mode="mock", created_at=now()))

    async def execute(self, action, ticket_id):
        async with self.lock:
            return await self._execute(action, ticket_id)

    async def _execute(self, action, ticket_id):
        if action not in ALLOWLIST:
            await self.audit(ticket_id, "denied_action", "policy", "blocked", "Action was outside the explicit allowlist.")
            raise ServiceError("Action is not on the approved allowlist.", 403)
        ticket = await self.store.get("tickets", ticket_id)
        if not ticket or not ticket.get("is_demo") or not ticket.get("servicenow"):
            await self.audit(ticket_id, action, "policy", "blocked", "A matching persisted demo ticket and ITSM reference were not found.")
            raise ServiceError("An existing demo incident/request with an ITSM reference is required.", 409)
        sources = ticket.get("sources", [])
        if not any(s["article_id"] == ALLOWLIST[action] and s["similarity"] >= self.threshold for s in sources):
            await self.audit(ticket_id, action, "policy", "blocked", "Required approved knowledge was not retrieved.")
            raise ServiceError("The required approved knowledge was not retrieved; action blocked.", 403)
        expected = ticket["analysis"].get("action")
        if action == "provision_vscode":
            if ticket.get("software_id") != "vscode" or ticket["analysis"]["intent"] != "service_request":
                raise ServiceError("Software is not approved for this request.", 403)
        elif action != expected:
            raise ServiceError("Requested action does not match the diagnosed issue.", 403)
        await self.audit(ticket_id, action, "identify", "passed", "Target is a fixed fictional demo identity/device.")
        target_collection, target_id = ("devices", DEMO_DEVICE) if action == "provision_vscode" else ("users", DEMO_USER)
        before = await self.store.get(target_collection, target_id)
        if not before:
            await self.audit(ticket_id, action, "diagnose", "failed", "Demo target not found.")
            raise ServiceError("Demo target was not found; no action was executed.")
        await self.audit(ticket_id, action, "diagnose", "passed", "Read current demo target state.")
        await self.audit(ticket_id, action, "knowledge_search", "passed", f"Policy source: {ALLOWLIST[action]}.")
        await self.audit(ticket_id, action, "select_approved_action", "passed", f"Allowlist approved {action}.")
        if action == "password_reset":
            healthy = not before.get("password_expired", True)
            changes = {"password_expired": False, "reset_count": before.get("reset_count", 0) + (0 if healthy else 1)}
        elif action == "account_unlock":
            healthy = not before.get("locked", True)
            changes = {"locked": False}
        else:
            healthy = "vscode" in before.get("installed_software", [])
            changes = {"installed_software": sorted(set(before.get("installed_software", []) + ["vscode"]))}
        # Write-ahead event: if audit storage fails, mutation does not run.
        await self.audit(ticket_id, action, "execute", "started", "No change needed." if healthy else "Applying approved demo state change.")
        try:
            if not healthy:
                await self.store.update(target_collection, target_id, changes)
            await self.audit(ticket_id, action, "execute", "completed", "Already healthy; no change." if healthy else "Approved demo mutation completed; awaiting validation.")
            after = await self.store.get(target_collection, target_id)
            valid = bool(after) and all(after.get(k) == value for k, value in changes.items())
            await self.audit(ticket_id, action, "validate", "passed" if valid else "failed",
                             "Post-action read matches required state." if valid else "Post-action state did not match.")
            if not valid:
                raise ServiceError("Mock action validation failed; human review is required.")
            return dict(action=action, mode="mock", status="already_healthy" if healthy else "validated",
                        validated=True, target=target_id, before={k: before.get(k) for k in changes},
                        after={k: after.get(k) for k in changes},
                        message="Demo state verified. No real account was changed or software installed.")
        except ServiceError:
            await self.audit(ticket_id, action, "execute_or_validate", "failed", "Execution or validation failed; review target state before retrying.")
            raise
