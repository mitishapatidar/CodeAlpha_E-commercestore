import { CircleHelp, Headset, Inbox, PackageSearch, ReceiptIndianRupee, RotateCcw, ShieldAlert, Ticket } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/api";
import { Chat } from "@/components/Chat";
import { AnimatedAIChat, type CommandSuggestion } from "@/components/ui/animated-ai-chat";
import { Chip, SectionLabel, Skeleton } from "@/components/ui/primitives";
import { humanDate, inr, pretty, statusTone } from "@/format";
import type { ChatMessage, Customer, CustomerTicket, Order } from "@/types";

const BASE_COMMANDS: CommandSuggestion[] = [
  { icon: <PackageSearch className="h-4 w-4" />, label: "Track order", description: "Where is my order?", prefix: "/track", template: "Where is my order " },
  { icon: <RotateCcw className="h-4 w-4" />, label: "Return / refund", description: "Damaged, defective or changed mind", prefix: "/return", template: "I want to return my order " },
  { icon: <CircleHelp className="h-4 w-4" />, label: "Product help", description: "Specs, warranty, compatibility", prefix: "/product", template: "Tell me about the " },
  { icon: <Headset className="h-4 w-4" />, label: "Talk to a human", description: "Connect me with support staff", prefix: "/human", template: "I want to talk to a human agent" },
];

const TYPE_ICON: Record<string, typeof Ticket> = { refund: ReceiptIndianRupee, return: RotateCcw, escalation: ShieldAlert, ticket: Ticket };

export function CustomerHelp({
  customer,
  orders,
  messages,
  sending,
  onSend,
  onNewSession,
  onError,
}: {
  customer: Customer;
  orders: Order[];
  messages: ChatMessage[];
  sending: boolean;
  onSend: (text: string) => void;
  onNewSession: () => void;
  onError: (msg: string) => void;
}) {
  const [tickets, setTickets] = useState<CustomerTicket[] | null>(null);
  const agentReplies = messages.filter((m) => m.role === "agent").length;

  useEffect(() => {
    let live = true;
    api
      .tickets(customer.customer_id)
      .then((t) => live && setTickets(t))
      .catch((e: Error) => live && onError(`Could not load your requests: ${e.message}`));
    return () => {
      live = false;
    };
  }, [customer.customer_id, agentReplies, onError]);

  const started = messages.length > 0 || sending;
  const recent = useMemo(() => [...orders].sort((a, b) => b.order_date.localeCompare(a.order_date)).slice(0, 4), [orders]);
  const commands = useMemo<CommandSuggestion[]>(() => {
    const latest = recent[0];
    if (!latest) return BASE_COMMANDS;
    const item = latest.items?.[0] ?? "order";
    return [
      { ...BASE_COMMANDS[0], description: `Latest: ${latest.order_id} (${pretty(latest.order_status)})`, template: `Where is my order ${latest.order_id}?` },
      { ...BASE_COMMANDS[1], description: `${item} · ${latest.order_id}`, template: `I want to return the ${item} from order ${latest.order_id} because ` },
      BASE_COMMANDS[2],
      BASE_COMMANDS[3],
    ];
  }, [recent]);

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
      <section aria-label="Support chat" className="min-w-0">
        {!started ? (
          <div className="overflow-hidden rounded-3xl border border-line bg-navy">
            <AnimatedAIChat
              className="min-h-[540px]"
              title={`Hi ${customer.first_name}, how can we help?`}
              subtitle="Track orders, raise complaints, returns and refunds. Every answer is checked against your real orders."
              placeholder="Describe your issue, e.g. “My headphones from ORD-001234 arrived damaged”"
              assistantName="Nova"
              commands={commands}
              onSubmit={onSend}
              busy={sending}
            />
          </div>
        ) : (
          <div className="flex h-[min(640px,calc(100vh-15rem))] min-h-[420px] flex-col overflow-hidden rounded-3xl border border-line bg-bg">
            <div className="brand-gradient h-1 shrink-0" aria-hidden />
            <Chat
              customer={customer}
              messages={messages}
              sending={sending}
              selectedId={null}
              onSelect={() => undefined}
              onSend={onSend}
              onNewSession={onNewSession}
              view="customer"
            />
          </div>
        )}
      </section>

      <aside aria-label="My orders and support requests" className="space-y-5">
        {recent.length > 0 && (
          <div>
            <SectionLabel>Need help with an order?</SectionLabel>
            <ul className="space-y-2">
              {recent.map((o) => {
                const item = o.items?.[0];
                return (
                  <li key={o.order_id} className="rounded-2xl border border-line bg-surface p-3">
                    <div className="truncate text-xs font-semibold text-fg" title={o.items?.join(", ")}>{o.items?.join(", ") || o.order_id}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5 text-2xs text-faint">
                      <span className="font-mono">{o.order_id}</span>
                      <Chip className={statusTone(o.order_status)}>{pretty(o.order_status)}</Chip>
                      <span className="ml-auto tabular-nums text-muted">{inr(o.total_amount)}</span>
                    </div>
                    <div className="mt-2 flex gap-1.5">
                      <button type="button" disabled={sending} onClick={() => onSend(`Where is my order ${o.order_id}?`)} className="flex-1 rounded-lg px-2 py-1 text-2xs font-medium text-fg ring-1 ring-inset ring-line-strong hover:bg-black/[0.04] disabled:opacity-50">
                        Track
                      </button>
                      <button type="button" disabled={sending} onClick={() => onSend(item ? `I have a problem with my ${item} from order ${o.order_id}` : `I need help with my order ${o.order_id}`)} className="brand-gradient flex-1 rounded-lg px-2 py-1 text-2xs font-semibold text-[#0f1111] hover:brightness-105 disabled:opacity-50">
                        Report a problem
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        <div>
        <SectionLabel right={<span className="text-2xs text-faint">{tickets?.length ?? ""}</span>}>My support requests</SectionLabel>
        {tickets === null ? (
          <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20 rounded-2xl" />)}</div>
        ) : tickets.length === 0 ? (
          <div className="flex flex-col items-center rounded-2xl border border-dashed border-line p-6 text-center">
            <Inbox className="size-6 text-faint" aria-hidden />
            <p className="mt-2 text-sm text-fg">No requests yet</p>
            <p className="text-xs text-muted">Complaints, returns and refunds you raise will appear here.</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {tickets.map((t) => {
              const Icon = TYPE_ICON[t.type] ?? Ticket;
              return (
                <li key={t.id} className="rounded-2xl border border-line bg-surface p-3">
                  <div className="flex items-center gap-2">
                    <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-black/[0.04]">
                      <Icon className="size-3.5 text-muted" aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-semibold capitalize text-fg">{pretty(t.category)}</span>
                      <span className="block font-mono text-2xs text-faint">{t.id}{t.order_id ? ` · ${t.order_id}` : ""}</span>
                    </span>
                    {t.source === "agent" && <Chip className="bg-orange-500/10 text-orange-800 ring-orange-500/25">new</Chip>}
                  </div>
                  {t.summary && <p className="mt-2 line-clamp-2 text-2xs leading-relaxed text-muted">{t.summary}</p>}
                  <div className="mt-2 flex flex-wrap items-center gap-1.5 text-2xs text-faint">
                    {t.status && <Chip className={statusTone(t.status)}>{pretty(t.status)}</Chip>}
                    {t.amount != null && <Chip className="bg-amber-500/10 text-amber-800 ring-amber-500/25">{inr(t.amount)}</Chip>}
                    <span className="ml-auto">{humanDate(t.created_at)}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        </div>
      </aside>
    </div>
  );
}
