import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, X } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import { DECISION } from "../format";
import type { Decision } from "../types";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

export function Chip({ children, className, title, mono }: { children: ReactNode; className?: string; title?: string; mono?: boolean }) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex max-w-full items-center gap-1 truncate rounded-full px-2 py-0.5 text-2xs font-medium ring-1 ring-inset",
        mono && "font-mono",
        className ?? "bg-white/[0.04] text-muted ring-white/10",
      )}
    >
      {children}
    </span>
  );
}

export function DecisionBadge({ decision, size = "md" }: { decision: Decision; size?: "sm" | "md" | "lg" }) {
  const d = DECISION[decision];
  const Icon = d.icon;
  const sz = size === "lg" ? "px-3 py-1.5 text-sm gap-2" : size === "md" ? "px-2.5 py-1 text-xs gap-1.5" : "px-2 py-0.5 text-2xs gap-1";
  return (
    <span
      title={d.hint}
      className={cx("inline-flex items-center rounded-full font-semibold tracking-wide ring-1 ring-inset", d.text, d.bg, d.ring, sz)}
    >
      <Icon className={size === "lg" ? "size-4" : "size-3.5"} aria-hidden />
      {decision}
    </span>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("rounded-2xl border border-line bg-surface shadow-card", className)}>{children}</div>;
}

export function SectionLabel({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <h3 className="text-2xs font-semibold uppercase tracking-[0.08em] text-faint">{children}</h3>
      {right}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} aria-hidden />;
}

export function IconButton({ label, children, className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cx(
        "inline-flex size-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-white/5 hover:text-fg disabled:opacity-40",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Button({
  children,
  variant = "ghost",
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" }) {
  const v =
    variant === "primary"
      ? "brand-gradient text-white shadow-[0_6px_20px_-8px_rgba(249,115,22,0.6)] hover:brightness-110"
      : variant === "danger"
        ? "bg-rose-500/10 text-rose-300 ring-1 ring-inset ring-rose-500/30 hover:bg-rose-500/20"
        : "bg-white/[0.04] text-fg ring-1 ring-inset ring-white/10 hover:bg-white/[0.08]";
  return (
    <button
      type="button"
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        v,
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

// ------------------------------------------------------------------ toasts
export interface Toast {
  id: string;
  kind: "error" | "success";
  text: string;
  action?: { label: string; run: () => void };
}

export function Toasts({ items, dismiss }: { items: Toast[]; dismiss: (id: string) => void }) {
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(92vw,360px)] flex-col gap-2" role="status" aria-live="polite">
      <AnimatePresence initial={false}>
        {items.map((t) => (
          <ToastItem key={t.id} t={t} dismiss={dismiss} />
        ))}
      </AnimatePresence>
    </div>
  );
}

function ToastItem({ t, dismiss }: { t: Toast; dismiss: (id: string) => void }) {
  useEffect(() => {
    const h = setTimeout(() => dismiss(t.id), t.kind === "error" ? 7000 : 3500);
    return () => clearTimeout(h);
  }, [t, dismiss]);
  const Icon = t.kind === "error" ? AlertTriangle : CheckCircle2;
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.98 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className="pointer-events-auto flex items-start gap-3 rounded-xl border border-line-strong bg-elevated p-3 shadow-card"
    >
      <Icon className={cx("mt-0.5 size-4 shrink-0", t.kind === "error" ? "text-rose-400" : "text-emerald-400")} aria-hidden />
      <p className="min-w-0 flex-1 text-sm text-fg">{t.text}</p>
      {t.action && (
        <button
          type="button"
          className="text-xs font-semibold text-orange-300 hover:text-orange-200"
          onClick={() => {
            t.action?.run();
            dismiss(t.id);
          }}
        >
          {t.action.label}
        </button>
      )}
      <button type="button" aria-label="Dismiss notification" className="text-faint hover:text-fg" onClick={() => dismiss(t.id)}>
        <X className="size-4" />
      </button>
    </motion.div>
  );
}

// ------------------------------------------------------------------ drawer
export function Drawer({
  open,
  side,
  onClose,
  children,
  label,
}: {
  open: boolean;
  side: "left" | "right";
  onClose: () => void;
  children: ReactNode;
  label: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label={label}>
          <motion.button
            type="button"
            aria-label="Close panel"
            className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className={cx(
              "absolute top-0 flex h-full w-[min(92vw,380px)] flex-col border-line bg-bg shadow-2xl",
              side === "right" ? "right-0 border-l" : "left-0 border-r",
            )}
            initial={{ x: side === "right" ? "100%" : "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: side === "right" ? "100%" : "-100%" }}
            transition={{ duration: 0.22, ease: "easeOut" }}
          >
            {children}
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
}
