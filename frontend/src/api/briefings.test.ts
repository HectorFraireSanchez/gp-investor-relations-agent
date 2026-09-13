import { afterEach, describe, expect, it, vi } from 'vitest'
import { generateBriefing } from './briefings'

afterEach(() => vi.unstubAllGlobals())

describe('briefing transport', () => {
  it('posts the prompt and returns the response unchanged', async () => {
    const result = { answer: 'Answer [8]', citations: [], invalid_source_ids: [] }
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)))
    vi.stubGlobal('fetch', fetch)
    expect(await generateBriefing('Prepare Redwood')).toEqual(result)
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/briefings$/), {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: 'Prepare Redwood' }),
    })
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
