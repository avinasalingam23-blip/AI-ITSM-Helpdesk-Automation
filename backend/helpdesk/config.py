import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    database: str = "helpdesk"
    servicenow_mode: str = "mock"
    servicenow_url: str = ""
    servicenow_user: str = ""
    servicenow_password: str = ""
    request_item_id: str = ""
    network_group_id: str = ""
    identity_group_id: str = ""
    desktop_group_id: str = ""
    helpdesk_group_id: str = ""
    chroma_path: Path = ROOT / "backend" / "data" / "chroma"
    retrieval_threshold: float = 0.40
    models_enabled: bool = True
    local_models_only: bool = True

    @classmethod
    def load(cls):
        # Preserve the existing literal <db_password> / URL-escaped password setup.
        values = {**dotenv_values(ROOT / "backend" / ".env", interpolate=False,
                                  encoding="utf-8-sig"), **os.environ}
        template = values.get("MONGODB_URI_TEMPLATE", "") or ""
        password = values.get("MONGODB_PASSWORD", "") or ""
        if not password or "<db_password>" not in template:
            raise RuntimeError("Check MongoDB settings in backend/.env (see .env.example).")
        mode = values.get("SERVICENOW_MODE", "mock")
        if mode not in {"mock", "real"}:
            raise RuntimeError("SERVICENOW_MODE must be mock or real.")
        url = (values.get("SERVICENOW_URL", "") or "").rstrip("/")
        if mode == "real" and (urlsplit(url).scheme != "https" or
                               not urlsplit(url).hostname or
                               not values.get("SERVICENOW_USER") or
                               not values.get("SERVICENOW_PASSWORD")):
            raise RuntimeError("Real ServiceNow requires an HTTPS URL and backend credentials.")
        return cls(
            mongo_uri=template.replace("<db_password>", quote_plus(password)),
            database=values.get("MONGODB_DB") or "helpdesk",
            servicenow_mode=mode, servicenow_url=url,
            servicenow_user=values.get("SERVICENOW_USER") or "",
            servicenow_password=values.get("SERVICENOW_PASSWORD") or "",
            request_item_id=values.get("SERVICENOW_VSCODE_ITEM_ID") or "",
            network_group_id=values.get("SERVICENOW_NETWORK_GROUP_ID") or "",
            identity_group_id=values.get("SERVICENOW_IDENTITY_GROUP_ID") or "",
            desktop_group_id=values.get("SERVICENOW_DESKTOP_GROUP_ID") or "",
            helpdesk_group_id=values.get("SERVICENOW_HELPDESK_GROUP_ID") or "",
            models_enabled=values.get("MODELS_ENABLED", "true").lower() == "true",
            local_models_only=values.get("HF_LOCAL_FILES_ONLY", "true").lower() == "true",
        )
