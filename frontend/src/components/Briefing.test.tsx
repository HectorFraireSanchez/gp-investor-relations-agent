import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Briefing } from './Briefing'
import { metadataRows, sourceLabel } from '../sources'
import type { Citation } from '../types/briefing'

const database: Citation = {
  number: 7, source_id: 'db:capital_calls:CC-019',
  source: { source_id: 'db:capital_calls:CC-019', source_type: 'database', database: 'northstar.db', table: 'capital_calls', record_key: { call_id: 'CC-019' } },
}
const document: Citation = {
  number: 2, source_id: 'doc:redwood_meeting_notes_2026_08_14.md',
  source: { source_id: 'doc:redwood_meeting_notes_2026_08_14.md', source_type: 'document', filename: 'redwood_meeting_notes_2026_08_14.md' },
}

describe('citation references', () => {
  it('uses backend numbers and the exact returned object, including repeated references', () => {
    const onSelect = vi.fn()
    render(<Briefing response={{ answer: '**Call [7]**. Meeting [2]. Again [7].', citations: [document, database], invalid_source_ids: [] }} onSelect={onSelect} />)
    const buttons = screen.getAllByRole('button', { name: 'Source 7: Capital Call CC-019' })
    expect(buttons).toHaveLength(2)
    buttons.forEach((button) => fireEvent.click(button))
    expect(onSelect.mock.calls[0][0]).toBe(database)
    expect(onSelect.mock.calls[1][0]).toBe(database)
    fireEvent.click(screen.getByRole('button', { name: /Source 2:/ }))
    expect(onSelect.mock.calls[2][0]).toBe(document)
  })

  it('preserves unknown numbers, code, links, and unavailable markers without granting trust', () => {
    const { container } = render(<Briefing response={{
      answer: 'Unknown [99]. [citation unavailable]. Code `[7]`. [Link [7]](https://example.com)\n\n<script>alert(1)</script>',
      citations: [database], invalid_source_ids: ['private-id'],
    }} onSelect={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /^Source 7:/ })).not.toBeInTheDocument()
    expect(container.querySelector('code')).toHaveTextContent('[7]')
    expect(screen.getByRole('link')).toHaveTextContent('Link [7]')
    expect(container).toHaveTextContent('Unknown [99]')
    expect(container).toHaveTextContent('[citation unavailable]')
    expect(container).not.toHaveTextContent('private-id')
    expect(container.querySelector('script')).toBeNull()
  })

  it('handles a response with no cited sources', () => {
    render(<Briefing response={{ answer: 'No records are available.', citations: [], invalid_source_ids: [] }} onSelect={vi.fn()} />)
    expect(screen.getByText('No sources were cited in this response.')).toBeInTheDocument()
  })
})

describe('source labels', () => {
  it('uses only available database keys, without inventing investor names', () => {
    expect(sourceLabel(database.source)).toBe('Capital Call CC-019')
    expect(sourceLabel({ source_id: 'x', source_type: 'database', table: 'investors', record_key: { investor_id: 'INV-001' } })).toBe('Investor Record — INV-001')
    expect(sourceLabel({ source_id: 'x', source_type: 'database', table: 'positions', record_key: { fund: 'Northstar Growth Fund II' } })).toBe('Northstar Growth Fund II — Position')
    expect(sourceLabel({ source_id: 'x', source_type: 'database', table: 'investors' })).toBe('Investor Record')
  })

  it('formats document filenames and real filename dates deterministically', () => {
    expect(sourceLabel(document.source)).toBe('Redwood Meeting Notes — Aug 14, 2026')
    expect(sourceLabel({ source_id: 'x', source_type: 'document', filename: 'redwood_side_letter.md' })).toBe('Redwood Side Letter')
    expect(sourceLabel({ source_id: 'x', source_type: 'document', filename: 'notes_2026_02_31.md' })).toBe('Notes 2026 02 31')
    expect(sourceLabel({ source_id: 'x', source_type: 'document' })).toBe('Document')
  })

  it('shows existing metadata, including extra fields, without adding missing provenance', () => {
    const rows = metadataRows({ ...document.source, extra: { preserved: true } })
    expect(rows).toContainEqual(['Filename', document.source.filename])
    expect(rows).toContainEqual(['Extra', '{\n  "preserved": true\n}'])
    expect(rows.some(([label]) => label === 'Page' || label === 'File ID')).toBe(false)
  })
})
