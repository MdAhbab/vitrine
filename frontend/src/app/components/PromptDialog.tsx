import { useEffect, useState } from 'react';
import { Dialog } from './Dialog';

export type PromptRequest = {
  title: string;
  description?: string;
  /** Omit for a plain confirmation. */
  input?: { label: string; type?: 'text' | 'password'; placeholder?: string; initial?: string };
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: (value: string) => void | Promise<void>;
};

/**
 * In-app replacement for window.confirm / window.prompt.
 *
 * The admin console — bans, deletions, escrow release/refund, password resets —
 * was the one surface still using native OS dialogs, which break the app's
 * visual language and, in the password-reset case, meant typing a plaintext
 * password into an unstyled, unmasked browser prompt.
 */
export function PromptDialog({ request, onClose }: { request: PromptRequest | null; onClose: () => void }) {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setValue(request?.input?.initial ?? '');
    setBusy(false);
  }, [request]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!request || busy) return;
    if (request.input && !value.trim()) return;
    setBusy(true);
    try {
      await request.onConfirm(value.trim());
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={!!request} onClose={onClose} max="max-w-md" label={request?.title ?? 'Confirm'}>
      {request && (
        <form onSubmit={submit} className="p-6 space-y-4">
          <div>
            <h2 className="font-serif text-lg">{request.title}</h2>
            {request.description && (
              <p className="text-sm text-text-muted mt-1.5">{request.description}</p>
            )}
          </div>

          {request.input && (
            <label className="block space-y-1.5">
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                {request.input.label}
              </span>
              <input
                autoFocus
                type={request.input.type ?? 'text'}
                value={value}
                placeholder={request.input.placeholder}
                onChange={(e) => setValue(e.target.value)}
                className="w-full h-11 px-3 rounded-lg hairline bg-transparent text-sm"
              />
            </label>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="h-11 px-4 rounded-lg hairline text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || (!!request.input && !value.trim())}
              className={`h-11 px-4 rounded-lg text-sm disabled:opacity-50 ${
                request.danger
                  ? 'bg-danger text-white'
                  : 'gold-gradient text-[var(--accent-ink)]'
              }`}
            >
              {busy ? 'Working…' : request.confirmLabel ?? 'Confirm'}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
