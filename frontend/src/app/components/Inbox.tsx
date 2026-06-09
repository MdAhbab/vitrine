import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { Bot, Send, Eye } from 'lucide-react';
import { useStore, type Role, type Thread } from '../lib/store';

export function Inbox({ role, viewer }: { role: Role; viewer: { id: string; name: string } }) {
  const { threads, messages, sendMessage, agentReply } = useStore();
  const visible = threads.filter((t) => {
    if (role === 'admin') return true;
    if (role === 'buyer') return t.buyerId === viewer.id;
    return t.sellerId === viewer.id;
  });
  const [activeId, setActiveId] = useState<string | undefined>(visible[0]?.id);
  useEffect(() => { if (!visible.find((t) => t.id === activeId)) setActiveId(visible[0]?.id); }, [visible.map((t) => t.id).join()]);

  const active = visible.find((t) => t.id === activeId);
  const msgs = messages.filter((m) => m.threadId === activeId);
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }); }, [msgs.length]);

  const send = () => {
    if (!input.trim() || !active || role === 'admin') return;
    sendMessage(active.id, input, { id: viewer.id, name: viewer.name });
    setInput('');
    if (active.isAgent && role === 'seller') {
      setTimeout(() => agentReply(active.id), 600);
    }
  };

  return (
    <div className="hairline rounded-2xl overflow-hidden bg-surface grid grid-cols-1 md:grid-cols-[300px_1fr] min-h-[520px]">
      <aside className="border-b md:border-b-0 md:border-r bg-surface-2/40 max-h-[560px] overflow-y-auto">
        <div className="px-5 py-4 border-b">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Conversations</div>
          <div className="font-serif text-lg mt-1">{visible.length} threads</div>
        </div>
        {visible.length === 0 ? (
          <div className="p-6 text-sm text-text-muted">No conversations yet.</div>
        ) : visible.map((t) => {
          const last = [...messages].reverse().find((m) => m.threadId === t.id);
          return (
            <button
              key={t.id}
              onClick={() => setActiveId(t.id)}
              className={`w-full text-left p-4 flex gap-3 border-b transition-colors ${activeId === t.id ? 'bg-surface' : 'hover:bg-surface'}`}
            >
              <img src={t.productCover} alt="" className="w-10 h-10 rounded-lg object-cover" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-serif text-sm truncate flex-1">{t.productName}</span>
                  {t.isAgent && <span className="font-mono text-[9px] uppercase tracking-wider text-accent flex items-center gap-1"><Bot size={10} />rep</span>}
                </div>
                <div className="text-xs text-text-muted truncate">
                  {role === 'seller' || role === 'admin' ? t.buyerName : t.sellerName}
                </div>
                <div className="text-xs text-text-muted truncate mt-0.5">{last?.body ?? '…'}</div>
              </div>
            </button>
          );
        })}
      </aside>

      <section className="flex flex-col min-h-[520px]">
        {!active ? (
          <div className="flex-1 grid place-items-center text-sm text-text-muted">Pick a conversation.</div>
        ) : (
          <>
            <header className="px-6 py-4 border-b flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <img src={active.productCover} alt="" className="w-10 h-10 rounded-lg object-cover" />
                <div className="min-w-0">
                  <div className="font-serif text-base truncate">{active.productName}</div>
                  <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                    {role === 'admin' && <>{active.buyerName} ↔ {active.sellerName}</>}
                    {role === 'buyer' && <>with {active.sellerName}</>}
                    {role === 'seller' && <>from {active.buyerName}</>}
                  </div>
                </div>
              </div>
              {active.isAgent && (
                <span className="font-mono text-[10px] uppercase tracking-wider text-accent hairline border-accent/40 rounded-full px-2 py-1 inline-flex items-center gap-1">
                  <Bot size={11} />AI rep · budget ${active.agentBudget}
                </span>
              )}
            </header>

            <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-3 max-h-[460px]">
              {msgs.map((m) => {
                const mine = role !== 'admin' && m.authorId === viewer.id;
                return (
                  <div key={m.id} className={mine ? 'flex justify-end' : 'flex'}>
                    <div className="max-w-[78%]">
                      <div className={`text-[10px] uppercase tracking-wider font-mono mb-1 ${m.isAgent ? 'text-accent' : 'text-text-muted'} ${mine ? 'text-right' : ''}`}>
                        {m.isAgent && <Bot size={10} className="inline mr-1" />}
                        {m.authorName} · {timeAgo(m.ts)}
                      </div>
                      <div className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                        mine ? 'bg-text text-bg rounded-tr-sm' : m.isAgent ? 'bg-accent/10 hairline border-accent/30 rounded-tl-sm' : 'bg-surface-2 rounded-tl-sm'
                      }`}>
                        {m.body}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {role !== 'admin' ? (
              <form onSubmit={(e) => { e.preventDefault(); send(); }} className="border-t p-3">
                <div className="hairline rounded-xl bg-surface flex items-end gap-2 p-1.5 focus-within:border-accent transition-colors">
                  <textarea
                    rows={1}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                    placeholder={active.isAgent && role === 'buyer' ? 'Your AI rep is handling this — chime in if you want to adjust.' : 'Write a message…'}
                    className="flex-1 bg-transparent outline-none resize-none text-sm py-2 px-2 max-h-28"
                  />
                  <button className="w-9 h-9 grid place-items-center rounded-lg bg-text text-bg disabled:opacity-30" disabled={!input.trim()} aria-label="Send">
                    <Send size={13} />
                  </button>
                </div>
              </form>
            ) : (
              <div className="border-t p-3 flex items-center gap-2 text-xs text-text-muted">
                <Eye size={13} /> Curator view · read-only
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function timeAgo(ts: number) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
