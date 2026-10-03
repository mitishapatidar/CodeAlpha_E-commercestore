import { BrainCircuit, Gauge, LayoutDashboard, MessageSquare, MessagesSquare, PanelLeft, RefreshCw, Sparkles } from "lucide-react";
import type { Health } from "../types";
import { Chip, IconButton, cx } from "./ui";

export interface SessionStats {
  messages: number;
  tokens: number;
  llmCalls: number;
  avgLatency: number;
}

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="brand-gradient grid size-8 place-items-center rounded-xl shadow-[0_6px_18px_-6px_rgba(249,115,22,0.7)]">
        <svg viewBox="0 0 32 32" className="size-5" aria-hidden>
          <path d="M9 22V10l14 12V10" fill="none" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="leading-tight">
        <div className="whitespace-nowrap text-sm font-semibold tracking-tight text-fg">
          NovaMart <span className="text-faint">·</span> <span className="brand-text">Agent Console</span>
        </div>
        <div className="hidden whitespace-nowrap text-2xs text-faint xl:block">Understand → Verify → Decide → Act</div>
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: typeof Gauge; label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5 rounded-lg bg-white/[0.03] px-2 py-1 ring-1 ring-inset ring-white/[0.06]" title={label}>
      <Icon className="size-3.5 text-faint" aria-hidden />
      <span className="text-xs font-semibold tabular-nums text-fg">{value}</span>
      <span className="hidden text-2xs text-faint 2xl:inline">{label}</span>
    </div>
  );
}

export function TopBar({
  health,
  online,
  retry,
  stats,
  view,
  setView,
  openSidebar,
  openBrain,
}: {
  health: Health | null;
  online: boolean | null;
  retry: () => void;
  stats: SessionStats;
  view: "console" | "customer";
  setView: (v: "console" | "customer") => void;
  openSidebar: () => void;
  openBrain: () => void;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-bg/80 px-3 backdrop-blur sm:px-4">
      {view === "console" && (
        <IconButton label="Open customers and scenarios" className="sm:hidden" onClick={openSidebar}>
          <PanelLeft className="size-4" />
        </IconButton>
      )}
      <Logo />

      <div className="ml-2 hidden items-center gap-2 md:flex">
        <span className="flex items-center gap-1.5 rounded-full px-2 py-1 text-2xs font-medium ring-1 ring-inset ring-white/10">
          <span
            className={cx(
              "size-2 rounded-full",
              online === null ? "bg-slate-500" : online ? "animate-pulse-dot bg-emerald-400" : "bg-rose-500",
            )}
            aria-hidden
          />
          <span className={online === false ? "text-rose-300" : "text-muted"}>
            {online === null ? "Connecting" : online ? "Live" : "Offline"}
          </span>
        </span>
        {online === false && (
          <button type="button" onClick={retry} className="inline-flex items-center gap-1 text-2xs font-semibold text-orange-300 hover:text-orange-200">
            <RefreshCw className="size-3" /> Retry
          </button>
        )}
        {health && (
          <>
            <Chip className="bg-white/[0.03] text-muted ring-white/10" title={health.model}>
              <Sparkles className="size-3 text-orange-300" aria-hidden />
              <span className="max-w-[180px] truncate whitespace-nowrap">{health.llm_enabled === false ? "Rules engine · LLM off" : health.model}</span>
            </Chip>
            <div className="hidden items-center gap-1 lg:flex">
              {health.policy_versions.map((v) => (
                <Chip key={v} mono className="bg-white/[0.03] text-muted ring-white/10" title="Policy version loaded from data">
                  policy {v}
                </Chip>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="ml-auto flex items-center gap-2">
        {view === "console" && (
          <div className="hidden items-center gap-1.5 xl:flex">
            <Stat icon={MessagesSquare} label="messages" value={String(stats.messages)} />
            <Stat icon={Sparkles} label="tokens" value={stats.tokens.toLocaleString("en-IN")} />
            <Stat icon={BrainCircuit} label="LLM calls" value={String(stats.llmCalls)} />
            <Stat icon={Gauge} label="avg latency" value={`${stats.avgLatency} ms`} />
          </div>
        )}
        <div className="flex rounded-xl bg-white/[0.04] p-0.5 ring-1 ring-inset ring-white/10" role="tablist" aria-label="View">
          {(
            [
              ["console", LayoutDashboard, "Console"],
              ["customer", MessageSquare, "Customer"],
            ] as const
          ).map(([key, Icon, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={view === key}
              onClick={() => setView(key)}
              className={cx(
                "inline-flex items-center gap-1.5 whitespace-nowrap rounded-[10px] px-2.5 py-1 text-xs font-medium transition",
                view === key ? "bg-elevated text-fg shadow-card ring-1 ring-inset ring-white/10" : "text-muted hover:text-fg",
              )}
            >
              <Icon className="size-3.5" aria-hidden />
              <span className="hidden lg:inline">{label} view</span>
            </button>
          ))}
        </div>
        {view === "console" && (
          <IconButton label="Open Agent Brain" className="lg:hidden" onClick={openBrain}>
            <BrainCircuit className="size-4" />
          </IconButton>
        )}
      </div>
    </header>
  );
}
