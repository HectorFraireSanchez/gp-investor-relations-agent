import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, ArrowUpRight, Check, Layers, LoaderCircle, Plus, TriangleAlert } from 'lucide-react'
import { generateBriefing } from './api/briefings'
import { Briefing } from './components/Briefing'
import { SourceDrawer } from './components/SourceDrawer'
import type { Citation, RenderedResponse } from './types/briefing'

const examples = [
  { label: 'Redwood meeting prep', prompt: 'Prepare me for my meeting with Redwood Family Office. Include its investment position, outstanding capital calls, special reporting obligations, and our most recent discussion.' },
  { label: 'Beacon reporting obligations', prompt: 'What special reporting obligations apply to Beacon University Endowment?' },
  { label: 'Redwood capital calls', prompt: 'What outstanding capital calls does Redwood Family Office have?' },
]

type ConversationMessage =
  | { id: number; role: 'user'; content: string }
  | { id: number; role: 'assistant'; response: RenderedResponse }

export default function App() {
  const [prompt, setPrompt] = useState('')
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Citation | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const history = useRef<HTMLDivElement>(null)
  const followLatest = useRef(true)
  const inFlight = useRef(false)
  const citationTrigger = useRef<HTMLElement | null>(null)
  const nextMessageId = useRef(0)
  const loading = pendingPrompt !== null
  const hasConversation = messages.length > 0

  useLayoutEffect(() => {
    const pane = history.current
    if (!pane) return
    if (!hasConversation && !loading && !error) pane.scrollTop = 0
    else if (followLatest.current) pane.scrollTop = pane.scrollHeight
  }, [messages, pendingPrompt, error, hasConversation, loading])

  useLayoutEffect(() => {
    if (!input.current) return
    input.current.style.height = 'auto'
    input.current.style.height = `${Math.min(input.current.scrollHeight, 144)}px`
  }, [prompt])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const submittedPrompt = prompt.trim()
    if (inFlight.current || !submittedPrompt) return
    inFlight.current = true
    followLatest.current = true
    setPendingPrompt(submittedPrompt)
    setError(null)
    try {
      const { conversation_id: returnedId, ...response } = await generateBriefing(submittedPrompt, conversationId)
      if (typeof returnedId !== 'string' || !returnedId.trim() || (conversationId !== null && returnedId !== conversationId)) {
        throw new Error('The response could not be linked to this conversation. Please start a new conversation.')
      }
      const userMessage: ConversationMessage = { id: nextMessageId.current++, role: 'user', content: submittedPrompt }
      const assistantMessage: ConversationMessage = { id: nextMessageId.current++, role: 'assistant', response }
      setMessages((previous) => [...previous, userMessage, assistantMessage])
      setConversationId(returnedId)
      setPrompt('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Something went wrong. Please try again.')
    } finally {
      inFlight.current = false
      setPendingPrompt(null)
    }
  }

  function newConversation() {
    if (inFlight.current) return
    followLatest.current = true
    setConversationId(null)
    setMessages([])
    setError(null)
    setSelected(null)
    citationTrigger.current = null
    setPrompt('')
    input.current?.focus()
  }

  const selectCitation = useCallback((citation: Citation) => {
    citationTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setSelected(citation)
  }, [])

  return <div className="flex h-dvh flex-col overflow-hidden">
    <a href="#prompt" className="skip-link">Skip to meeting request</a>
    <header className="shrink-0 border-b border-line bg-white">
      <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-4 px-5 py-3 sm:px-9">
        <div className="flex items-center gap-3">
          <img src="/northstar.svg" width="34" height="34" alt="" />
          <div><p className="font-serif text-[23px] leading-none tracking-tight text-ink">Northstar</p>
            <p className="mt-1 text-[9px] font-medium uppercase tracking-[0.17em] text-muted">Investor Intelligence</p></div>
        </div>
        <span className="rounded-full border border-line bg-canvas px-3 py-1.5 text-[10px] font-medium text-muted">Synthetic data demo</span>
      </div>
    </header>

    <main className="mx-auto flex min-h-0 w-full max-w-[1040px] flex-1 flex-col px-3 pt-3 sm:px-6 sm:pt-5">
      <p className="sr-only" role="status">{loading ? 'Northstar is preparing a response. This may take a moment.' : hasConversation && !error ? 'Your response is ready.' : ''}</p>
      <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-t-xl border border-b-0 border-line bg-white shadow-sm" aria-labelledby="briefing-heading">
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3 sm:px-7 sm:py-4">
          <div>
            <h1 className="font-serif text-xl tracking-tight text-ink sm:text-2xl">Investor Meeting Prep</h1>
            <div className="mt-1 flex items-center gap-2 text-muted"><Layers size={12} strokeWidth={1.7} />
              <h2 id="briefing-heading" className="text-xs">{hasConversation ? 'Your investor conversation' : 'Your meeting briefing'}</h2></div>
          </div>
          <div className="flex items-center gap-3">
            <span className={`hidden items-center gap-1.5 text-xs sm:flex ${hasConversation ? 'text-forest' : 'text-muted'}`}>
              {loading ? 'In progress' : hasConversation ? <><Check size={13} />Ready to review</> : 'Awaiting your request'}
            </span>
            {hasConversation && <button type="button" className="secondary-button text-xs" disabled={loading} onClick={newConversation}>New conversation</button>}
          </div>
        </div>
        <div ref={history} role="region" aria-label="Conversation history" tabIndex={0} aria-busy={loading}
          onScroll={(event) => {
            const pane = event.currentTarget
            followLatest.current = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 80
          }}
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-6 [scrollbar-gutter:stable] sm:px-8 sm:py-8">
            {hasConversation ? <div>
              <ol className="space-y-9" aria-label="Conversation">
                {messages.map((message) => <li key={message.id}>
                  {message.role === 'user' ? <div className="rounded-lg border border-line bg-canvas/60 px-5 py-4">
                    <p className="eyebrow mb-2">Investor request</p>
                    <p className="whitespace-pre-wrap break-words text-sm leading-7 text-ink">{message.content}</p>
                  </div> : <article aria-label="Northstar response">
                    <p className="eyebrow mb-5">Northstar</p>
                    <Briefing response={message.response} onSelect={selectCitation} />
                  </article>}
                </li>)}
              </ol>
              {loading && <div className="mt-9 border-t border-line pt-6" data-testid="follow-up-loading">
                <p className="eyebrow mb-2">Pending request</p>
                <p className="mb-4 whitespace-pre-wrap break-words text-sm leading-7 text-ink">{pendingPrompt}</p>
                <p className="flex items-center gap-3 text-sm text-muted"><LoaderCircle size={16} className="motion-safe:animate-spin" />Northstar is preparing a response…</p>
              </div>}
              {error && <div role="alert" className="mt-7 rounded-lg border border-amber-200 bg-amber-50 p-5">
                <p className="mb-4 text-sm leading-6 text-amber-900">{error}</p>
                <button className="secondary-button" onClick={() => input.current?.form?.requestSubmit()}>Try again<ArrowRight size={14} /></button>
              </div>}
            </div> : loading ? <div className="min-h-[370px]" data-testid="loading-state">
              <div className="mb-9 flex items-center gap-3 text-sm text-muted"><LoaderCircle className="motion-safe:animate-spin text-forest" size={18} />Preparing your investor briefing…</div>
              <div aria-hidden="true" className="space-y-7 motion-safe:animate-pulse">
                {[0, 1, 2].map((index) => <div key={index} className="space-y-3"><div className="skeleton h-4 w-2/5" /><div className="skeleton h-2.5 w-full" /><div className="skeleton h-2.5 w-11/12" /><div className="skeleton h-2.5 w-4/5" /></div>)}
              </div>
            </div> : error ? <div role="alert" className="flex min-h-[370px] flex-col items-center justify-center text-center">
              <span className="mb-5 rounded-full bg-amber-50 p-4 text-amber-800"><TriangleAlert size={25} strokeWidth={1.5} /></span>
              <h3 className="font-serif text-2xl text-ink">The briefing couldn’t be completed</h3>
              <p className="mb-6 mt-3 max-w-sm text-sm leading-6 text-muted">{error}</p>
              <button className="secondary-button" onClick={() => input.current?.form?.requestSubmit()}>Try again<ArrowRight size={14} /></button>
            </div> :
              <div className="flex min-h-[370px] flex-col items-center justify-center py-5 text-center">
                <div aria-hidden="true" className="relative mb-7 flex h-20 w-16 rotate-[-5deg] flex-col gap-2 rounded-lg border border-line bg-canvas px-3.5 py-4 shadow-sm">
                  <div className="h-1.5 w-6 rounded bg-forest/40" /><div className="mt-1 h-1 w-full rounded bg-line" /><div className="h-1 w-full rounded bg-line" /><div className="h-1 w-5 rounded bg-line" />
                  <span className="absolute -bottom-2 -right-3 rounded-full border-4 border-white bg-forest p-1 text-white"><Plus size={14} /></span>
                </div>
                <h3 className="font-serif text-[26px] tracking-tight text-ink">Preparation starts here.</h3>
                <p className="mt-3 max-w-[320px] text-sm leading-7 text-muted">Choose an investor and tell us what matters.<br className="hidden sm:block" /> Your briefing and its sources will appear here.</p>
                <div className="mt-7 flex w-full max-w-lg flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-center">
                  {examples.map((example) => <button key={example.label} type="button" className="example-button"
                    onClick={() => { setPrompt(example.prompt); input.current?.focus() }}><span>{example.label}</span><ArrowUpRight size={14} aria-hidden="true" /></button>)}
                </div>
              </div>}
        </div>
        <form onSubmit={submit} aria-label="Briefing request" className="shrink-0 border-t border-line bg-white px-3 pb-3 pt-3 sm:px-6 sm:pb-4">
          <label htmlFor="prompt" className="mb-2 block text-xs font-medium text-ink">{hasConversation ? 'Ask a follow-up' : 'Who are you meeting with?'}</label>
          <div className="flex items-end gap-2 rounded-xl border border-line bg-canvas/60 p-2 focus-within:border-forest/50 sm:gap-3">
            <textarea ref={input} id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} readOnly={loading}
              maxLength={10000} rows={2} aria-describedby="prompt-hint" placeholder={hasConversation ? 'Ask about the meeting, position, capital calls, or reporting obligations…' : 'Prepare me for my meeting with Redwood Family Office…'}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.nativeEvent.isComposing && (!event.shiftKey || event.ctrlKey || event.metaKey)) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
              className="max-h-36 min-h-14 w-full resize-none bg-transparent px-2 py-1 text-sm leading-6 text-ink placeholder:text-muted/80 read-only:opacity-60" />
            <button type="submit" disabled={loading || !prompt.trim()} className="primary-button shrink-0 px-3 sm:px-4"
              aria-label={loading ? (hasConversation ? 'Preparing response…' : 'Generating briefing…') : (hasConversation ? 'Ask Northstar' : 'Generate briefing')}>
              {loading ? <LoaderCircle size={17} className="motion-safe:animate-spin" /> : <ArrowRight size={17} />}
              <span className="hidden sm:inline">{loading ? 'Preparing…' : hasConversation ? 'Ask Northstar' : 'Generate briefing'}</span>
            </button>
          </div>
          <p id="prompt-hint" className="mt-2 text-[10px] leading-4 text-muted">Enter to send · Shift + Enter for a new line</p>
        </form>
      </section>
      <footer className="shrink-0 px-2 py-2 text-center text-[10px] leading-4 text-muted [padding-bottom:max(0.5rem,env(safe-area-inset-bottom))]">Prepared with AI assistance. Review each answer and its sources before your meeting.</footer>
    </main>
    <SourceDrawer citation={selected} onClose={() => setSelected(null)} returnFocus={() => citationTrigger.current?.focus()} />
  </div>
}
