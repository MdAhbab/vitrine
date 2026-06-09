import { useEffect, useRef, useState } from 'react';
import { Bot, Send, Eye, Sparkles, Paperclip, FileText } from 'lucide-react';
import { useStore, type MessageAttachment, type Role } from '../lib/store';
import { api, mediaUrl, USE_MOCKS } from '../lib/api';

const CHAT_MAX_BYTES = 4 * 1024 * 1024;

export function Inbox({ role, viewer }: { role: Role; viewer: { id: string; name: string } }) {
  const { threads, messages, sendMessage, agentReply, deactivateRep } = useStore();
  const visible = threads.filter((t) => {
    if (role === 'admin') return true;
    if (role === 'buyer') return t.buyerId === viewer.id;
    return t.sellerId === viewer.id;
  });
  const [activeId, setActiveId] = useState<string | undefined>(visible[0]?.id);
  const loadMessages = useStore((s: any) => s.loadMessages);
  
  useEffect(() => {
    if (!visible.find((t) => t.id === activeId)) {
      setActiveId(visible[0]?.id);
    }
  }, [visible.map((t) => t.id).join()]);

  useEffect(() => {
    if (activeId && loadMessages) {
      loadMessages(activeId).catch(() => {});
      const t = setInterval(() => {
        loadMessages(activeId).catch(() => {});
      }, 3000);
      return () => clearInterval(t);
    }
  }, [activeId]);

  const active = visible.find((t) => t.id === activeId);
  const msgs = messages.filter((m) => m.threadId === activeId);
  const [input, setInput] = useState('');
  const [pendingAtt, setPendingAtt] = useState<MessageAttachment | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }); }, [msgs.length]);

  const attachFile = async (file: File | null) => {
    if (!file || USE_MOCKS) return;
    if (file.size > CHAT_MAX_BYTES) {
      alert('Attachments must be 4 MB or smaller (images or PDF only).');
      return;
    }
    const ok = file.type.startsWith('image/') || file.type === 'application/pdf';
    if (!ok) {
      alert('Only images and PDF files are allowed in chat.');
      return;
    }
    setUploading(true);
    try {
      const res = await api.uploadChatAttachment(file);
      setPendingAtt({ url: res.url, name: res.name, mime: res.mime, kind: res.kind, size: res.size });
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const send = async () => {
    if ((!input.trim() && !pendingAtt) || !active || role === 'admin') return;
    const attachments = pendingAtt ? [pendingAtt] : [];
    if (USE_MOCKS) {
      sendMessage(active.id, input, { id: viewer.id, name: viewer.name }, attachments);
      setInput('');
      setPendingAtt(null);
      if (active.isAgent && role === 'seller') {
        setTimeout(() => agentReply(active.id), 600);
      }
      return;
    }

    try {
      await sendMessage(active.id, input, { id: viewer.id, name: viewer.name }, attachments);
      setInput('');
      setPendingAtt(null);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Failed to send message');
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
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-accent hairline border-accent/40 rounded-full px-2 py-1 inline-flex items-center gap-1">
                    <Bot size={11} />AI rep · budget ${active.agentBudget}
                  </span>
                  {role === 'buyer' && (
                    <button
                      onClick={async () => {
                        if (confirm(`Are you sure you want to deactivate the AI representative for this negotiation?`)) {
                          await deactivateRep(active.id);
                        }
                      }}
                      className="hairline rounded-lg px-2.5 py-1 text-xs text-text-soft hover:border-danger hover:text-danger hover:bg-danger/5 transition-colors cursor-pointer"
                    >
                      Deactivate rep
                    </button>
                  )}
                </div>
              )}
            </header>

            <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-3 max-h-[460px]">
              {msgs.map((m) => {
                const mine = role !== 'admin' && m.authorId === viewer.id;
                const featureMatch = m.body.match(/<!-- feature_request_id: ([a-f0-9]+) -->/);
                const featureRequestId = featureMatch ? featureMatch[1] : null;
                const cleanBody = m.body.replace(/<!--.*?-->/gs, '').trim();

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
                        {cleanBody && <div className="whitespace-pre-line">{cleanBody}</div>}
                        {(m.attachments ?? []).map((a) => (
                          a.kind === 'pdf' ? (
                            <a
                              key={a.url}
                              href={mediaUrl(a.url)}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-2 flex items-center gap-2 text-xs underline opacity-90"
                            >
                              <FileText size={14} /> {a.name}
                            </a>
                          ) : (
                            <a key={a.url} href={mediaUrl(a.url)} target="_blank" rel="noreferrer" className="block mt-2">
                              <img src={mediaUrl(a.url)} alt={a.name} className="max-w-full max-h-48 rounded-lg" />
                            </a>
                          )
                        ))}
                        {featureRequestId && (
                          <FeatureRequestBubble
                            id={featureRequestId}
                            role={role}
                            onUpdate={() => loadMessages(activeId!).catch(() => {})}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {role !== 'admin' ? (
              <form onSubmit={(e) => { e.preventDefault(); send(); }} className="border-t p-3">
                {pendingAtt && (
                  <div className="mb-2 flex items-center gap-2 text-xs hairline rounded-lg px-3 py-2 bg-surface-2/50">
                    {pendingAtt.kind === 'pdf' ? <FileText size={14} /> : <img src={mediaUrl(pendingAtt.url)} alt="" className="w-8 h-8 rounded object-cover" />}
                    <span className="truncate flex-1">{pendingAtt.name}</span>
                    <button type="button" onClick={() => setPendingAtt(null)} className="text-text-muted hover:text-danger text-[10px] uppercase">Remove</button>
                  </div>
                )}
                <div className="hairline rounded-xl bg-surface flex items-end gap-2 p-1.5 focus-within:border-accent transition-colors">
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/*,application/pdf"
                    className="hidden"
                    onChange={(e) => attachFile(e.target.files?.[0] ?? null)}
                  />
                  <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    disabled={uploading}
                    className="w-9 h-9 shrink-0 grid place-items-center rounded-lg hover:bg-surface-2 disabled:opacity-40"
                    aria-label="Attach file"
                  >
                    <Paperclip size={14} />
                  </button>
                  <textarea
                    rows={1}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                    placeholder={active.isAgent && role === 'buyer' ? 'Your AI rep is handling this — chime in if you want to adjust.' : 'Write a message…'}
                    className="flex-1 bg-transparent outline-none resize-none text-sm py-2 px-2 max-h-28"
                  />
                  <button className="w-9 h-9 grid place-items-center rounded-lg bg-text text-bg disabled:opacity-30" disabled={!input.trim() && !pendingAtt} aria-label="Send">
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

function FeatureRequestBubble({ id, role, onUpdate }: { id: string; role: Role; onUpdate: () => void }) {
  const [loading, setLoading] = useState(true);
  const [req, setReq] = useState<any>(null);
  const [quoteVal, setQuoteVal] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    api.getFeatureRequest(id)
      .then((data) => {
        if (active) setReq(data);
      })
      .catch(console.error)
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [id]);

  if (loading) {
    return <div className="text-[11px] text-text-muted animate-pulse mt-2">Loading feature request details...</div>;
  }
  if (!req) {
    return <div className="text-[11px] text-danger mt-2">Failed to load feature request details.</div>;
  }

  const handleQuoteSubmit = async () => {
    if (!quoteVal || isNaN(+quoteVal) || +quoteVal <= 0) {
      alert("Please enter a valid price");
      return;
    }
    setSubmitting(true);
    try {
      await api.quoteFeatureRequest(id, { developer_charge: +quoteVal });
      const updated = await api.getFeatureRequest(id);
      setReq(updated);
      onUpdate();
    } catch (e: any) {
      alert(e.message || "Failed to submit quote");
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async () => {
    setSubmitting(true);
    try {
      await api.approveFeatureRequest(id);
      const updated = await api.getFeatureRequest(id);
      setReq(updated);
      onUpdate();
    } catch (e: any) {
      alert(e.message || "Failed to approve quote");
    } finally {
      setSubmitting(false);
    }
  };

  const aiEst = req.estimated_charge_cents ? `$${(req.estimated_charge_cents / 100).toLocaleString()}` : 'N/A';
  const devQuote = req.developer_charge_cents ? `$${(req.developer_charge_cents / 100).toLocaleString()}` : 'N/A';

  return (
    <div className="mt-3 p-3.5 rounded-xl bg-surface/80 border border-border-c/30 space-y-3 text-text">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-wider text-accent font-semibold flex items-center gap-1">
          <Sparkles size={10} /> Custom Feature Scope
        </span>
        <span className="font-mono text-[8px] uppercase tracking-wider px-2 py-0.5 rounded bg-surface-2/60 border border-border-c/30 text-text-soft">
          {req.status.replace(/_/g, ' ')}
        </span>
      </div>

      <div className="text-xs border-t border-border-c/40 pt-2.5 space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-text-muted block text-[9px] uppercase font-mono">AI Estimate</span>
            <span className="font-mono font-medium">{aiEst}</span>
          </div>
          <div>
            <span className="text-text-muted block text-[9px] uppercase font-mono">Developer Quote</span>
            <span className="font-mono font-medium">{devQuote}</span>
          </div>
        </div>
      </div>

      {req.status === 'pending_dev_approval' && role === 'seller' && (
        <div className="border-t border-border-c/40 pt-2.5 flex items-center gap-2">
          <input
            type="number"
            placeholder="Quote ($)"
            value={quoteVal}
            onChange={(e) => setQuoteVal(e.target.value)}
            className="border border-border-c/50 rounded-lg px-2 h-8 text-xs bg-bg outline-none w-24 focus:border-accent text-text font-mono"
          />
          <button
            onClick={handleQuoteSubmit}
            disabled={submitting}
            className="bg-accent text-[var(--accent-ink)] rounded-lg px-3 h-8 text-xs font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
          >
            Quote feature
          </button>
        </div>
      )}

      {req.status === 'pending_buyer_approval' && role === 'buyer' && (
        <div className="border-t border-border-c/40 pt-2.5">
          <button
            onClick={handleApprove}
            disabled={submitting}
            className="w-full bg-accent text-[var(--accent-ink)] rounded-lg h-9 text-xs font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
          >
            Approve & Add to Invoice
          </button>
        </div>
      )}
    </div>
  );
}
