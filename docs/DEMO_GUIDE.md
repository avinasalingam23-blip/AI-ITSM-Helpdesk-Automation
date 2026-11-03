# Avinash's 15–20 minute demonstration

## Before the presentation

1. Keep the laptop connected to power and internet; Atlas is a cloud database even though inference is local.
2. Stop the backend and run the scoped demo reset from the README if you want to show a fresh before/after change. The previous successful demonstration may otherwise show `already_healthy`, which is a valid idempotent result.
3. Start one backend without `--reload` for the presentation, and reuse/start one frontend on port 5173. Keep the terminal output available and open `/api/system`: database connected, AI ready, ServiceNow mock.
4. Open the portal and optionally `/docs` in a second tab. Keep the AI analysis and dashboard available through the sidebar. Never display `.env` or database credentials.
5. For a rehearsal, run `backend/scripts/verify_live.py`. It creates demo tickets and changes the fictional account/device state; reset again before presenting if you need a fresh state transition.

## 0–2 minutes: explain the problem

Suggested words:

> “I'm Avinash. Employees often don't know whether an IT issue needs a support article, an incident, an access request or a simple recovery action. My prototype takes one natural-language message and routes it through a complete helpdesk workflow. It keeps the evidence, ServiceNow reference and action audit together.”

Point out the demo identity banner. Explain that ServiceNow, account recovery and installation are clearly labelled simulations; Atlas persistence, semantic retrieval and local Qwen generation are working integrations.

## 2–5 minutes: explain the architecture

Show the README diagram or describe:

> “React calls FastAPI. Qwen proposes structured fields. Python validates them and applies explicit business policy. MiniLM embeds the message on CPU, Chroma finds approved document passages, and Qwen uses those passages for guidance. MongoDB Atlas stores tickets, chat history, knowledge metadata, mock users/devices, requests and audit records. The ServiceNow adapter can select a persistent mock API or a configured real instance.”

Explain why this fits the laptop: MiniLM on CPU, a 1.5B model, a 3 GiB GPU weight budget, bounded context, and one loaded model instance. No paid AI API or training is required.

## 5–7 minutes: VPN incident

Send **“My VPN is not connecting.”**

Show the returned guidance, expand a real retrieved passage, and inspect AI analysis.

Expected final policy fields:

| Field | Expected |
| --- | --- |
| Intent | Incident |
| Category / subcategory | Network / VPN |
| Priority | P2 |
| Impact / urgency | Individual / High |
| Assignment group | Network Support |
| Knowledge | KB-VPN above the retrieval threshold |
| ITSM | Persisted MOCK-INC reference, open |

Say:

> “The model proposes a classification, but the priority is controlled by the assessment's explicit business rule. A VPN incident does not become resolved just because the assistant offered instructions. There is no approved automatic VPN repair.”

Show the ticket on the dashboard. If asked about the PDF's longer authentication example, submit “I cannot connect to VPN since this morning. Authentication keeps failing.” The same P2/individual/high/network routing applies.

## 7–9 minutes: password self-healing

Send **“My password has expired.”**

Open AI analysis and show the trace plus audit. The workflow identifies the issue, diagnoses the current demo state, retrieves KB-PASSWORD, selects `password_reset`, records the attempt, changes the fictional account, validates the read-back, and updates mock ServiceNow.

Show `password_expired: true → false` and `reset_count: 0 → 1` in the before/after state. The incident is resolved only after validation and successful ITSM update. No password or token is generated or shown.

Say:

> “The AI does not run a command. It chooses a supported workflow, and Python checks an explicit action allowlist and a fixed demo target. A real production reset would require identity verification and an authorised identity provider integration.”

Optional extra: **“My account is locked. Please unlock it.”** Show `locked: true → false`. Explain that password expiry and account lock are independent states. Repeating a healthy request returns an already-healthy result without incrementing the reset counter.

## 9–11 minutes: Outlook knowledge question

Send **“How do I troubleshoot Outlook synchronisation?”**

Show the Qwen-selected evidence steps and KB-OUTLOOK source passages. These are exact retrieved sentences, validated and cited by the backend; invented model prose is discarded. No incident is created for a supported knowledge question unless the employee chooses escalation.

Explain:

> “The article is chunked, embedded and persisted before this question arrives. The query is embedded at runtime. The model selects useful evidence from the returned passages, rather than generating unsupported steps. The evidence card is the actual retrieved text, not a fabricated reference.”

Open Knowledge Base and search **“email stopped updating”**. Show chunk IDs and cosine scores. The scores measure semantic similarity; they are not a calibrated probability that the model is right.

## 11–13 minutes: Visual Studio Code provisioning

Send **“I need Visual Studio Code.”**

Show the service request and `MOCK-REQ` reference. In AI analysis, show `provision_vscode`, the fixed device `DEMO-LAPTOP-01`, and `installed_software: [] → ["vscode"]`.

Say:

> “The catalogue approves this specific item. The application creates a ServiceNow request before calling the mock provisioning API. It confirms the inventory state before marking the request complete. This is a simulated inventory change; it does not install software on this laptop.”

Optional control: **“Install Photoshop for me.”** It must remain awaiting human review; it must never execute the VS Code action as a substitute.

## 13–15 minutes: unsupported question and escalation

Send **“Who won the intergalactic chess tournament?”**

Show the insufficient-knowledge answer, no attributed sources, no invented facts and no automatic incident. Click **Escalate to helpdesk**. Show the new escalated incident and mock ITSM reference.

Say:

> “Abstaining is part of the workflow. An unsupported subject or evidence below 0.40 does not produce a confident support answer. The employee can choose a human ticket, and a recognised incident with weak evidence is escalated automatically.”

## 15–17 minutes: failure handling and technical decisions

Show the tests or verification report rather than disconnecting the live database during the presentation.

- State validation failure: ticket failed, mock ITSM record remains unresolved, failed validation audited.
- ServiceNow update failure after a successful demo action: actual state change remains visible, workflow failed, reconciliation required.
- Database outage: 503, no memory fallback or fictional successful save.
- Audit outage: no unrecorded action execution.
- Request retries: same ID replays the original response; changed content or interrupted IDs require review.

Explain that the real adapter maps incidents and a configured catalogue item but has not been tested against a developer instance. Show `backend/.env.example` only if needed; never the live `.env`. Real-mode records are not resolved by fictional account actions.

## 17–20 minutes: learnings and next steps

Discuss source quality, the short VS Code query, classification validation, bounded local inference and avoiding false success across multiple systems. Be clear about remaining work for production: enterprise sign-in/RBAC, measured retrieval/answer evaluation, distributed jobs, reconciliation, approvals and a real ITSM instance.

Close with the dashboard and show that each business journey left inspectable records. Submission is preferred by 3 November 2026, due no later than 4 November, with demonstration on 5 November.

## Recovery notes

| Symptom | What to do |
| --- | --- |
| Frontend cannot load data | Confirm backend port 8000, wait for model startup, click Refresh |
| AI retrieval only/unavailable | Check cached models and local storage; do not describe excerpts as generated answers |
| Atlas unavailable | Restore internet and Atlas network permissions; do not rerun mutations blindly |
| Request takes time | Wait for local inference; the UI shows pending state and uses a stable retry ID |
| Already healthy / software present | Explain idempotency, or stop the backend and use the scoped demo reset |
| Failed / needs reconciliation | Inspect ticket, before/after state and audit; do not claim resolution |
