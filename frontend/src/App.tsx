import { useCallback, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, ArrowUpRight, BookOpen, Check, FileText, Layers, LoaderCircle, Plus, TriangleAlert } from 'lucide-react'
import { generateBriefing } from './api/briefings'
import { Briefing } from './components/Briefing'
import { SourceDrawer } from './components/SourceDrawer'
import type { Citation, RenderedResponse } from './types/briefing'

const examples = [
  { label: 'Redwood meeting prep', prompt: 'Prepare me for my meeting with Redwood Family Office. Include its investment position, outstanding capital calls, special reporting obligations, and our most recent discussion.' },
  { label: 'Beacon reporting obligations', prompt: 'What special reporting obligations apply to Beacon University Endowment?' },
  { label: 'Redwood capital calls', prompt: 'What outstanding capital calls does Redwood Family Office have?' },
]

export default function App() {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<RenderedResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Citation | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const inFlight = useRef(false)
  const citationTrigger = useRef<HTMLElement | null>(null)
  const resultHeading = useRef<HTMLHeadingElement>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (inFlight.current || !prompt.trim()) return
    inFlight.current = true
    setLoading(true)
    setError(null)
    setResponse(null)
    setSelected(null)
    try {
      setResponse(await generateBriefing(prompt))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Something went wrong. Please try again.')
    } finally {
      inFlight.current = false
      setLoading(false)
      resultHeading.current?.focus({ preventScroll: true })
    }
  }

  const selectCitation = useCallback((citation: Citation) => {
    citationTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setSelected(citation)
  }, [])

  return <div className="min-h-screen">
    <a href="#prompt" className="skip-link">Skip to meeting request</a>
    <header className="border-b border-line bg-white">
      <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-4 px-5 py-5 sm:px-9 lg:px-12">
        <div className="flex items-center gap-3">
          <img src="/northstar.svg" width="38" height="38" alt="" />
          <div><p className="font-serif text-[25px] leading-none tracking-tight text-ink">Northstar</p>
            <p className="mt-1.5 text-[10px] font-medium uppercase tracking-[0.17em] text-muted">Investor Intelligence</p></div>
        </div>
        <span className="rounded-full border border-line bg-canvas px-3 py-1.5 text-[11px] font-medium text-muted">Synthetic data demo</span>
      </div>
    </header>

    <main className="mx-auto max-w-[1320px] px-5 pb-14 pt-9 sm:px-9 sm:pt-12 lg:px-12">
      <div className="mb-9 max-w-2xl">
        <p className="eyebrow mb-3">The investor workspace</p>
        <h1 className="font-serif text-[34px] leading-tight tracking-tight text-ink sm:text-[42px]">Investor Meeting Prep</h1>
        <p className="mt-4 max-w-xl text-[15px] leading-7 text-muted">Walk into the conversation informed. Create source-grounded briefings from structured fund data and investor documents.</p>
      </div>

      <div className="grid items-start gap-7 lg:grid-cols-[350px_minmax(0,1fr)] xl:grid-cols-[370px_minmax(0,1fr)] xl:gap-9">
        <aside className="space-y-5 lg:sticky lg:top-7" aria-label="Briefing request">
          <form onSubmit={submit} className="rounded-xl border border-line bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center gap-2.5 text-ink"><FileText size={18} strokeWidth={1.6} /><h2 className="text-sm font-semibold">Set the context</h2></div>
            <label htmlFor="prompt" className="mb-2 block text-sm font-medium text-ink">Who are you meeting with?</label>
            <textarea ref={input} id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} disabled={loading}
              maxLength={10000} rows={6} aria-describedby="prompt-hint" placeholder="Prepare me for my meeting with Redwood Family Office…"
              onKeyDown={(event) => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') event.currentTarget.form?.requestSubmit() }}
              className="w-full resize-y rounded-lg border border-line bg-canvas/50 px-3.5 py-3 text-sm leading-6 text-ink placeholder:text-muted/80 disabled:opacity-60" />
            <p id="prompt-hint" className="mb-5 mt-2 text-xs leading-5 text-muted">Add an investor and the topics you want to cover.</p>
            <button type="submit" disabled={loading || !prompt.trim()} className="primary-button w-full">
              {loading ? <><LoaderCircle size={16} className="motion-safe:animate-spin" />Generating briefing…</> : <>Generate briefing<ArrowRight size={16} /></>}
            </button>
            <div className="mt-6 border-t border-line pt-5">
              <p className="mb-3 text-xs font-medium text-muted">Or start with an example</p>
              <div className="flex flex-col gap-2">
                {examples.map((example) => <button key={example.label} type="button" disabled={loading} className="example-button"
                  onClick={() => { setPrompt(example.prompt); input.current?.focus() }}><span>{example.label}</span><ArrowUpRight size={14} aria-hidden="true" /></button>)}
              </div>
            </div>
          </form>
          <div className="rounded-xl border border-[#dbe5de] bg-[#edf2ed] p-5">
            <div className="mb-2 flex items-center gap-2 text-forest"><BookOpen size={16} /><h3 className="text-xs font-semibold">A clear path back to the source</h3></div>
            <p className="text-xs leading-6 text-[#52655c]">Open any numbered citation to inspect the database record or document behind your briefing.</p>
          </div>
        </aside>

        <section className="min-w-0 overflow-hidden rounded-xl border border-line bg-white shadow-sm" aria-labelledby="briefing-heading" aria-busy={loading}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-5 sm:px-8">
            <div className="flex items-center gap-2.5"><Layers size={17} className="text-muted" strokeWidth={1.7} />
              <h2 id="briefing-heading" ref={resultHeading} tabIndex={-1} className="text-sm font-semibold text-ink">Your meeting briefing</h2></div>
            <span className={`flex items-center gap-1.5 text-xs ${response ? 'text-forest' : 'text-muted'}`}>
              {response ? <><Check size={13} />Ready to review</> : loading ? 'In progress' : 'Awaiting your request'}
            </span>
          </div>
          <div className="px-6 py-8 sm:px-9 sm:py-9">
            <p className="sr-only" role="status">{loading ? 'Generating your briefing. This may take a moment.' : response ? 'Your briefing is ready.' : ''}</p>
            {loading ? <div className="min-h-[370px]" data-testid="loading-state">
              <div className="mb-9 flex items-center gap-3 text-sm text-muted"><LoaderCircle className="motion-safe:animate-spin text-forest" size={18} />Preparing your investor briefing…</div>
              <div aria-hidden="true" className="space-y-7 motion-safe:animate-pulse">
                {[0, 1, 2].map((index) => <div key={index} className="space-y-3"><div className="skeleton h-4 w-2/5" /><div className="skeleton h-2.5 w-full" /><div className="skeleton h-2.5 w-11/12" /><div className="skeleton h-2.5 w-4/5" /></div>)}
              </div>
            </div> : error ? <div role="alert" className="flex min-h-[370px] flex-col items-center justify-center text-center">
              <span className="mb-5 rounded-full bg-amber-50 p-4 text-amber-800"><TriangleAlert size={25} strokeWidth={1.5} /></span>
              <h3 className="font-serif text-2xl text-ink">The briefing couldn’t be completed</h3>
              <p className="mb-6 mt-3 max-w-sm text-sm leading-6 text-muted">{error}</p>
              <button className="secondary-button" onClick={() => input.current?.form?.requestSubmit()}>Try again<ArrowRight size={14} /></button>
            </div> : response ? <Briefing response={response} onSelect={selectCitation} /> :
              <div className="flex min-h-[370px] flex-col items-center justify-center py-5 text-center">
                <div aria-hidden="true" className="relative mb-7 flex h-20 w-16 rotate-[-5deg] flex-col gap-2 rounded-lg border border-line bg-canvas px-3.5 py-4 shadow-sm">
                  <div className="h-1.5 w-6 rounded bg-forest/40" /><div className="mt-1 h-1 w-full rounded bg-line" /><div className="h-1 w-full rounded bg-line" /><div className="h-1 w-5 rounded bg-line" />
                  <span className="absolute -bottom-2 -right-3 rounded-full border-4 border-white bg-forest p-1 text-white"><Plus size={14} /></span>
                </div>
                <h3 className="font-serif text-[26px] tracking-tight text-ink">Preparation starts here.</h3>
                <p className="mt-3 max-w-[320px] text-sm leading-7 text-muted">Choose an investor and tell us what matters.<br className="hidden sm:block" /> Your briefing and its sources will appear here.</p>
                <div className="mt-8 flex flex-wrap justify-center gap-x-5 gap-y-2 text-[11px] text-muted"><span>Fund positions</span><span>Capital calls</span><span>Document context</span></div>
              </div>}
          </div>
          <div className="border-t border-line bg-canvas/40 px-6 py-3.5 text-[11px] leading-5 text-muted sm:px-8">Prepared with AI assistance. Review the briefing and its sources before your meeting.</div>
        </section>
      </div>
      <footer className="mt-10 flex flex-wrap justify-between gap-2 border-t border-line pt-5 text-[11px] text-muted"><span>Northstar Capital · Investor Relations</span><span>Fictional investors. Real preparation workflow.</span></footer>
    </main>
    <SourceDrawer citation={selected} onClose={() => setSelected(null)} returnFocus={() => citationTrigger.current?.focus()} />
  </div>
}
