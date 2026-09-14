import { afterEach, describe, expect, it, vi } from 'vitest'
import { generateBriefing } from './briefings'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('briefing transport', () => {
  it.each([
    [undefined, 'http://localhost:8000/api/briefings'],
    ['', 'http://localhost:8000/api/briefings'],
    ['  https://api.example.test/service///  ', 'https://api.example.test/service/api/briefings'],
  ])('uses the configured API base URL (%s)', async (configured, expected) => {
    vi.stubEnv('VITE_API_BASE_URL', configured)
    vi.resetModules()
    const { generateBriefing: configuredClient } = await import('./briefings')
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ conversation_id: 'conv_test', answer: '', citations: [], invalid_source_ids: [] })))
    vi.stubGlobal('fetch', fetch)
    await configuredClient('Prepare Redwood')
    expect(fetch).toHaveBeenCalledWith(expected, expect.objectContaining({ method: 'POST' }))
  })

  it('posts the prompt and returns the response unchanged', async () => {
    const result = { conversation_id: 'conv_redwood_test', answer: 'Answer [8]', citations: [], invalid_source_ids: [] }
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)))
    vi.stubGlobal('fetch', fetch)
    expect(await generateBriefing('Prepare Redwood')).toEqual(result)
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/briefings$/), {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: 'Prepare Redwood' }),
    })
  })

  it('sends only the new prompt and opaque ID for a follow-up', async () => {
    const result = { conversation_id: 'opaque-existing-id', answer: 'Meeting notes', citations: [], invalid_source_ids: [] }
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)))
    vi.stubGlobal('fetch', fetch)
    const response = await generateBriefing('What did they discuss?', result.conversation_id)
    expect(response.conversation_id).toBe(result.conversation_id)
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ prompt: 'What did they discuss?', conversation_id: result.conversation_id })
  })

  it('omits a null conversation ID on a new request', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ conversation_id: 'new-id', answer: '', citations: [], invalid_source_ids: [] })))
    vi.stubGlobal('fetch', fetch)
    await generateBriefing('Prepare Redwood', null)
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ prompt: 'Prepare Redwood' })
  })

  it('handles network and API failures without exposing internal responses', async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response('private failure', { status: 502 }))
      .mockResolvedValueOnce(new Response('validation details', { status: 422 }))
    vi.stubGlobal('fetch', fetch)
    await expect(generateBriefing('x')).rejects.toThrow('Unable to reach Northstar')
    await expect(generateBriefing('x')).rejects.toThrow('Please try again')
    await expect(generateBriefing('x')).rejects.toThrow('between 1 and 10,000')
  })
})
