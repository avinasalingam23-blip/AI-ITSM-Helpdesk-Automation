import asyncio

import httpx

from .domain import CATALOGUE, DEMO_DEVICE, DEMO_USER, ServiceError, classify, identifier, now, redact


class HelpdeskService:
    def __init__(self, store, ai, integration, automation, mock_client, settings):
        self.store, self.ai, self.integration, self.automation = store, ai, integration, automation
        self.mock_client, self.settings = mock_client, settings
        # One local worker: serialisation protects demo state and makes retries idempotent.
        self.lock = asyncio.Lock()

    async def chat(self, payload):
        if self.lock.locked():
            raise ServiceError("Another request is running. Please wait and retry.", 429)
        async with self.lock:
            await self.store.ping()
            await self.store.seed()
            previous = await self.store.get("chats", payload.request_id)
            if previous:
                if previous.get("message") != redact(payload.message) or previous.get("escalate") != payload.escalate:
                    raise ServiceError("This request ID belongs to another message.", 409)
                if previous.get("response"):
                    return previous["response"]
                raise ServiceError("This request is incomplete. Inspect its ticket/audit before submitting again.", 409)
            message = redact(payload.message)
            await self.store.insert("chats", dict(_id=payload.request_id, chat_id=payload.request_id,
                message=message, escalate=payload.escalate, user_id=DEMO_USER, is_demo=True, status="processing", created_at=now()))
            response = dict(request_id=payload.request_id, message=message, created_at=now(), user_id=DEMO_USER,
                            sources=[], ticket=None, request=None, automation=None, integration_mode=self.integration.mode,
                            timeline=[], status="processing", answer="", answer_mode="none", warnings=[])
            ticket = None
            try:
                proposal = await asyncio.to_thread(self.ai.propose, message)
                analysis = classify(message, proposal)
                response["analysis"] = analysis
                try:
                    retrieved = await asyncio.to_thread(self.ai.search, message)
                except Exception:
                    retrieved = []
                    response["warnings"].append("Knowledge retrieval unavailable; automatic actions are blocked.")
                threshold = self.settings.retrieval_threshold
                sources = [s for s in retrieved if s["similarity"] >= threshold]
                relevant = [s for s in sources if s["article_id"] == analysis["article_id"]]
                supported = bool(relevant) and analysis["topic"] != "unknown"
                score = max((s["similarity"] for s in relevant), default=0.0)
                analysis.update(confidence=round(score, 4), confidence_label="Heuristic: cosine similarity to approved topic; not a probability",
                                escalation_threshold=threshold, escalation_required=not supported)
                response["sources"] = relevant if supported else []
                response["timeline"].extend([
                    {"stage": "Identify", "status": "passed", "detail": f"{analysis['intent']} / {analysis['category']} / {analysis['priority']}"},
                    {"stage": "Knowledge search", "status": "passed" if supported else "needs_review", "detail": f"{len(response['sources'])} relevant approved passages above {threshold:.2f}"}])
                if supported:
                    response["answer"], response["answer_mode"] = await asyncio.to_thread(self.ai.answer, message, relevant[:3])
                    if response["answer_mode"] == "insufficient_knowledge":
                        supported = False
                        analysis["escalation_required"] = True
                        response["warnings"].append("Qwen judged the retrieved evidence insufficient; automation is blocked and human review is recommended.")
                else:
                    response.update(answer="The approved knowledge base has insufficient information for this question. I cannot provide a reliable answer. Use Escalate to helpdesk to create a ticket for human review.", answer_mode="insufficient_knowledge")
                needs_ticket = payload.escalate or analysis["intent"] in {"incident", "automation", "service_request"}
                if not needs_ticket:
                    response["status"] = "answered" if supported else "needs_escalation"
                else:
                    request_kind = analysis["intent"] == "service_request"
                    ticket_id = identifier("REQ" if request_kind else "INC")
                    software = "vscode" if request_kind and any(term in message.lower() for term in ["visual studio code", "vscode", "vs code"]) else None
                    ticket = dict(_id=ticket_id, ticket_id=ticket_id, title=analysis["summary"], description=message,
                                  status="open", created_at=now(), user_id=DEMO_USER, is_demo=True,
                                  kind="request" if request_kind else "incident", analysis=analysis,
                                  sources=response["sources"], servicenow=None, integration_status="pending",
                                  software_id=software, chat_id=payload.request_id)
                    await self.store.insert("tickets", ticket)
                    response["ticket"] = {k: v for k, v in ticket.items() if k != "_id"}
                    if request_kind:
                        await self.store.insert("requests", dict(_id=ticket_id, request_id=ticket_id,
                            ticket_id=ticket_id, software_id=software, software=CATALOGUE[0]["name"] if software else "Human review required",
                            device_id=DEMO_DEVICE, status="open", is_demo=True, created_at=now()))
                    await self.automation.audit(ticket_id, "workflow", "integration_create", "started", "Creating ITSM record; review before retrying an uncertain remote result.")
                    reference = await self.integration.create(ticket, "request" if request_kind else "incident")
                    ticket = await self.store.update("tickets", ticket_id, dict(servicenow=reference, integration_status="created"))
                    response["ticket"] = ticket
                    response["timeline"].append({"stage": "ServiceNow creation", "status": "passed", "detail": f"{reference['number']} ({reference['mode']})"})
                    await self.automation.audit(ticket_id, "workflow", "integration_create", "passed", f"{reference['mode']} reference {reference['number']}")
                    action = analysis["action"] if supported else None
                    if request_kind and supported and software == "vscode":
                        action = "provision_vscode"
                    if action:
                        endpoint = "/mock/provisioning/vscode" if action == "provision_vscode" else f"/mock/automation/{action}"
                        result = await self.mock_client.post(endpoint, json={"ticket_id": ticket_id})
                        if result.is_error:
                            raise ServiceError("Approved mock action failed. Review the audit trail and demo state.")
                        automation = result.json()
                        response["automation"] = automation
                        if not automation.get("validated"):
                            raise ServiceError("Mock action did not validate; no resolution was recorded.")
                        status = "completed" if request_kind else "resolved"
                        reference = await self.integration.update(reference, status, f"Approved {action}: demo state validated; no real account/software change.")
                        status = status if self.integration.mode == "mock" else "awaiting_review"
                        await self.automation.audit(ticket_id, action, "update_servicenow", "passed", f"{reference['mode']} status {reference['status']}")
                        ticket = await self.store.update("tickets", ticket_id, dict(status=status, servicenow=reference,
                            integration_status="synced", ai_resolved=status == "resolved", automation=automation))
                        response["timeline"].extend([
                            {"stage": "Execute approved mock action", "status": "passed", "detail": action},
                            {"stage": "Validate", "status": "passed", "detail": automation["status"]},
                            {"stage": "Update ServiceNow", "status": "passed", "detail": f"{reference['mode']} / {reference['status']}"}])
                        response["answer"] += "\n\n" + ("Demo workflow validated and mock ServiceNow updated. " if self.integration.mode == "mock" else "Demo workflow validated; real ServiceNow needs human review. ") + automation["message"]
                    else:
                        status = "awaiting_review" if request_kind else "escalated" if not supported or payload.escalate else "open"
                        reference = await self.integration.update(reference, status, "Human review required; no approved automated action was executed.")
                        ticket = await self.store.update("tickets", ticket_id, dict(status=status, servicenow=reference,
                                                                                  integration_status="synced", escalated=status in {"escalated", "awaiting_review"}))
                        if request_kind:
                            response["answer"] += "\n\nThis request requires human approval. No provisioning was performed."
                    response["ticket"], response["status"] = ticket, ticket["status"]
                    if request_kind:
                        response["request"] = await self.store.update("requests", ticket_id,
                            dict(status=ticket["status"], servicenow=ticket["servicenow"], automation=response["automation"]))
            except Exception as exc:
                # Keep partial state visible and never convert a failed step to a success.
                response["status"] = "failed"
                error = exc.message if isinstance(exc, ServiceError) else "Workflow failed unexpectedly. Review the ticket and audit trail before retrying."
                response["warnings"].append(error)
                response["answer"] += "\n\nWorkflow incomplete: " + error
                response["timeline"].append({"stage": "Workflow", "status": "failed", "detail": error})
                if ticket:
                    try:
                        response["ticket"] = await self.store.update("tickets", ticket["ticket_id"],
                            dict(status="failed", escalated=True, integration_status="needs_reconciliation", last_error=error))
                        await self.automation.audit(ticket["ticket_id"], "workflow", "failure", "failed", error)
                        if ticket.get("kind") == "request":
                            response["request"] = await self.store.update("requests", ticket["ticket_id"], dict(status="failed", last_error=error))
                    except ServiceError:
                        response["warnings"].append("Failure state could not be persisted. Database reconciliation is required.")
            # If this write fails, HTTP 503 explains that success cannot be confirmed.
            await self.store.update("chats", payload.request_id, dict(response=response, status=response["status"]))
            return response
