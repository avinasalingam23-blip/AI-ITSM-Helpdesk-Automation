import re
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

DEMO_USER = "demo-avinash"
DEMO_DEVICE = "DEMO-LAPTOP-01"
CATALOGUE = [{"id": "vscode", "name": "Visual Studio Code", "publisher": "Microsoft",
              "approved": True, "version": "demo-approved", "device": DEMO_DEVICE,
              "description": "Approved code editor. Provisioning changes a demo device record only."}]


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix):
    return f"{prefix}-{uuid4().hex[:12].upper()}"


class ServiceError(Exception):
    def __init__(self, message, status=503):
        self.message, self.status = message, status
        super().__init__(message)


def redact(value: str) -> str:
    """Remove common credentials before persistence, model prompts and responses."""
    value = re.sub(r"(?i)(?:mongodb(?:\+srv)?|https?)://\S+", "[redacted URL]", value)
    value = re.sub(r"(?i)\b(password|passwd|token|secret|api[_ -]?key)\s*[:=]\s*\S+",
                   r"\1=[redacted]", value)
    value = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]+)\b", "[redacted]", value)
    value = re.sub(r"(?i)\b(my password is|my token is|my secret is)\s+\S+", r"\1 [redacted]", value)
    return value


class TicketCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10, max_length=4000)


class ChatInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message: str = Field(min_length=3, max_length=2000)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")
    escalate: bool = False


class ModelClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["knowledge", "incident", "automation", "service_request", "unknown"]
    topic: Literal["vpn", "password", "unlock", "outlook", "wifi", "performance", "software", "access", "unknown"]
    summary: str = Field(min_length=3, max_length=150)
    impact: Literal["Individual", "Multiple users"] = "Individual"
    urgency: Literal["Low", "Medium", "High"] = "Medium"


TOPICS = {
    "vpn": ("Network", "VPN", "Network Support", "KB-VPN"),
    "password": ("Identity", "Password", "Identity Support", "KB-PASSWORD"),
    "unlock": ("Identity", "Account unlock", "Identity Support", "KB-UNLOCK"),
    "outlook": ("Messaging", "Outlook", "Desktop Support", "KB-OUTLOOK"),
    "wifi": ("Network", "Wi-Fi", "Network Support", "KB-WIFI"),
    "performance": ("Hardware", "Laptop performance", "Desktop Support", "KB-PERFORMANCE"),
    "software": ("Software", "Installation", "Desktop Support", "KB-SOFTWARE"),
    "access": ("Access", "Application access", "Service Desk", "KB-ACCESS"),
    "unknown": ("Other", "Unclassified", "Service Desk", None),
}


def classify(message: str, proposal: dict | None = None):
    """Validated model proposal plus conservative, explicit business policy.

    The model cannot authorize an action, choose its target or promote urgency/impact.
    Known automation routes require direct first-person issue wording.
    """
    m = message.lower()
    question = bool(re.search(r"\b(how|what|where|why|steps|guide|can i)\b", m))
    topic = "unknown"
    for key, pattern in [
        ("vpn", r"\b(vpn|virtual private network)\b"),
        ("unlock", r"\b(lock(?:ed)? out|account.{0,20}lock|unlock)\b"),
        ("password", r"\b(password|passwd)\b"),
        ("outlook", r"\b(outlook|email|mail.{0,20}(sync|updat))\b"),
        ("wifi", r"\b(wi[ -]?fi|wireless)\b"),
        ("performance", r"\b(slow|performance|freez|overheat|lagg)"),
        ("software", r"\b(software|install|visual studio code|vscode|vs code|photoshop)\b"),
        ("access", r"\b(application access|access to|permission|app access)\b"),
    ]:
        if re.search(pattern, m):
            topic = key
            break
    intent = "unknown" if topic == "unknown" else "knowledge" if question else "incident"
    first_person = bool(re.search(r"\b(my|i|me)\b", m))
    action = None
    if not question and first_person:
        if topic == "password" and re.search(r"\b(expired|reset|forgot|forgotten)\b", m):
            intent, action = "automation", "password_reset"
        elif topic == "unlock" and re.search(r"\b(lock|locked|unlock)\b", m):
            intent, action = "automation", "account_unlock"
    if topic in {"software", "access"} and not question:
        intent = "service_request"
    # Unrecognised software is a human-reviewed request, never allowlisted implicitly.
    if topic == "unknown" and re.search(r"\b(install|software)\b", m):
        topic, intent = "software", "service_request"
    impact = "Multiple users" if re.search(r"\b(everyone|whole (team|office)|all (users|employees))\b", m) else "Individual"
    urgency = "High" if topic == "vpn" or re.search(r"\b(urgent|blocked|cannot work|can't work)\b", m) else "Medium"
    priority = "P1" if impact == "Multiple users" and urgency == "High" else "P2" if urgency == "High" else "P3"
    category, subcategory, group, article_id = TOPICS[topic]
    summary = {"vpn": "VPN authentication or connection failure", "password": "Employee password assistance",
               "unlock": "Employee account locked", "outlook": "Outlook synchronisation assistance",
               "software": "Software provisioning request"}.get(topic, message[:120])
    validated = None
    if proposal:
        try:
            validated = ModelClassification.model_validate(proposal).model_dump()
            if validated["topic"] == topic and validated["intent"] == intent:
                summary = redact(validated["summary"])
        except ValueError:
            validated = None
    return dict(intent=intent, topic=topic, category=category, subcategory=subcategory,
                assignment_group=group, impact=impact, urgency=urgency, priority=priority,
                summary=summary, action=action, article_id=article_id,
                classifier="Qwen proposal + business rules" if validated else "Business rules (model unavailable or invalid)",
                model_proposal=validated,
                policy="VPN incidents are high urgency/P2 for an individual; broad high-urgency outages are P1. Only explicit demo self-service actions may execute.")
