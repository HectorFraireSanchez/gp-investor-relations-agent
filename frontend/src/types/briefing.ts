export interface Source {
  source_id: string
  source_type?: string
  database?: string
  schema?: string
  table?: string
  record_key?: Record<string, unknown>
  filename?: string
  file_id?: string
  [key: string]: unknown
}

export interface Citation {
  number: number
  source_id: string
  source: Source
}

export interface RenderedResponse {
  answer: string
  citations: Citation[]
  invalid_source_ids: string[]
}
