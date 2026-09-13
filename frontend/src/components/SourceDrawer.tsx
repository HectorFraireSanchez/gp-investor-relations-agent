import type { Citation } from '../types/briefing'
import { metadataRows, sourceKind, sourceLabel } from '../sources'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from './ui/sheet'

interface Props {
  citation: Citation | null
  onClose: () => void
  returnFocus: () => void
}

export function SourceDrawer({ citation, onClose, returnFocus }: Props) {
  return <Sheet open={citation !== null} onOpenChange={(open) => { if (!open) onClose() }}>
    <SheetContent onCloseAutoFocus={(event) => { event.preventDefault(); returnFocus() }}>
      {citation && <>
        <p className="eyebrow mb-7 mt-2">Source details</p>
        <span className="source-number mb-5 inline-flex">{citation.number}</span>
        <SheetTitle className="font-serif text-2xl leading-snug text-ink">{sourceLabel(citation.source)}</SheetTitle>
        <SheetDescription className="mb-8 mt-3 text-sm leading-6 text-muted">
          {sourceKind(citation.source)} referenced in this briefing. Metadata below comes from the returned source record.
        </SheetDescription>
        <dl className="divide-y divide-line border-y border-line">
          {metadataRows(citation.source).map(([label, value]) => <div key={label} className="py-4">
            <dt className="mb-1.5 text-xs font-medium text-muted">{label}</dt>
            <dd className="whitespace-pre-wrap break-words font-mono text-xs leading-6 text-ink">{value}</dd>
          </div>)}
        </dl>
      </>}
    </SheetContent>
  </Sheet>
}
