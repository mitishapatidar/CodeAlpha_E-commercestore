import { motion } from "framer-motion";
import { AlertTriangle, ArrowUpRight, Inbox, ReceiptIndianRupee, RefreshCw, ShieldAlert, Ticket, Timer, Undo2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/api";
import { AgentBrain } from "@/components/AgentBrain";
import { Chip, DecisionBadge, SectionLabel, Skeleton } from "@/components/ui/primitives";
import { DECISION, FLAG_LABEL, inr, pretty, timeOf } from "@/format";
import { cn } from "@/lib/utils";
import type { ActionRecord, ChatMessage, Decision, TurnRecord } from "@/types";

const ACTION_META: Record<string, { icon: typeof Ticket; tone: string; label: string }> = {
  escalation: { icon: ShieldAlert, tone: "text-rose-300 bg-rose-500/10 ring-rose-500/25", label: "Escalation" },
  refund: { icon: ReceiptIndianRupee, tone: "text-amber-300 bg-amber-500/10 ring-amber-500/25", label: "Refund" },
  return: { icon: Undo2, tone: "text-sky-300 bg-sky-500/10 ring-sky-500/25", label: "Return" },
  ticket: { icon: Ticket, tone: "text-slate-300 bg-slate-500/10 ring-slate-500/25", label: "Ticket" },
};

function Kpi({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
      <div className="text-2xs font-medium uppercase tracking-[0.08em] text-faint">{label}</div>
      <div className={cn("mt-1.5 text-2xl font-semibold tabular-nums text-fg", accent)}>{value}</div>
      {hint && <div className="mt-0.5 text-2xs text-muted">{hint}</div>}
    </div>
  );
}

export function OwnerReview({ onError }: { onError: (msg: string, retry?: () => void) => void }) {
  const [turns, setTurns] = useState<TurnRecord[] | null>(null);
  const [actions, setActions] = useState<ActionRecord[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState<Decision | "ALL">("ALL");
  const [actionFilter, setActionFilter] = useState<string>("all");

  const load = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([api.turns(150), api.actions(200)]);
      setTurns(t);
      setActions(a);
    } catch (e) {
      onError(`Could not load review data: ${(e as Error).message}`);
    }
  }, [onError]);

  useEffect(() => {
    load();
    const h = setInterval(() => document.visibilityState === "visible" && load(), 4000);
    return () => clearInterval(h);
  }, [load]);

  const stats = useMemo(() => {
    const t = turns ?? [];
    const by: Record<Decision, number> = { ANSWER: 0, ASK: 0, ACT: 0, ESCALATE: 0 };
    t.forEach((x) => (by[x.response.decision] += 1));
    const a = actions ?? [];
    const refunds = a.filter((x) => x.type === "refund");
    return {
      total: t.length,
      by,
      refundCount: refunds.length,
      refundSum: refunds.reduce((s, r) => s + (Number(r.amount) || 0), 0),
      escalations: a.filter((x) => x.type === "escalation").length,
      flagged: t.filter((x) => x.response.flags.length > 0).length,
      avgLatency: t.length ? Math.round(t.reduce((s, x) => s + x.response.latency_ms, 0) / t.length) : 0,
    };
  }, [turns, actions]);

  const visibleTurns = (turns ?? []).filter((t) => filter === "ALL" || t.response.decision === filter);
  const visibleActions = (actions ?? []).filter((a) => actionFilter === "all" || a.type === actionFilter);
  const sel = (turns ?? []).find((t) => t.id === selected) ?? visibleTurns[0] ?? null;
  const selMessage: ChatMessage | null = sel
    ? { id: sel.id, role: "agent", text: sel.response.reply, at: Date.parse(sel.at) || Date.now(), response: sel.response }
    : null;

  return (
    <div className="flex min-h-0 flex-1">
      <div className="min-w-0 flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-fg">Agent review</h1>
              <p className="text-sm text-muted">Every decision the AI support agent made, with the actions it took. Updates live.</p>
            </div>
            <button
              type="button"
              onClick={load}
              className="inline-flex items-center gap-1.5 rounded-xl bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-fg ring-1 ring-inset ring-white/10 hover:bg-white/[0.08]"
            >
              <RefreshCw className="size-3.5" aria-hidden /> Refresh
            </button>
          </div>

          {/* KPIs */}
          {turns === null ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}</div>
          ) : (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Kpi label="Conversations" value={String(stats.total)} hint={`${stats.flagged} with risk flags`} />
              <Kpi label="Refunds issued" value={inr(stats.refundSum)} hint={`${stats.refundCount} refund${stats.refundCount === 1 ? "" : "s"} within policy`} accent="text-amber-200" />
              <Kpi label="Escalations" value={String(stats.escalations)} hint="handed to human teams" accent="text-rose-200" />
              <Kpi label="Avg latency" value={`${stats.avgLatency} ms`} hint="per agent turn" />
            </div>
          )}

          {/* decision mix */}
          <div className="mt-3 rounded-2xl border border-line bg-surface p-4">
            <SectionLabel right={<span className="text-2xs text-faint">click to filter</span>}>Decision mix</SectionLabel>
            <div className="flex h-2.5 overflow-hidden rounded-full bg-white/[0.04]" aria-hidden>
              {(Object.keys(stats.by) as Decision[]).map((d) =>
                stats.total ? <div key={d} className={DECISION[d].dot} style={{ width: `${(stats.by[d] / stats.total) * 100}%` }} /> : null,
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(["ALL", "ANSWER", "ASK", "ACT", "ESCALATE"] as const).map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setFilter(d)}
                  aria-pressed={filter === d}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset transition",
                    filter === d ? "bg-white/[0.08] text-fg ring-white/20" : "text-muted ring-white/10 hover:text-fg",
                  )}
                >
                  {d !== "ALL" && <span className={cn("size-2 rounded-full", DECISION[d].dot)} aria-hidden />}
                  {d === "ALL" ? "All" : d} <span className="tabular-nums text-faint">{d === "ALL" ? stats.total : stats.by[d]}</span>
                </button>
              ))}
            </div>
          </div>

          {/* decisions table */}
          <section className="mt-5" aria-label="Agent decisions">
            <SectionLabel>Agent decisions</SectionLabel>
            {turns === null ? (
              <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}</div>
            ) : visibleTurns.length === 0 ? (
              <div className="flex flex-col items-center rounded-2xl border border-dashed border-line p-8 text-center">
                <Inbox className="size-6 text-faint" aria-hidden />
                <p className="mt-2 text-sm text-fg">No conversations yet</p>
                <p className="text-xs text-muted">Chat as a customer, or run demo scenarios in the Live console tab.</p>
              </div>
            ) : (
              <ul className="space-y-1.5">
                {visibleTurns.map((t) => {
                  const r = t.response;
                  const active = sel?.id === t.id;
                  return (
                    <li key={t.id}>
                      <motion.button
                        layout
                        type="button"
                        onClick={() => setSelected(t.id)}
                        aria-pressed={active}
                        className={cn(
                          "flex w-full items-start gap-3 rounded-xl border bg-surface px-3 py-2.5 text-left transition",
                          active ? "border-orange-500/40 shadow-glow" : "border-line hover:border-line-strong",
                        )}
                      >
                        <DecisionBadge decision={r.decision} size="sm" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm text-fg" title={t.message}>{t.message}</p>
                          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-2xs text-faint">
                            <span className="font-mono">{t.customer_id ?? "anonymous"}</span>
                            <span>·</span>
                            <span>{timeOf(Date.parse(t.at))}</span>
                            {r.intents.slice(0, 2).map((it, i) => (
                              <Chip key={i}>{pretty(it.type)}{it.order_id ? ` · ${it.order_id}` : ""}</Chip>
                            ))}
                            {r.flags.map((f) => (
                              <Chip key={f} className="bg-rose-500/10 text-rose-200 ring-rose-500/25">
                                <AlertTriangle className="size-3" aria-hidden /> {FLAG_LABEL[f] ?? f}
                              </Chip>
                            ))}
                          </div>
                        </div>
                        <div className="shrink-0 text-right">
                          {r.refund_amount != null && <div className="text-xs font-semibold text-amber-200">{inr(r.refund_amount)}</div>}
                          {r.ticket_id && <div className="font-mono text-2xs text-faint">{r.ticket_id}</div>}
                        </div>
                      </motion.button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {/* action queue */}
          <section className="mt-6" aria-label="Action queue">
            <SectionLabel
              right={
                <div className="flex gap-1">
                  {["all", "escalation", "refund", "return", "ticket"].map((k) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setActionFilter(k)}
                      aria-pressed={actionFilter === k}
                      className={cn("rounded-md px-2 py-0.5 text-2xs font-medium", actionFilter === k ? "bg-white/[0.08] text-fg" : "text-faint hover:text-fg")}
                    >
                      {k === "all" ? "All" : ACTION_META[k].label}
                    </button>
                  ))}
                </div>
              }
            >
              Action queue
            </SectionLabel>
            {actions === null ? (
              <Skeleton className="h-24 rounded-2xl" />
            ) : visibleActions.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-line p-6 text-center text-xs text-muted">No refunds, returns, tickets or escalations yet.</p>
            ) : (
              <div className="overflow-hidden rounded-2xl border border-line">
                <table className="w-full text-left text-xs">
                  <thead className="bg-white/[0.03] text-2xs uppercase tracking-wider text-faint">
                    <tr>
                      <th className="px-3 py-2 font-medium">Type</th>
                      <th className="px-3 py-2 font-medium">Reference</th>
                      <th className="hidden px-3 py-2 font-medium sm:table-cell">Customer / order</th>
                      <th className="px-3 py-2 font-medium">Details</th>
                      <th className="px-3 py-2 text-right font-medium">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {visibleActions.map((a) => {
                      const m = ACTION_META[a.type] ?? ACTION_META.ticket;
                      const Icon = m.icon;
                      return (
                        <tr key={a.id} className="bg-surface">
                          <td className="px-3 py-2">
                            <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-2xs font-medium ring-1 ring-inset", m.tone)}>
                              <Icon className="size-3" aria-hidden /> {m.label}
                            </span>
                          </td>
                          <td className="px-3 py-2 font-mono text-fg">{a.id}</td>
                          <td className="hidden px-3 py-2 text-muted sm:table-cell">
                            <div className="font-mono">{a.customer_id}</div>
                            {a.order_id && <div className="font-mono text-faint">{a.order_id}</div>}
                          </td>
                          <td className="max-w-[320px] px-3 py-2 text-muted">
                            {a.type === "refund" && <span className="font-semibold text-amber-200">{inr(Number(a.amount))}</span>}{" "}
                            {a.type === "escalation" ? (
                              <span>
                                <span className="text-fg">{a.team}</span> · {a.priority} · <span className="text-faint">{String(a.reason ?? "").slice(0, 120)}</span>
                              </span>
                            ) : (
                              <span className="line-clamp-2">{String(a.summary ?? a.reason ?? a.resolution ?? "")}</span>
                            )}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right text-faint">
                            <Timer className="mr-1 inline size-3" aria-hidden />
                            {timeOf(Date.parse(a.created_at))}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </div>

      <aside className="hidden w-[400px] shrink-0 border-l border-line bg-bg lg:flex lg:flex-col" aria-label="Decision trace">
        {selMessage ? (
          <>
            <div className="flex items-center gap-2 border-b border-line px-4 py-2 text-2xs text-faint">
              <ArrowUpRight className="size-3" aria-hidden /> Trace for: <span className="truncate text-muted">{sel?.message}</span>
            </div>
            <div className="min-h-0 flex-1">
              <AgentBrain message={selMessage} />
            </div>
          </>
        ) : (
          <AgentBrain message={null} />
        )}
      </aside>
    </div>
  );
}
