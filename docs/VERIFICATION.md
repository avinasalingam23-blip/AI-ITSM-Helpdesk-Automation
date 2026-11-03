# Verification evidence

Environment: Avinash's Windows workspace, 2 November 2026. The supplied assessment PDF was readable and its requirements were compared with the implementation.

## Automated checks

- Backend suite: **40 passed**, including actual CPU MiniLM/on-disk Chroma and tests rejecting invented model prose/evidence IDs. One upstream Starlette/httpx TestClient deprecation warning remains. The final rerun also checks the bounded evidence-selection parser.
- Frontend: TypeScript/Vite production build and ESLint passed. Existing dependency versions, lockfile and minimatch override were preserved.
- Live backend: `/health` and `/api/system` returned 200; Atlas connected; Qwen and CPU MiniLM ready; Chroma persisted 24 chunks from eight articles.
- Existing Vite server returned HTTP 200 and served the new application title.

The final HTTP verifier passed all five required scenarios, explicit escalation, account unlock, stable-ID retry replay and preservation of **both original ticket records**. `artifacts/live-verification.json` contains the complete responses and is ignored by Git.

| Live scenario | Outcome | Answer mode | Classification |
| --- | --- | --- | --- |
| My VPN is not connecting. | Open incident, P2/Individual/High, Network Support, persistent mock reference | Actual Qwen + KB-VPN | Validated Qwen proposal + business rules |
| My password has expired. | Validated demo account state, resolved ticket, mock ITSM update | Actual Qwen + KB-PASSWORD | Validated Qwen proposal + business rules |
| Outlook synchronisation question | Answered, no automatic incident | Actual Qwen + KB-OUTLOOK | Labelled rule fallback after invalid model proposal |
| I need Visual Studio Code. | Request completed, fictional device inventory validated, mock request updated | Actual Qwen + KB-SOFTWARE | Labelled rule fallback after invalid model proposal |
| Unsupported chess question | Honest abstention; explicit escalation created a mock incident | Insufficient knowledge; no attributed sources | Labelled rule fallback |

Final measured scenario timings were approximately **4.4, 3.9, 3.9, 5.0 and 3.1 seconds** respectively, including retry replay and relevant verification. These are observations from this laptop, not latency guarantees. Password and unlock state had already changed in earlier successful attempts; the final run correctly validated the already-healthy state. The scoped reset restores a fresh demonstration state.

The real retrieval test initially found the short VS Code question ranked an access article above the software article. Improving the software title, scope and article separation corrected retrieval; scores were not hardcoded. Reviewing the first successful live answer set also revealed unsupported menu/administrator instructions in free-form Qwen prose. The final implementation therefore uses **constrained extractive RAG**: Qwen selects sentence IDs from real retrieved passages, the backend validates every ID, and only the original source sentences are displayed with citations. Model-invented prose and unknown evidence IDs are rejected, with clearly labelled excerpts as the fallback. Model selections may be valid JSON or explicit evidence ID labels; either format passes the same source-ID validation. The live report was regenerated and all five scenarios passed for this final implementation.

## Verification limits

Unit/API failure tests use explicit test doubles; they do not intentionally interrupt Avinash's real Atlas service. No real ServiceNow developer instance, identity provider or software deployment service was supplied. Those operations remain labelled mock or unverified real-adapter configuration.

No browser-control tool is available in this session. HTTP serving, TypeScript compilation and lint can be verified here; visual layout, keyboard use and responsive browser behaviour still need a manual review on the laptop. Open each of the four screens, expand a source, inspect a ticket/article dialog, resize the viewport and repeat a portal scenario. The dialogs include keyboard focus handling and Escape-to-close, but that behaviour has not been exercised in a browser automation run.
