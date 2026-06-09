import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Monitor, Smartphone, RotateCcw, ExternalLink, X } from 'lucide-react';

type Mode = 'browser' | 'phone';

export function PreviewFrame({
  url,
  open,
  onClose,
  productName,
}: {
  url: string;
  open: boolean;
  onClose: () => void;
  productName: string;
}) {
  const [mode, setMode] = useState<Mode>('browser');
  const [reloadKey, setReloadKey] = useState(0);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm grid place-items-center p-4 sm:p-8"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.96, opacity: 0, y: 12 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.97, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 220, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-surface rounded-2xl hairline overflow-hidden w-full max-w-[1100px] flex flex-col shadow-2xl"
            style={{ maxHeight: '90vh' }}
          >
            <div className="flex items-center justify-between gap-4 px-4 h-12 border-b bg-bg/40">
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-text-muted/30" />
                  <span className="w-2.5 h-2.5 rounded-full bg-text-muted/30" />
                  <span className="w-2.5 h-2.5 rounded-full bg-text-muted/30" />
                </div>
                <div className="hidden sm:flex items-center gap-2 font-mono text-[11px] text-text-muted bg-surface-2 px-3 py-1 rounded-full truncate max-w-xs">
                  <span className="live-dot" style={{ width: 6, height: 6 }} />
                  {url.replace(/^https?:\/\//, '')}
                </div>
                <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted hidden md:inline">
                  {productName}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <div className="hairline rounded-full p-0.5 flex">
                  <button
                    onClick={() => setMode('browser')}
                    className={`px-2 h-7 rounded-full grid place-items-center transition-colors ${mode === 'browser' ? 'bg-text text-bg' : 'text-text-muted'}`}
                    aria-label="Browser"
                  >
                    <Monitor size={13} />
                  </button>
                  <button
                    onClick={() => setMode('phone')}
                    className={`px-2 h-7 rounded-full grid place-items-center transition-colors ${mode === 'phone' ? 'bg-text text-bg' : 'text-text-muted'}`}
                    aria-label="Phone"
                  >
                    <Smartphone size={13} />
                  </button>
                </div>
                <button onClick={() => setReloadKey((k) => k + 1)} className="w-8 h-8 grid place-items-center text-text-muted hover:text-text" aria-label="Reload">
                  <RotateCcw size={13} />
                </button>
                <a href={url} target="_blank" rel="noreferrer" className="w-8 h-8 grid place-items-center text-text-muted hover:text-text" aria-label="Open">
                  <ExternalLink size={13} />
                </a>
                <button onClick={onClose} className="w-8 h-8 grid place-items-center text-text-muted hover:text-text" aria-label="Close">
                  <X size={14} />
                </button>
              </div>
            </div>
            <div className="bg-surface-2 flex-1 grid place-items-center p-4 sm:p-8 overflow-auto">
              <motion.div
                key={mode}
                initial={{ scale: 0.97, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 240, damping: 26 }}
                className={`bg-surface hairline overflow-hidden ${
                  mode === 'browser' ? 'w-full max-w-[980px] aspect-[16/10] rounded-lg' : 'w-[320px] aspect-[9/19] rounded-[40px] p-2 border-2'
                }`}
              >
                <iframe
                  key={reloadKey}
                  src={url}
                  title={`${productName} preview`}
                  className={`w-full h-full ${mode === 'phone' ? 'rounded-[32px]' : ''}`}
                  sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                  loading="lazy"
                />
              </motion.div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
