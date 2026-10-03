import { MapPin, Play, RotateCcw, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { DECISION, TIER_TONE, humanDate, initials, inr, pretty, statusTone } from "../format";
import type { Customer, Order, Scenario } from "../types";
import { Button, Chip, SectionLabel, Skeleton, cx } from "./ui/primitives";

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const h = setTimeout(() => setV(value), ms);
    return () => clearTimeout(h);
  }, [value, ms]);
  return v;
}

export function Sidebar({
  customer,
  onSelectCustomer,
  orders,
  ordersLoading,
  scenarios,
  scenariosLoading,
  runScenario,
  resetDemo,
  busy,
  onError,
}: {
  customer: Customer | null;
  onSelectCustomer: (c: Customer) => void;
  orders: Order[];
  ordersLoading: boolean;
  scenarios: Scenario[];
  scenariosLoading: boolean;
  runScenario: (s: Scenario) => void;
  resetDemo: () => void;
  busy: boolean;
  onError: (msg: string, retry?: () => void) => void;
}) {
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [results, setResults] = useState<Customer[]>([]);
  const [searching, setSearching] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!dq.trim()) {
      setResults([]);
      return;
    }
    let live = true;
    setSearching(true);
    api
      .customers(dq.trim(), 8)
      .then((r) => live && setResults(r))
      .catch((e: Error) => live && onError(`Customer search failed: ${e.message}`))
      .finally(() => live && setSearching(false));
    return () => {
      live = false;
    };
  }, [dq, onError]);

  const groups = useMemo(() => {
    const m = new Map<string, Scenario[]>();
    scenarios.forEach((s) => m.set(s.category, [...(m.get(s.category) ?? []), s]));
    return [...m.entries()];
  }, [scenarios]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* search */}
      <div className="border-b border-line p-3">
        <label className="relative block">
          <span className="sr-only">Search customers</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" aria-hidden />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search customer, email, ID"
            className="w-full rounded-xl border border-line bg-elevated py-2 pl-9 pr-9 text-sm text-fg placeholder:text-faint focus:border-amz-orange focus:outline-none focus:ring-2 focus:ring-orange-500/20"
          />
          {q ? (
            <button type="button" aria-label="Clear search" onClick={() => setQ("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-faint hover:text-fg">
              <X className="size-4" />
            </button>
          ) : (
            <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-line px-1.5 font-mono text-2xs text-faint">/</kbd>
          )}
        </label>
        {q.trim() && (
          <div className="mt-2 max-h-64 overflow-y-auto rounded-xl border border-line bg-elevated p-1" role="listbox" aria-label="Customer results">
            {searching && results.length === 0 ? (
              <div className="space-y-1.5 p-1.5">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-9" />
                ))}
              </div>
            ) : results.length === 0 ? (
              <p className="p-3 text-xs text-faint">No customers match “{q}”.</p>
            ) : (
              results.map((c) => (
                <button
                  key={c.customer_id}
                  type="button"
                  role="option"
                  aria-selected={customer?.customer_id === c.customer_id}
                  onClick={() => {
                    onSelectCustomer(c);
                    setQ("");
                  }}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left hover:bg-black/5"
                >
                  <Avatar c={c} small />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-fg">
                      {c.first_name} {c.last_name}
                    </span>
                    <span className="block truncate font-mono text-2xs text-faint">{c.customer_id}</span>
                  </span>
                  <Chip className={TIER_TONE[c.loyalty_tier] ?? undefined}>{c.loyalty_tier}</Chip>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-3">
        {/* customer */}
        <section aria-label="Selected customer">
          <SectionLabel>Customer</SectionLabel>
          {customer ? (
            <div className="rounded-2xl border border-line bg-elevated p-3">
              <div className="flex items-center gap-3">
                <Avatar c={customer} />
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-fg">
                    {customer.first_name} {customer.last_name}
                  </div>
                  <div className="truncate text-xs text-muted" title={customer.email}>
                    {customer.email}
                  </div>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Chip className={TIER_TONE[customer.loyalty_tier] ?? undefined}>{customer.loyalty_tier}</Chip>
                <Chip>{pretty(customer.customer_segment)}</Chip>
                <Chip className={statusTone(customer.account_status)}>{customer.account_status}</Chip>
                {customer.city && (
                  <Chip>
                    <MapPin className="size-3" aria-hidden />
                    {customer.city}
                  </Chip>
                )}
              </div>
              <div className="mt-2 font-mono text-2xs text-faint">{customer.customer_id}</div>
            </div>
          ) : (
            <p className="rounded-2xl border border-dashed border-line p-4 text-xs text-faint">
              Search a customer or run a demo scenario below.
            </p>
          )}
        </section>

        {/* orders */}
        {customer && (
          <section aria-label="Orders">
            <SectionLabel right={<span className="text-2xs text-faint">{orders.length || ""}</span>}>Orders</SectionLabel>
            {ordersLoading ? (
              <div className="space-y-2">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-14" />
                ))}
              </div>
            ) : orders.length === 0 ? (
              <p className="text-xs text-faint">No orders on this account.</p>
            ) : (
              <ul className="space-y-1.5">
                {orders.slice(0, 12).map((o) => (
                  <li key={o.order_id} className="rounded-xl border border-line bg-surface px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-medium text-fg">{o.order_id}</span>
                      <span className="text-xs font-semibold tabular-nums text-fg">{inr(o.total_amount)}</span>
                    </div>
                    {o.items && o.items.length > 0 && (
                      <div className="mt-0.5 truncate text-2xs text-muted" title={o.items.join(", ")}>
                        {o.items.join(", ")}
                      </div>
                    )}
                    <div className="mt-1.5 flex flex-wrap items-center gap-1">
                      <span className="mr-1 text-2xs text-faint">{humanDate(o.order_date)}</span>
                      <Chip className={statusTone(o.order_status)}>{pretty(o.order_status)}</Chip>
                      {o.payment_status !== "paid" && <Chip className={statusTone(o.payment_status)}>{pretty(o.payment_status)}</Chip>}
                      {o.refund_status !== "none" && <Chip className={statusTone(o.refund_status)}>refund {pretty(o.refund_status)}</Chip>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {/* scenarios */}
        <section aria-label="Demo scenarios">
          <SectionLabel right={<span className="text-2xs text-faint">from real data</span>}>Demo scenarios</SectionLabel>
          {scenariosLoading ? (
            <div className="space-y-2">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {groups.map(([cat, items]) => (
                <div key={cat}>
                  <div className="mb-1 text-2xs font-medium text-muted">{cat}</div>
                  <ul className="space-y-1">
                    {items.map((s) => {
                      const d = DECISION[s.expected_decision];
                      return (
                        <li key={s.id}>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => runScenario(s)}
                            title={s.message}
                            className="group flex w-full items-center gap-2 rounded-xl border border-transparent px-2 py-1.5 text-left transition hover:border-line hover:bg-black/[0.03] disabled:opacity-50"
                          >
                            <span className="grid size-6 shrink-0 place-items-center rounded-lg bg-black/[0.04] text-faint transition group-hover:brand-gradient group-hover:text-[#0f1111]">
                              <Play className="size-3" aria-hidden />
                            </span>
                            <span className="min-w-0 flex-1 truncate text-xs text-fg">{s.title}</span>
                            <span className={cx("shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset", d.text, d.bg, d.ring)}>
                              {s.expected_decision}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* reset */}
      <div className="border-t border-line p-3">
        {confirmReset ? (
          <div className="flex items-center gap-2">
            <span className="flex-1 text-2xs text-muted">Clear refunds/tickets the agent created?</span>
            <Button variant="danger" onClick={() => { resetDemo(); setConfirmReset(false); }}>
              Confirm
            </Button>
            <Button onClick={() => setConfirmReset(false)}>Cancel</Button>
          </div>
        ) : (
          <Button className="w-full" onClick={() => setConfirmReset(true)}>
            <RotateCcw className="size-3.5" aria-hidden /> Reset demo data
          </Button>
        )}
      </div>
    </div>
  );
}

export function Avatar({ c, small }: { c: Pick<Customer, "first_name" | "last_name">; small?: boolean }) {
  return (
    <span
      className={cx(
        "grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-slate-600 to-slate-800 font-semibold text-white ring-1 ring-black/10",
        small ? "size-7 text-2xs" : "size-10 text-sm",
      )}
      aria-hidden
    >
      {initials(c.first_name, c.last_name)}
    </span>
  );
}
