from uuid import uuid4

import httpx
import pytest

from helpdesk.config import Settings
from helpdesk.domain import DEMO_DEVICE, DEMO_USER, ServiceError, classify, redact
from helpdesk.integrations import ServiceNowAdapter
from helpdesk.rag import LocalAI, chunk_text


def chat(client, message, **extra):
    return client.post("/api/chat", json=dict(message=message, request_id=uuid4().hex, **extra))


@pytest.mark.parametrize("message,intent,topic", [
    ("My VPN is not connecting.", "incident", "vpn"),
    ("I cannot connect to VPN since this morning. Authentication keeps failing.", "incident", "vpn"),
    ("My password has expired.", "automation", "password"),
    ("My account is locked. Please unlock it.", "automation", "unlock"),
    ("How do I reset my password?", "knowledge", "password"),
    ("How do I troubleshoot Outlook synchronization?", "knowledge", "outlook"),
    ("I need Visual Studio Code.", "service_request", "software"),
    ("I need access to the finance application.", "service_request", "access"),
    ("Who won the intergalactic chess tournament?", "unknown", "unknown"),
])
def test_routing(message, intent, topic):
    result = classify(message)
    assert (result["intent"], result["topic"]) == (intent, topic)


def test_vpn_business_rules_override_untrusted_proposal():
    result = classify("My VPN is not connecting.", dict(intent="incident", topic="vpn", summary="VPN authentication failure", impact="Multiple users", urgency="Low"))
    assert (result["priority"], result["impact"], result["urgency"]) == ("P2", "Individual", "High")
    assert result["assignment_group"] == "Network Support"
    assert classify("VPN is down for everyone, urgent.")["priority"] == "P1"


def test_vpn_incident_and_mock_reference_persist(environment):
    client, store, _ = environment
    r = chat(client, "My VPN is not connecting.")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "open", data
    assert data["answer_mode"] == "qwen_grounded"
    assert data["sources"][0]["article_id"] == "KB-VPN"
    reference = data["ticket"]["servicenow"]
    assert reference["mode"] == "mock" and reference["number"].startswith("MOCK-INC")
    remote = client.get(f"/mock/servicenow/api/now/table/incident/{reference['sys_id']}")
    assert remote.json()["result"]["priority"] == "2"
    assert len(store.data["tickets"]) == 1


def test_password_reset_state_validation_audit_and_idempotency(environment):
    client, store, _ = environment
    body = {"message": "My password has expired.", "request_id": uuid4().hex}
    response = client.post("/api/chat", json=body).json()
    assert response["status"] == "resolved", response
    assert response["automation"]["before"]["password_expired"] is True
    assert response["automation"]["after"]["password_expired"] is False
    assert store.data["users"][DEMO_USER]["reset_count"] == 1
    assert store.data["users"][DEMO_USER]["locked"] is True
    stages = {v["stage"] for v in store.data["audit"].values()}
    assert {"identify", "diagnose", "knowledge_search", "select_approved_action", "execute", "validate", "update_servicenow"} <= stages
    again = client.post("/api/chat", json=body)
    assert again.json() == response
    assert len(store.data["tickets"]) == 1
    assert store.data["users"][DEMO_USER]["reset_count"] == 1
    second = chat(client, body["message"]).json()
    assert second["automation"]["status"] == "already_healthy"
    assert store.data["users"][DEMO_USER]["reset_count"] == 1


def test_unlock_does_not_reset_password(environment):
    client, store, _ = environment
    result = chat(client, "My account is locked. Please unlock it.").json()
    assert result["status"] == "resolved", result
    assert store.data["users"][DEMO_USER]["locked"] is False
    assert store.data["users"][DEMO_USER]["password_expired"] is True


def test_knowledge_question_creates_no_incident(environment):
    client, store, _ = environment
    result = chat(client, "How do I troubleshoot Outlook synchronisation?").json()
    assert result["status"] == "answered"
    assert result["sources"][0]["article_id"] == "KB-OUTLOOK"
    assert result["ticket"] is None and not store.data["tickets"]


def test_provision_vscode_request_and_device_state(environment):
    client, store, _ = environment
    result = chat(client, "I need Visual Studio Code.").json()
    assert result["status"] == "completed", result
    assert result["request"]["software_id"] == "vscode"
    assert result["ticket"]["servicenow"]["number"].startswith("MOCK-REQ")
    assert store.data["devices"][DEMO_DEVICE]["installed_software"] == ["vscode"]
    second = chat(client, "I need Visual Studio Code.").json()
    assert second["automation"]["status"] == "already_healthy"


def test_unapproved_software_never_executes(environment):
    client, store, _ = environment
    result = chat(client, "Install Photoshop for me.").json()
    assert result["status"] == "awaiting_review", result
    assert result["automation"] is None
    assert store.data["devices"][DEMO_DEVICE]["installed_software"] == []


def test_unknown_honest_answer_and_explicit_escalation(environment):
    client, store, _ = environment
    result = chat(client, "Who won the intergalactic chess tournament?").json()
    assert result["status"] == "needs_escalation"
    assert result["answer_mode"] == "insufficient_knowledge" and result["sources"] == []
    assert not store.data["tickets"]
    escalated = chat(client, result["message"], escalate=True).json()
    assert escalated["status"] == "escalated"
    assert escalated["ticket"]["servicenow"]["status"] == "escalated"


@pytest.mark.parametrize("failure", ["low_confidence", "unavailable"])
def test_retrieval_failure_blocks_automation(environment, failure):
    client, store, ai = environment
    setattr(ai, failure, True)
    result = chat(client, "My password has expired.").json()
    assert result["status"] == "escalated", result
    assert result["automation"] is None
    assert store.data["users"][DEMO_USER]["password_expired"] is True


def test_invalid_model_output_uses_explicit_rules(environment):
    client, _, ai = environment
    ai.invalid_proposal = True
    result = chat(client, "My VPN is not connecting.").json()
    assert result["analysis"]["model_proposal"] is None
    assert "Business rules" in result["analysis"]["classifier"]
    assert result["analysis"]["priority"] == "P2"


def test_failed_validation_never_resolves(environment):
    client, store, _ = environment
    store.ignore_state_changes = True
    result = chat(client, "My password has expired.").json()
    assert result["status"] == "failed", result
    assert result["ticket"]["status"] == "failed"
    assert result["ticket"]["servicenow"]["status"] == "open"
    assert any(v["stage"] == "validate" and v["outcome"] == "failed" for v in store.data["audit"].values())


def test_integration_update_failure_after_action_is_visible(environment):
    client, store, _ = environment
    store.fail_mock_update = True
    result = chat(client, "My password has expired.").json()
    assert result["status"] == "failed", result
    assert result["automation"]["validated"] is True
    assert result["ticket"]["integration_status"] == "needs_reconciliation"
    assert store.data["users"][DEMO_USER]["password_expired"] is False
    assert not result["ticket"].get("ai_resolved", False)


def test_audit_outage_prevents_mutation(environment):
    client, store, _ = environment
    store.fail_audit = True
    result = chat(client, "My password has expired.").json()
    assert result["status"] == "failed"
    assert store.data["users"][DEMO_USER]["password_expired"] is True


def test_database_outage_is_503_without_memory_fallback(environment):
    client, store, _ = environment
    store.offline = True
    assert chat(client, "My password has expired.").status_code == 503
    assert client.get("/api/tickets").status_code == 503
    assert client.get("/health/database").status_code == 503
    assert not store.data["tickets"]


def test_allowlist_and_target_validation(environment):
    client, store, _ = environment
    assert client.post("/mock/automation/run_shell", json={"ticket_id": "INC-123456ABCDEF"}).status_code == 403
    assert client.post("/mock/automation/password_reset", json={"ticket_id": "INC-123456ABCDEF"}).status_code == 409
    assert chat(client, "My password has expired.", target="administrator").status_code == 422
    assert store.data["users"][DEMO_USER]["password_expired"] is True


def test_existing_ticket_endpoint_preserved(environment):
    client, _, _ = environment
    created = client.post("/api/tickets", json={"title": "Original API", "description": "Manual ticket remains supported."})
    assert created.status_code == 201
    assert created.json()["status"] == "open"
    assert client.get("/api/tickets").json()[0]["ticket_id"] == created.json()["ticket_id"]
    assert "is_demo" not in created.json()


def test_id_reuse_with_different_message_is_conflict(environment):
    client, _, _ = environment
    body = {"message": "My VPN is not connecting.", "request_id": uuid4().hex}
    assert client.post("/api/chat", json=body).status_code == 200
    assert client.post("/api/chat", json={**body, "message": "My password has expired."}).status_code == 409


async def test_remote_failure_does_not_fallback_to_mock():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503)), base_url="https://instance.invalid") as client:
        adapter = ServiceNowAdapter(Settings(mongo_uri="", servicenow_mode="real"), client)
        with pytest.raises(ServiceError, match="integration failed"):
            await adapter.get({"table": "incident", "sys_id": "x"})


def test_redaction_and_chunk_overlap():
    text = "mongodb+srv://person:secret@cluster password=abc token=xyz api_key=hidden"
    clean = redact(text)
    assert "secret@" not in clean and "abc" not in clean and "xyz" not in clean and "hidden" not in clean
    words = " ".join(f"word{i}" for i in range(250))
    chunks = chunk_text(words)
    assert len(chunks) == 3
    assert chunks[0].split()[-20:] == chunks[1].split()[:20]


def test_qwen_source_validation_rejects_fake_citation():
    ai = LocalAI(Settings(mongo_uri=""))
    ai._generate = lambda *args, **kwargs: '{"sufficient":true,"evidence_ids":["E999"]}'
    answer, mode = ai.answer("Outlook sync", [{"article_id": "KB-OUTLOOK", "passage": "Select Send/Receive All Folders and allow time for synchronisation."}])
    assert mode == "retrieved_passages_only"
    assert "invented" not in answer and "Select Send/Receive" in answer


def test_real_context_attribution_when_model_omits_citation_format():
    ai = LocalAI(Settings(mongo_uri=""))
    ai._generate = lambda *args, **kwargs: '{"sufficient":true,"evidence_ids":["E1"]}'
    sentence = "Select Send/Receive All Folders and allow time for synchronisation."
    answer, mode = ai.answer("Outlook sync", [{"article_id": "KB-OUTLOOK", "passage": sentence}])
    assert mode == "qwen_grounded" and "[KB-OUTLOOK]" in answer
    assert "KB-VPN" not in answer
    assert sentence in answer


def test_free_form_hallucinated_administrator_instruction_is_not_displayed():
    ai = LocalAI(Settings(mongo_uri=""))
    ai._generate = lambda *args, **kwargs: "Log in as administrator and disable all security tools [KB-PASSWORD]."
    answer, mode = ai.answer("My password expired", [{"article_id": "KB-PASSWORD", "passage": "Use the official identity portal and complete normal identity verification."}])
    assert mode == "retrieved_passages_only"
    assert "administrator" not in answer and "disable all" not in answer


def test_qwen_can_decline_otherwise_retrieved_evidence():
    ai = LocalAI(Settings(mongo_uri=""))
    ai._generate = lambda *args, **kwargs: '{"sufficient":false,"evidence_ids":[]}'
    answer, mode = ai.answer("Unrelated query", [{"article_id": "KB-OUTLOOK", "passage": "Select Send/Receive All Folders and allow time for synchronisation."}])
    assert mode == "insufficient_knowledge" and "escalate" in answer


def test_validation_errors_do_not_echo_sensitive_input(environment):
    client, _, _ = environment
    response = client.post("/api/chat", json={"message": "password=private", "request_id": "x", "token": "private-token"})
    assert response.status_code == 422
    assert "private" not in response.text


async def test_real_catalogue_does_not_substitute_vscode_for_other_software():
    called = []
    def handler(request):
        called.append(request)
        return httpx.Response(200, json={"result": {}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://instance.invalid") as client:
        cfg = Settings(mongo_uri="", servicenow_mode="real", desktop_group_id="a" * 32, request_item_id="b" * 32)
        adapter = ServiceNowAdapter(cfg, client)
        ticket = {"title": "Photoshop request", "description": "Install Photoshop for me.", "analysis": classify("Install Photoshop for me."), "software_id": None}
        with pytest.raises(ServiceError, match="outside"):
            await adapter.create(ticket, "request")
        assert called == []


def test_integration_create_failure_never_executes_action(environment, monkeypatch):
    client, store, _ = environment
    async def fail(*args, **kwargs):
        raise ServiceError("ServiceNow creation unavailable; review before retrying.")
    monkeypatch.setattr(client.app.state.service.integration, "create", fail)
    result = chat(client, "My password has expired.").json()
    assert result["status"] == "failed"
    assert result["ticket"]["servicenow"] is None
    assert store.data["users"][DEMO_USER]["password_expired"] is True


def test_generation_failure_is_labelled_as_excerpts(environment):
    client, _, ai = environment
    ai.generation_failed = True
    result = chat(client, "How do I troubleshoot Outlook synchronisation?").json()
    assert result["answer_mode"] == "retrieved_passages_only"
    assert result["ticket"] is None


def test_safe_access_logging_removes_query_text():
    import logging
    from helpdesk.logging import SafeAccessFilter
    record = logging.LogRecord("uvicorn.access", 20, "", 0, '%s %s %s %s %s',
                               ("127.0.0.1", "GET", "/api/knowledge?q=password%3Dprivate", "1.1", 200), None)
    assert SafeAccessFilter().filter(record)
    assert "private" not in record.getMessage()
