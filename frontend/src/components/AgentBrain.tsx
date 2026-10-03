import { motion, useReducedMotion } from "framer-motion";
import {
  AlertTriangle,
  BrainCircuit,
  Check,
  ChevronRight,
  ClipboardCopy,
  Copy,
  Gavel,
  ListChecks,
  ScanSearch,
  ScrollText,
  Sparkles,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { DECISION, FLAG_LABEL, WRITE_TOOLS, inr, pretty } from "../format";
import type { ChatMessage, ToolCall } from "../types";
import { Chip, DecisionBadge, IconButton, SectionLabel, cx } from "./ui";

function compactParams(p: Record<string, unknown>): string {
  return Object.entries(p)
    .filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0))
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join("  ");
}

function Step({
  icon: Icon,
  title,
  index,
  children,
  tone = "text-orange-300",
  last,
}: {
  icon: typeof Zap;
  title: string;
  index: number;
  children: ReactNode;
  tone?: string;
  last?: boolean;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.li
      initial={{ opacity: 0, x: reduce ? 0 : 8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2, delay: reduce ? 0 : index * 0.05, ease: "easeOut" }}
      className="relative pl-9"
    >
      {!last && <span className="absolute left-[13px] top-7 h-[calc(100%-12px)] w-px bg-line" aria-hidden />}
      <span className={cx("absolute left-0 top-0 grid size-7 place-items-center rounded-lg bg-elevated ring-1 ring-inset ring-white/10", tone)}>
        <Icon className="size-3.5" aria-hidden />
      </span>
      <div className="pb-5">
        <div className="mb-2 flex items-center gap-2 pt-1 text-xs font-semibold text-fg">
          <span className="text-faint">{index + 1}</span> {title}
        </div>
        {children}
      </div>
    </motion.li>
  );
}

function ToolRow({ t }: { t: ToolCall }) {
  const [open, setOpen] = useState(false);
  const write = WRITE_TOOLS.has(t.name);
  return (
    <div className={cx("rounded-xl border bg-surface", write ? "border-amber-500/25" : "border-line")}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-2.5 py-2 text-left"
      >
        <ChevronRight className={cx("size-3.5 shrink-0 text-faint transition-transform", open && "rotate-90")} aria-hidden />
        <span className={cx("font-mono text-xs font-medium", write ? "text-amber-200" : "text-fg")}>{t.name}</span>
        {write && <Chip className="bg-amber-500/10 text-amber-200 ring-amber-500/25">write</Chip>}
        <span className="ml-auto shrink-0">
          {t.ok ? <Check className="size-3.5 text-emerald-400" aria-label="succeeded" /> : <X className="size-3.5 text-rose-400" aria-label="failed" />}
        </span>
      </button>
      {!open && (
        <div className="truncate px-2.5 pb-2 pl-8 font-mono text-2xs text-faint" title={compactParams(t.params)}>
          {compactParams(t.params)}
        </div>
      )}
      {open && (
        <div className="space-y-2 border-t border-line px-2.5 py-2">
          <div>
            <div className="mb-1 text-2xs font-medium text-faint">params</div>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-bg p-2 font-mono text-2xs text-muted">
              {JSON.stringify(t.params, null, 2)}
            </pre>
          </div>
          <div>
            <div className="mb-1 text-2xs font-medium text-faint">result</div>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-bg p-2 font-mono text-2xs text-muted">
              {t.result ? JSON.stringify(t.result, null, 2) : t.result_summary}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export function AgentBrain({ message, onClose }: { message: ChatMessage | null; onClose?: () => void }) {
  const [copied, setCopied] = useState(false);
  const r = message?.response;

  const copy = async () => {
    if (!r) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(r, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: ignore */
    }
  };

  const reads = r?.tool_calls.filter((t) => !WRITE_TOOLS.has(t.name)) ?? [];
  const writes = r?.tool_calls.filter((t) => WRITE_TOOLS.has(t.name)) ?? [];
  // split the audit trail into sentences and keep the policy maths (version, window, cap, threshold, warranty)
  const policyLines = [
    ...new Set(
      (r?.reasoning ?? [])
        .map((l) => l.replace(/^#\d+ \w+ -> \w+: /, ""))
        .flatMap((l) => l.split(/(?<=\.)\s+(?=[A-Z])/))
        .filter((l) => /policy v\d|window|threshold|day \d|restocking|warranty|refundable|GST|capped/i.test(l)),
    ),
  ];
  const d = r ? DECISION[r.decision] : null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line px-4">
        <BrainCircuit className="size-4 text-orange-300" aria-hidden />
        <h2 className="text-sm font-semibold text-fg">Agent Brain</h2>
        <div className="ml-auto flex items-center gap-1">
          {r && (
            <button
              type="button"
              onClick={copy}
              className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-2xs font-medium text-muted ring-1 ring-inset ring-white/10 hover:text-fg"
            >
              {copied ? <ClipboardCopy className="size-3" aria-hidden /> : <Copy className="size-3" aria-hidden />}
              {copied ? "Copied" : "Copy JSON"}
            </button>
          )}
          {onClose && (
            <IconButton label="Close Agent Brain" onClick={onClose}>
              <X className="size-4" />
            </IconButton>
          )}
        </div>
      </div>

      {!r ? (
        <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
          <div className="mb-3 grid size-10 place-items-center rounded-xl bg-elevated ring-1 ring-white/10">
            <BrainCircuit className="size-5 text-faint" aria-hidden />
          </div>
          <p className="text-sm font-medium text-fg">No reply selected</p>
          <p className="mt-1 max-w-[240px] text-xs text-muted">
            Send a message or run a scenario. The full reasoning trace (intents, tools, policy and decision) shows up here.
          </p>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto p-4" key={message?.id}>
          {/* decision summary */}
          <div className={cx("mb-5 rounded-2xl p-3 ring-1 ring-inset", d?.bg, d?.ring)}>
            <div className="flex items-center justify-between gap-2">
              <DecisionBadge decision={r.decision} size="lg" />
              <span className="text-2xs text-muted">{d?.hint}</span>
            </div>
            <div className="mt-3 grid grid-cols-4 gap-2 text-center">
              {[
                ["in", r.tokens.input.toLocaleString("en-IN")],
                ["out", r.tokens.output.toLocaleString("en-IN")],
                ["LLM", String(r.tokens.llm_calls)],
                ["ms", String(r.latency_ms)],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-black/20 py-1.5">
                  <div className="text-sm font-semibold tabular-nums text-fg">{v}</div>
                  <div className="text-[10px] uppercase tracking-wider text-faint">{k === "in" ? "tokens in" : k === "out" ? "tokens out" : k === "LLM" ? "LLM calls" : "latency"}</div>
                </div>
              ))}
            </div>
          </div>

          {r.flags.length > 0 && (
            <div className="mb-5">
              <SectionLabel>Risk flags</SectionLabel>
              <div className="flex flex-wrap gap-1.5">
                {r.flags.map((f) => (
                  <Chip key={f} className="bg-rose-500/10 text-rose-200 ring-rose-500/25">
                    <AlertTriangle className="size-3" aria-hidden /> {FLAG_LABEL[f] ?? f}
                  </Chip>
                ))}
              </div>
            </div>
          )}

          <ol aria-label="Agent loop">
            <Step icon={ScanSearch} title="Understand" index={0}>
              {r.intents.length === 0 ? (
                <p className="text-xs text-muted">No actionable request (e.g. pure prompt injection).</p>
              ) : (
                <ul className="space-y-1.5">
                  {r.intents.map((it, i) => (
                    <li key={i} className="rounded-xl border border-line bg-surface px-2.5 py-2">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-xs font-semibold text-fg">{pretty(it.type)}</span>
                        {it.order_id && <Chip mono>{it.order_id}</Chip>}
                        {it.decision && <DecisionBadge decision={it.decision} size="sm" />}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {it.reason && <Chip>reason: {pretty(it.reason)}</Chip>}
                        {it.amount_claimed != null && <Chip>asked {inr(it.amount_claimed)}</Chip>}
                        {it.product_hint && <Chip>{it.product_hint}</Chip>}
                        {it.escalation_team && <Chip className="bg-rose-500/10 text-rose-200 ring-rose-500/25">→ {it.escalation_team}</Chip>}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Step>

            <Step icon={Wrench} title={`Verify · ${reads.length} read${reads.length === 1 ? "" : "s"}`} index={1} tone="text-sky-300">
              <div className="space-y-1.5">
                {reads.length === 0 ? <p className="text-xs text-muted">No lookups needed.</p> : reads.map((t, i) => <ToolRow key={i} t={t} />)}
              </div>
            </Step>

            <Step icon={ScrollText} title={`Policy${r.policy_version ? ` · ${r.policy_version}` : ""}`} index={2} tone="text-violet-300">
              {policyLines.length === 0 ? (
                <p className="text-xs text-muted">No policy rule was needed for this reply.</p>
              ) : (
                <ul className="space-y-1">
                  {policyLines.slice(0, 4).map((l, i) => (
                    <li key={i} className="rounded-lg bg-white/[0.02] px-2.5 py-1.5 text-2xs leading-relaxed text-muted">
                      {l}
                    </li>
                  ))}
                </ul>
              )}
            </Step>

            <Step icon={Gavel} title="Decide" index={3} tone={d?.text}>
              <div className="flex items-center gap-2">
                <DecisionBadge decision={r.decision} size="sm" />
                <span className="text-xs text-muted">{r.intents.length > 1 ? "highest-priority decision across intents" : d?.hint}</span>
              </div>
              {r.intents
                .filter((it) => it.explanation)
                .slice(0, 3)
                .map((it, i) => (
                  <p key={i} className="mt-1.5 text-2xs leading-relaxed text-muted">
                    <span className="text-fg">{pretty(it.type)}:</span> {it.explanation}
                  </p>
                ))}
            </Step>

            <Step icon={Zap} title="Act" index={4} tone="text-amber-300" last>
              {writes.length === 0 ? (
                <p className="text-xs text-muted">No write action. The agent answered or asked without changing anything.</p>
              ) : (
                <div className="space-y-1.5">
                  {writes.map((t, i) => (
                    <ToolRow key={i} t={t} />
                  ))}
                  {(r.refund_amount != null || r.ticket_id) && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {r.refund_amount != null && <Chip className="bg-amber-500/10 text-amber-200 ring-amber-500/25">refund {inr(r.refund_amount)}</Chip>}
                      {r.ticket_id && <Chip mono className="bg-white/[0.04] text-fg ring-white/10">{r.ticket_id}</Chip>}
                    </div>
                  )}
                </div>
              )}
            </Step>
          </ol>

          <div className="mt-2">
            <SectionLabel right={<span className="text-2xs text-faint">{r.reasoning.length} steps</span>}>
              <span className="inline-flex items-center gap-1">
                <ListChecks className="size-3" aria-hidden /> Full reasoning
              </span>
            </SectionLabel>
            <ol className="space-y-1.5">
              {r.reasoning.map((l, i) => (
                <li key={i} className="flex gap-2 text-2xs leading-relaxed text-muted">
                  <span className="mt-px shrink-0 font-mono text-faint">{String(i + 1).padStart(2, "0")}</span>
                  <span className="break-words">{l}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-1.5 border-t border-line pt-3 text-2xs text-faint">
            <Sparkles className="size-3" aria-hidden />
            parser: {r.parser ?? "—"} · reply: {r.reply_source ?? "—"} · language: {r.language ?? "—"}
          </div>
        </div>
      )}
    </div>
  );
}
