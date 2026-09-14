import type { BriefingResponse } from '../types/briefing'

const baseUrl = (import.meta.env.VITE_API_BASE_URL?.trim() || 'http://localhost:8000').replace(/\/+$/, '')

export async function generateBriefing(prompt: string, conversationId?: string | null): Promise<BriefingResponse> {
  let response: Response
  try {
    response = await fetch(`${baseUrl}/api/briefings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, ...(conversationId != null ? { conversation_id: conversationId } : {}) }),
    })
  } catch {
    throw new Error('Unable to reach Northstar. Check that the backend is running, then try again.')
  }
  if (!response.ok) {
    // Keep upstream diagnostics and raw validation payloads out of the UI.
    throw new Error(response.status === 422
      ? 'Enter a prompt between 1 and 10,000 characters.'
      : 'We couldn’t generate your briefing. Please try again.')
  }
  return response.json() as Promise<BriefingResponse>
}
