import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { generateBriefing } from './api/briefings'
import type { RenderedResponse } from './types/briefing'

vi.mock('./api/briefings', () => ({ generateBriefing: vi.fn() }))
const generate = vi.mocked(generateBriefing)
const result: RenderedResponse = {
  answer: 'Capital call [3]. Repeated [3].',
  citations: [{ number: 3, source_id: 'db:capital_calls:CC-019', source: { source_id: 'db:capital_calls:CC-019', source_type: 'database', table: 'capital_calls', record_key: { call_id: 'CC-019' } } }],
  invalid_source_ids: [],
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
    let finish!: (response: RenderedResponse) => void
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
})
