import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { generateBriefing } from './api/briefings'
import type { BriefingResponse } from './types/briefing'

vi.mock('./api/briefings', () => ({ generateBriefing: vi.fn() }))
const generate = vi.mocked(generateBriefing)
const result: BriefingResponse = {
  conversation_id: 'conv_redwood_test',
  answer: 'Capital call [3]. Repeated [3].',
  citations: [{ number: 3, source_id: 'db:capital_calls:CC-019', source: { source_id: 'db:capital_calls:CC-019', source_type: 'database', table: 'capital_calls', record_key: { call_id: 'CC-019' } } }],
  invalid_source_ids: [],
}

const followUp: BriefingResponse = {
  conversation_id: result.conversation_id,
  answer: 'The meeting covered AI automation [3].',
  citations: [{ number: 3, source_id: 'doc:redwood_meeting_notes_2026_08_14.md', source: {
    source_id: 'doc:redwood_meeting_notes_2026_08_14.md', source_type: 'document', filename: 'redwood_meeting_notes_2026_08_14.md',
  } }],
  invalid_source_ids: [],
}

async function startConversation() {
  render(<App />)
  await userEvent.type(screen.getByRole('textbox'), '  Prepare Redwood  ')
  await userEvent.click(screen.getByRole('button', { name: 'Generate briefing' }))
  await screen.findByText('Ready to review')
}

beforeEach(() => { generate.mockReset() })

describe('meeting preparation', () => {
  it('shows the empty state and fills an example without making an API call', async () => {
    render(<App />)
    expect(screen.getByText('Preparation starts here.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generate briefing' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Redwood meeting prep' }))
    expect((screen.getByRole('textbox') as HTMLTextAreaElement).value).toContain('Redwood Family Office')
    expect(screen.getByRole('textbox')).toHaveFocus()
    expect(generate).not.toHaveBeenCalled()
  })

  it('prevents duplicate requests and opens the correct drawer from repeated citations', async () => {
    let finish!: (response: BriefingResponse) => void
    generate.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Redwood capital calls' }))
    const form = screen.getByRole('textbox').closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    expect(generate).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('loading-state')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Generating briefing/ })).toBeDisabled()
    await act(async () => finish(result))
    expect(generate).toHaveBeenCalledWith('What outstanding capital calls does Redwood Family Office have?', null)
    expect(screen.getByText('What outstanding capital calls does Redwood Family Office have?')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('')
    expect(screen.queryByText(result.conversation_id)).not.toBeInTheDocument()
    const references = screen.getAllByRole('button', { name: 'Source 3: Capital Call CC-019' })
    for (const reference of references) {
      await userEvent.click(reference)
      expect(screen.getByRole('dialog')).toHaveTextContent('Capital Call CC-019')
      expect(screen.getByRole('dialog')).toHaveTextContent('capital_calls')
      await userEvent.keyboard('{Escape}')
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      await waitFor(() => expect(reference).toHaveFocus())
    }
  })

  it('shows an error, keeps the prompt, and allows a successful retry', async () => {
    generate.mockRejectedValueOnce(new Error('Unable to reach Northstar.')).mockResolvedValueOnce(result)
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Redwood capital calls' }))
    await userEvent.click(screen.getByRole('button', { name: 'Generate briefing' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach Northstar.')
    expect(screen.getByRole('textbox')).toHaveValue('What outstanding capital calls does Redwood Family Office have?')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Ready to review')).toBeInTheDocument()
    expect(generate).toHaveBeenCalledTimes(2)
  })

  it('retains turns while loading and keeps each answer’s citations independent', async () => {
    let finish!: (response: BriefingResponse) => void
    generate.mockResolvedValueOnce(result).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    await startConversation()
    expect(generate).toHaveBeenNthCalledWith(1, 'Prepare Redwood', null)
    expect(screen.queryByRole('button', { name: 'Redwood meeting prep' })).not.toBeInTheDocument()
    await userEvent.type(screen.getByRole('textbox'), 'What did they discuss?')
    const form = screen.getByRole('textbox').closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    expect(generate).toHaveBeenNthCalledWith(2, 'What did they discuss?', result.conversation_id)
    expect(generate).toHaveBeenCalledTimes(2)
    expect(screen.getByText('Prepare Redwood')).toBeInTheDocument()
    expect(screen.getByRole('article')).toHaveTextContent('Capital call')
    expect(screen.getByTestId('follow-up-loading')).toHaveTextContent('What did they discuss?')
    expect(screen.queryByTestId('loading-state')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New conversation' })).toBeDisabled()
    await act(async () => finish(followUp))
    expect(screen.getByRole('textbox')).toHaveValue('')
    expect(screen.getByText('What did they discuss?')).toBeInTheDocument()
    const answers = screen.getAllByRole('article')
    expect(answers).toHaveLength(2)
    expect(answers[0]).toHaveTextContent('Capital call')
    expect(answers[1]).toHaveTextContent('AI automation')
    const headings = screen.getAllByRole('heading', { name: 'Sources' })
    expect(new Set(headings.map((heading) => heading.id)).size).toBe(2)
    for (const [index, text] of ['CC-019', 'redwood_meeting_notes_2026_08_14.md'].entries()) {
      const reference = within(answers[index]).getAllByRole('button', { name: /^Source 3:/ })[0]
      await userEvent.click(reference)
      expect(screen.getByRole('dialog')).toHaveTextContent(text)
      await userEvent.keyboard('{Escape}')
      await waitFor(() => expect(reference).toHaveFocus())
    }
  })

  it('preserves a failed follow-up and retries using the same ID without duplicating turns', async () => {
    generate.mockResolvedValueOnce(result).mockRejectedValueOnce(new Error('Unable to reach Northstar.')).mockResolvedValueOnce(followUp)
    await startConversation()
    await userEvent.type(screen.getByRole('textbox'), 'What did they discuss?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask Northstar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach Northstar.')
    expect(screen.getByRole('textbox')).toHaveValue('What did they discuss?')
    expect(screen.getAllByRole('article')).toHaveLength(1)
    expect(screen.getByText('Prepare Redwood')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(2))
    expect(generate).toHaveBeenNthCalledWith(3, 'What did they discuss?', result.conversation_id)
    expect(screen.getAllByText('Prepare Redwood')).toHaveLength(1)
    expect(screen.getAllByText('What did they discuss?')).toHaveLength(1)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('starts a new local conversation without carrying forward the old ID or messages', async () => {
    generate.mockResolvedValueOnce(result).mockRejectedValueOnce(new Error('Please try again.'))
      .mockResolvedValueOnce({ ...result, conversation_id: 'conv_beacon_test', answer: 'Beacon reporting.' })
    await startConversation()
    await userEvent.type(screen.getByRole('textbox'), 'Failed follow-up')
    await userEvent.click(screen.getByRole('button', { name: 'Ask Northstar' }))
    await screen.findByRole('alert')
    await userEvent.click(screen.getByRole('button', { name: 'New conversation' }))
    expect(screen.getByText('Preparation starts here.')).toBeInTheDocument()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('')
    expect(screen.getByRole('textbox')).toHaveFocus()
    await userEvent.type(screen.getByRole('textbox'), 'Prepare Beacon')
    await userEvent.click(screen.getByRole('button', { name: 'Generate briefing' }))
    expect(await screen.findByText('Beacon reporting.')).toBeInTheDocument()
    expect(generate).toHaveBeenNthCalledWith(3, 'Prepare Beacon', null)
  })

  it('rejects an unexpected conversation switch without mixing answers or changing the existing ID', async () => {
    generate.mockResolvedValueOnce(result).mockResolvedValueOnce({ ...followUp, conversation_id: 'conv_other_test' }).mockResolvedValueOnce(followUp)
    await startConversation()
    await userEvent.type(screen.getByRole('textbox'), 'What did they discuss?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask Northstar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be linked')
    expect(screen.getAllByRole('article')).toHaveLength(1)
    expect(screen.getByRole('textbox')).toHaveValue('What did they discuss?')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(2))
    expect(generate).toHaveBeenNthCalledWith(3, 'What did they discuss?', result.conversation_id)
  })

  it.each(['ctrlKey', 'metaKey'])('submits a follow-up with %s + Enter and keeps textarea focus', async (key) => {
    generate.mockResolvedValueOnce(result).mockResolvedValueOnce(followUp)
    await startConversation()
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'What did they discuss?')
    fireEvent.keyDown(textarea, { key: 'Enter', [key]: true })
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(2))
    expect(generate).toHaveBeenCalledTimes(2)
    expect(textarea).toHaveFocus()
  })

  it('uses Enter to send, preserves Shift+Enter, and does not send during IME composition', async () => {
    generate.mockResolvedValueOnce(result)
    render(<App />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'Prepare Redwood')
    await userEvent.keyboard('{Shift>}{Enter}{/Shift}')
    expect(textarea).toHaveValue('Prepare Redwood\n')
    fireEvent.keyDown(textarea, { key: 'Enter', isComposing: true })
    expect(generate).not.toHaveBeenCalled()
    await userEvent.keyboard('{Enter}')
    await screen.findByText('Ready to review')
    expect(generate).toHaveBeenCalledExactlyOnceWith('Prepare Redwood', null)
    expect(textarea).toHaveFocus()
  })
})
