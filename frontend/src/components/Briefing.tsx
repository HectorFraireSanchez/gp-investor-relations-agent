import { memo, useId, useMemo } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Element, Root, RootContent } from 'hast'
import { ArrowUpRight, Database, FileText } from 'lucide-react'
import type { Citation, RenderedResponse } from '../types/briefing'
import { sourceKind, sourceLabel } from '../sources'

// Work on Markdown text nodes only: code, links, and raw HTML are never citation controls.
function citationReferences(numbers: Set<number>) {
  return () => (tree: Root) => {
    function walk(parent: Root | Element) {
      parent.children = parent.children.flatMap((child): RootContent[] => {
        if (child.type === 'element') {
          if (!['a', 'code', 'pre'].includes(child.tagName)) walk(child)
          return [child]
        }
        if (child.type !== 'text') return [child]
        const parts: RootContent[] = []
        let offset = 0
        for (const match of child.value.matchAll(/\[([1-9]\d*)\]/g)) {
          if (!numbers.has(Number(match[1]))) continue
          const index = match.index!
          parts.push({ type: 'text', value: child.value.slice(offset, index) })
          parts.push({ type: 'element', tagName: 'button', properties: { 'data-citation-number': match[1] },
            children: [{ type: 'text', value: match[0] }] })
          offset = index + match[0].length
        }
        parts.push({ type: 'text', value: child.value.slice(offset) })
        return parts
      })
    }
    walk(tree)
  }
}

export const Briefing = memo(function Briefing({ response, onSelect }: { response: RenderedResponse; onSelect: (citation: Citation) => void }) {
  const sourcesHeadingId = useId()
  const citations = useMemo(() => new Map(response.citations.map((citation) => [citation.number, citation])), [response])
  const plugin = useMemo(() => citationReferences(new Set(citations.keys())), [citations])
  return <>
    <div className="briefing-markdown">
      <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[plugin]} skipHtml components={{
        button: ({ node, children }) => {
          const citation = citations.get(Number(node?.properties['data-citation-number']))
          if (!citation) return <>{children}</>
          return <button type="button" className="citation-button" onClick={() => onSelect(citation)}
            aria-label={`Source ${citation.number}: ${sourceLabel(citation.source)}`} aria-haspopup="dialog">{children}</button>
        },
        table: ({ children }) => <div className="table-scroll"><table>{children}</table></div>,
        a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
        img: ({ alt }) => <span>{alt}</span>,
      }}>{response.answer}</Markdown>
    </div>
    {response.invalid_source_ids.length > 0 && <p className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
      Some references were unavailable. Review those claims before using this briefing.
    </p>}
    <section className="mt-10 border-t border-line pt-7" aria-labelledby={sourcesHeadingId}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 id={sourcesHeadingId} className="text-sm font-semibold text-ink">Sources</h3>
        <span className="text-xs text-muted">{response.citations.length} referenced</span>
      </div>
      {response.citations.length === 0 ? <p className="text-sm text-muted">No sources were cited in this response.</p> :
        <ol className="space-y-2">
          {response.citations.map((citation) => {
            const Icon = citation.source.source_type === 'database' ? Database : FileText
            return <li key={citation.number}>
              <button className="source-row" onClick={() => onSelect(citation)} aria-haspopup="dialog">
                <span className="source-number">{citation.number}</span>
                <span className="min-w-0 flex-1 text-left">
                  <span className="block text-sm font-medium text-ink">{sourceLabel(citation.source)}</span>
                  <span className="mt-1 flex items-center gap-1.5 text-xs text-muted"><Icon size={12} />{sourceKind(citation.source)}</span>
                </span>
                <ArrowUpRight size={16} className="shrink-0 text-muted" aria-hidden="true" />
              </button>
            </li>
          })}
        </ol>}
    </section>
  </>
})
