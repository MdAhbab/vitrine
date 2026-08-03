import { useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';

/**
 * The one modal primitive.
 *
 * The app previously hand-rolled four separate overlay shells, none of which
 * announced itself as a dialog, trapped focus, restored focus on close, locked
 * body scroll, or handled Escape consistently — including the checkout dialog.
 * Background content stayed keyboard-reachable behind every one of them.
 *
 * Anything that overlays the page should render through this.
 */

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/** Body-scroll lock, refcounted so stacked dialogs don't unlock each other. */
let lockCount = 0;
let releaseLock: (() => void) | null = null;

function lockBodyScroll(): () => void {
  if (lockCount === 0) {
    const { body } = document;
    const previousOverflow = body.style.overflow;
    const previousPad = body.style.paddingRight;
    // Compensate for the vanishing scrollbar so the page doesn't shift.
    const gap = window.innerWidth - document.documentElement.clientWidth;
    body.style.overflow = 'hidden';
    if (gap > 0) body.style.paddingRight = `${gap}px`;
    releaseLock = () => {
      body.style.overflow = previousOverflow;
      body.style.paddingRight = previousPad;
    };
  }
  lockCount += 1;
  return () => {
    lockCount = Math.max(0, lockCount - 1);
    if (lockCount === 0) {
      releaseLock?.();
      releaseLock = null;
    }
  };
}

export function Dialog({
  open,
  onClose,
  children,
  label,
  max = 'max-w-lg',
  className = '',
  panelClassName = '',
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  /** Accessible name, announced when the dialog opens. */
  label: string;
  max?: string;
  className?: string;
  panelClassName?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const panel = panelRef.current;
      if (!panel) return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      );
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      // Wrap at both ends so Tab can never reach the page behind the dialog.
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const unlock = lockBodyScroll();
    // Focus the first control, falling back to the panel itself.
    const panel = panelRef.current;
    const target = panel?.querySelector<HTMLElement>(FOCUSABLE) ?? panel;
    target?.focus({ preventScroll: true });
    return () => {
      unlock();
      // Send focus back where it came from, so keyboard users don't land at
      // the top of the document after closing.
      returnFocusRef.current?.focus?.({ preventScroll: true });
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
          onKeyDown={onKeyDown}
          className={`fixed inset-0 z-50 bg-black/55 backdrop-blur-sm grid place-items-center p-4 ${className}`}
        >
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={label}
            tabIndex={-1}
            initial={{ scale: 0.96, y: 12, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ type: 'spring', stiffness: 240, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className={
              panelClassName ||
              `bg-surface hairline rounded-2xl w-full ${max} shadow-2xl overflow-hidden max-h-[90vh] flex flex-col outline-none`
            }
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
