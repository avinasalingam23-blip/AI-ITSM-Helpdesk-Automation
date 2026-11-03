# Assessment coverage

| Assessment requirement | Implementation / evidence |
| --- | --- |
| Intelligent ticket intake | `helpdesk/domain.py`, `rag.py` and `service.py`: Qwen proposal, schema validation, explicit impact/urgency/priority/group rules, RAG evidence and ITSM incident |
| VPN example P2 / Individual / High / Network Support | Routing test and live HTTP verifier validate the fields and persisted mock ServiceNow record |
| Identify → diagnose → knowledge → approved action → execute → validate → update | `automations.py` and workflow audit; fictional password reset and independent account unlock; read-back validation before resolution |
| Every automated action audited | Write-ahead execution record, completed/failed execution, validation and integration events in `demo_audit`; denied allowlist attempts recorded |
| 5–10 realistic support documents | Eight Markdown articles plus an explicit approved catalogue in `knowledge-base/` |
| Chunk → embed → vector database → semantic retrieval → LLM → grounded answer | Overlapping chunks, real CPU MiniLM, persistent cosine Chroma, Qwen evidence selection, validated original sentences and exact source citations |
| React self-service chatbot with routing and ticket option | Employee portal, four example shortcuts, request statuses, source details and explicit escalation button |
| Software catalogue and provisioning | `vscode` catalogue entry, service request before mock provisioning HTTP call, fictional device mutation, validation and ITSM update |
| ServiceNow incident create/get/update | Persistent, labelled mock Table API; configurable real adapter with assignment sys_id mapping; live mock tests and adapter failure tests |
| ServiceNow service requests | Mock `sc_request`; real configured catalogue `order_now` path; unapproved catalogue substitutions blocked |
| MongoDB Atlas | Existing tickets preserved; new supporting demo collections for users/devices/chat/knowledge/requests/audit/ITSM records |
| Four required screens | Employee portal, ITSM dashboard, AI analysis and Knowledge Base in `frontend/src/App.tsx` |
| Confidence and escalation | Explicit 0.40 cosine threshold, heuristic label, unknown-topic abstention, evidence-insufficiency veto and human escalation |
| No unsupported generated instructions | Final RAG renders only exact retrieved sentences selected by Qwen; free-form invented text and invalid IDs are discarded |
| Model and hardware constraints | Existing Qwen 1.5B and MiniLM; CPU embeddings, retained models, single worker, bounded input/output and GPU/CPU placement |
| Secrets | Backend-only settings; literal-placeholder URI approach retained; `.env` ignored; validation errors omit inputs; access logs omit query strings |
| Error handling | Tests inject database/retrieval/audit/execution/validation/ITSM failures; no automatic memory fallback or false resolution |
| Five mandatory scenarios | `backend/demo_cases.json`, deterministic tests and actual HTTP/model/Atlas verifier |
| Demo reset and test data | Fixed demo-only reset filter and collection list; seeded fictional employee/device; reset safety test |
| Setup and explanation | Root README, dependency pins/full environment snapshot, placeholder `.env.example`, demo guide and verification report |

## Explicit limits

Real ServiceNow, enterprise sign-in, real account recovery and actual software installation are not claimed as live integrations. The assessment permits mocked operations. Classification fallbacks are labelled in each response. Source quality and evidence selection still need human review, and the confidence threshold is not calibrated. Browser visual/responsive/keyboard checks remain manual because this session has no browser-control tool.
