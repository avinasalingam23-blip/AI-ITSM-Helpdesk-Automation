export type Source = { chunk_id: string; article_id: string; title: string; category: string; passage: string; similarity: number }
export type Analysis = {
  intent: string; topic: string; summary: string; category: string; subcategory: string
  priority: string; impact: string; urgency: string; assignment_group: string
  classifier: string; confidence: number; confidence_label: string; escalation_threshold: number
  escalation_required: boolean; policy: string; action: string | null; model_proposal: Record<string, string> | null
}
export type Reference = { number: string; sys_id: string; mode: string; table: string; status: string }
export type Automation = { action: string; status: string; validated: boolean; mode: string; target: string; before: Record<string, unknown>; after: Record<string, unknown>; message: string }
export type Ticket = {
  ticket_id: string; title: string; description: string; status: string; created_at: string
  is_demo?: boolean; kind?: string; analysis?: Analysis; sources?: Source[]; servicenow?: Reference
  integration_status?: string; automation?: Automation; last_error?: string; chat_id?: string
}
export type Result = {
  request_id: string; message: string; created_at: string; status: string; answer: string; answer_mode: string
  analysis?: Analysis; sources: Source[]; ticket: Ticket | null; automation: Automation | null
  integration_mode: string; warnings: string[]; timeline: { stage: string; status: string; detail: string }[]
}
export type Audit = { event_id: string; ticket_id: string; action: string; stage: string; outcome: string; details: string; created_at: string }
export type Article = { id: string; title: string; category: string; content: string; owner: string; reviewed_at: string; approved_actions: string[] }
export type Knowledge = { articles: Article[]; results: Source[]; threshold: number; search_type: string }
export type Stats = { total: number; open: number; ai_resolved: number; escalated: number; software_requests: number; validated_automations: number; failed: number }
export type System = { database: string; servicenow_mode: string; ai: { status: string; error: string | null; llm: string; embeddings: string; embedding_device: string; chunks: number; threshold: number; vector_store: string }; identity: { name: string; mode: string } }
export type SoftwareRequest = { request_id: string; software: string; device_id: string; status: string; servicenow?: Reference }

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://127.0.0.1:8000'
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { ...init, signal: AbortSignal.timeout(path === '/api/chat' ? 240_000 : 20_000) })
  } catch { throw new Error('The backend did not respond. Check port 8000 and model startup. If a request was sent, inspect its ticket before retrying.') }
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: unknown }
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request could not be completed (${response.status}).`)
  }
  return response.json() as Promise<T>
}
export function sendChat(message: string, requestId: string, escalate = false) {
  return api<Result>('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, request_id: requestId, escalate }) })
}
