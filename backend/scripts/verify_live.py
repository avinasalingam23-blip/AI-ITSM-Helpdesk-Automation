"""Runs real cached models + Atlas + HTTP adapters. Creates labelled demo data only."""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    cases = json.loads((root / "backend/demo_cases.json").read_text(encoding="utf-8"))
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "cases": []}
    with httpx.Client(base_url=args.base_url, timeout=240) as client:
        system = client.get("/api/system").raise_for_status().json()
        check(system["database"] == "connected", "Atlas must be connected.")
        check(system["ai"]["status"] == "ready", "Both real local models must be ready.")
        check(system["servicenow_mode"] == "mock", "Live verification runs only in mock ServiceNow mode.")
        legacy = [t for t in client.get("/api/tickets").raise_for_status().json() if not t.get("is_demo")]
        fingerprints = {t["ticket_id"]: hashlib.sha256(json.dumps(t, sort_keys=True).encode()).hexdigest() for t in legacy}
        report["system"] = system
        for case in cases:
            body = {"message": case["message"], "request_id": "verify-" + uuid4().hex}
            start = time.monotonic()
            response = client.post("/api/chat", json=body).raise_for_status().json()
            analysis = response.get("analysis", {})
            check(analysis.get("intent") == case["intent"], f"{case['name']}: wrong intent")
            check(response["status"] == case["status"], f"{case['name']}: {response['status']} {response.get('warnings')}")
            if case.get("source"):
                check(any(s["article_id"] == case["source"] for s in response["sources"]), "Missing actual retrieved source.")
                check(response["answer_mode"] == "qwen_grounded", f"Expected real Qwen generation, got {response['answer_mode']}")
                # Rule fallback is an intentional, labelled failure path.
                # Require a genuine model proposal for the AI intake case.
                if case["intent"] == "incident":
                    check(analysis["model_proposal"] is not None, "VPN Qwen classification was not valid JSON.")
            else:
                check(response["sources"] == [] and response["answer_mode"] == "insufficient_knowledge", "Unknown answer should abstain.")
            if case.get("action"):
                check(response["automation"]["validated"] is True, "Action must validate state.")
                check(response["automation"]["action"] == case["action"], "Wrong action.")
                audit = client.get("/api/audit", params={"ticket_id": response["ticket"]["ticket_id"]}).raise_for_status().json()
                check(any(v["stage"] == "validate" and v["outcome"] == "passed" for v in audit), "Missing audit validation.")
            if response["ticket"]:
                ref = response["ticket"]["servicenow"]
                remote = client.get(f"/mock/servicenow/api/now/table/{ref['table']}/{ref['sys_id']}").raise_for_status().json()["result"]
                check(remote["state"] == response["status"], "ITSM status must match ticket.")
                if case["intent"] == "incident":
                    check(remote["priority"] == "2" and remote["assignment_group"] == "Network Support", "VPN field mapping incorrect.")
            if case["intent"] == "unknown":
                escalation = client.post("/api/chat", json={**body, "request_id": "verify-" + uuid4().hex, "escalate": True}).raise_for_status().json()
                check(escalation["status"] == "escalated" and escalation["ticket"]["servicenow"], "Explicit escalation did not create an ITSM ticket.")
            repeat = client.post("/api/chat", json=body).raise_for_status().json()
            check(repeat == response, "Retry must replay the original response.")
            item = dict(name=case["name"], passed=True, seconds=round(time.monotonic() - start, 2), response=response)
            report["cases"].append(item)
            print(f"PASS {case['name']}: {response['status']} / {response['answer_mode']} / {analysis['classifier']} / {item['seconds']}s", flush=True)
        # Additional approved account-unlock demonstration.
        unlock = client.post("/api/chat", json={"message": "My account is locked. Please unlock it.", "request_id": "verify-" + uuid4().hex}).raise_for_status().json()
        check(unlock["status"] == "resolved" and unlock["automation"]["after"]["locked"] is False, "Unlock failed.")
        state = client.get("/api/demo/state").raise_for_status().json()
        check(state["user"]["password_expired"] is False and state["user"]["locked"] is False, "Account state not persisted.")
        check("vscode" in state["device"]["installed_software"], "Provisioning state not persisted.")
        for key, digest in fingerprints.items():
            original = client.get(f"/api/tickets/{key}").raise_for_status().json()
            check(hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest() == digest, "An existing ticket changed!")
        report.update(unlock=unlock, demo_state=state, preserved_legacy_tickets=len(fingerprints), passed=True)
    directory = root / "artifacts"
    directory.mkdir(exist_ok=True)
    destination = directory / "live-verification.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PASS account unlock, retry replay and preservation of {len(fingerprints)} existing tickets.")
    print(f"Saved report: {destination}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, httpx.HTTPError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
