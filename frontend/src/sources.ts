import type { Source } from './types/briefing'

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined
}

function title(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function sourceLabel(source: Source): string {
  const key = source.record_key ?? {}
  if (source.source_type === 'database') {
    if (source.table === 'investors') {
      return text(key.investor_id) ? `Investor Record — ${key.investor_id}` : 'Investor Record'
    }
    if (source.table === 'positions') {
      return text(key.fund) ? `${key.fund} — Position` : 'Fund Position'
    }
    if (source.table === 'capital_calls') {
      return text(key.call_id) ? `Capital Call ${key.call_id}` : 'Capital Call'
    }
    return text(source.table) ? `${title(source.table!)} — Record` : 'Database Record'
  }
  if (source.source_type === 'document' && text(source.filename)) {
    const stem = source.filename!.replace(/\.[^.]+$/, '')
    const dated = stem.match(/^(.*)_(\d{4})_(\d{2})_(\d{2})$/)
    if (dated) {
      const [, name, year, month, day] = dated
      const date = new Date(`${year}-${month}-${day}T00:00:00Z`)
      // Only interpret a real calendar date encoded in the authoritative filename.
      if (!Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === `${year}-${month}-${day}`) {
        return `${title(name)} — ${new Intl.DateTimeFormat('en-US', {
          month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
        }).format(date)}`
      }
    }
    return title(stem)
  }
  return source.source_type === 'document' ? 'Document' : 'Source Record'
}

export function sourceKind(source: Source): string {
  if (source.source_type === 'database') return 'Database record'
  if (source.source_type === 'document') return 'Document'
  return 'Source'
}

export function metadataRows(source: Source): [string, string][] {
  const labels: Record<string, string> = {
    source_type: 'Source type', database: 'Database', schema: 'Schema', table: 'Table',
    record_key: 'Record', filename: 'Filename', file_id: 'File ID', source_id: 'Source ID',
  }
  return Object.entries(source)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => [
      labels[key] ?? title(key),
      typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value),
    ])
}
