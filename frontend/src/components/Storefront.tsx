import { AnimatePresence, motion } from "framer-motion";
import {
  AudioLines,
  BadgePercent,
  Cable,
  Camera,
  ChevronDown,
  Gamepad2,
  Headphones,
  Keyboard,
  Laptop,
  LifeBuoy,
  LogOut,
  MessageCircle,
  Monitor,
  Mouse,
  Package,
  Router,
  Search,
  ShieldCheck,
  ShoppingCart,
  Smartphone,
  Speaker,
  Star,
  Tablet,
  Truck,
  Undo2,
  User,
  Watch,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { humanDate, inr, pretty, statusTone } from "../format";
import type { Category, ChatMessage, Customer, Order, Product } from "../types";
import { Chat } from "./Chat";
import { CustomerHelp } from "./CustomerHelp";
import { Avatar } from "./Sidebar";
import { Chip, Skeleton, cx } from "./ui/primitives";

const CAT_ICON: Record<string, LucideIcon> = {
  Smartphones: Smartphone, Laptops: Laptop, Headphones: Headphones, Earbuds: AudioLines, Smartwatches: Watch,
  Tablets: Tablet, Cameras: Camera, Monitors: Monitor, Keyboards: Keyboard, Mice: Mouse, Speakers: Speaker,
  Networking: Router, Gaming: Gamepad2, Accessories: Cable,
};
const CAT_TINT: Record<string, string> = {
  Smartphones: "from-sky-500/25 to-indigo-500/10", Laptops: "from-violet-500/25 to-fuchsia-500/10",
  Headphones: "from-rose-500/25 to-orange-500/10", Earbuds: "from-amber-500/25 to-rose-500/10",
  Smartwatches: "from-emerald-500/25 to-teal-500/10", Tablets: "from-cyan-500/25 to-sky-500/10",
  Cameras: "from-orange-500/25 to-amber-500/10", Monitors: "from-indigo-500/25 to-violet-500/10",
  Keyboards: "from-slate-400/25 to-slate-600/10", Mice: "from-teal-500/25 to-emerald-500/10",
  Speakers: "from-fuchsia-500/25 to-rose-500/10", Networking: "from-blue-500/25 to-cyan-500/10",
  Gaming: "from-red-500/25 to-violet-500/10", Accessories: "from-lime-500/20 to-emerald-500/10",
};

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const h = setTimeout(() => setV(value), ms);
    return () => clearTimeout(h);
  }, [value, ms]);
  return v;
}

// ------------------------------------------------------------ account menu
type StoreTab = "shop" | "orders" | "help";

function AccountMenu({ customer, onLogout, goto }: { customer: Customer; onLogout: () => void; goto: (t: StoreTab) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const item = "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm text-fg hover:bg-white/5";
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-xl px-2 py-1.5 text-left transition hover:bg-white/5"
      >
        <Avatar c={customer} small />
        <span className="hidden leading-tight md:block">
          <span className="block text-2xs text-faint">Hello,</span>
          <span className="block max-w-[120px] truncate text-xs font-semibold text-fg">{customer.first_name}</span>
        </span>
        <ChevronDown className="size-3.5 text-faint" aria-hidden />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full z-30 mt-2 w-64 rounded-2xl border border-line-strong bg-elevated p-2 shadow-2xl"
            role="menu"
          >
            <div className="flex items-center gap-2.5 border-b border-line px-2.5 pb-2.5 pt-1">
              <Avatar c={customer} />
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold text-fg">{customer.first_name} {customer.last_name}</span>
                <span className="block truncate text-2xs text-faint">{customer.email}</span>
              </span>
            </div>
            <div className="pt-1.5">
              <button type="button" role="menuitem" className={item} onClick={() => { goto("orders"); setOpen(false); }}>
                <Package className="size-4 text-muted" aria-hidden /> My Orders
              </button>
              <button type="button" role="menuitem" className={item} onClick={() => { goto("help"); setOpen(false); }}>
                <LifeBuoy className="size-4 text-muted" aria-hidden /> Help & Complaints
              </button>
              <button type="button" role="menuitem" className={cx(item, "text-rose-300")} onClick={onLogout}>
                <LogOut className="size-4" aria-hidden /> Logout
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ------------------------------------------------------------ product card
function ProductCard({ p, onAsk }: { p: Product; onAsk: (p: Product) => void }) {
  const Icon = CAT_ICON[p.category] ?? Package;
  const out = p.status !== "active";
  return (
    <article className="group flex flex-col overflow-hidden rounded-2xl border border-line bg-surface transition hover:-translate-y-0.5 hover:border-line-strong hover:shadow-card">
      <div className={cx("relative grid aspect-[4/3] place-items-center bg-gradient-to-br", CAT_TINT[p.category] ?? "from-slate-500/20 to-slate-700/10")}>
        <Icon className="size-14 text-white/80 drop-shadow-[0_8px_20px_rgba(0,0,0,0.4)] transition group-hover:scale-105" strokeWidth={1.4} aria-hidden />
        {p.discount_percent > 0 && (
          <span className="absolute left-2.5 top-2.5 rounded-md bg-rose-500 px-1.5 py-0.5 text-2xs font-bold text-white">
            {Math.round(p.discount_percent)}% off
          </span>
        )}
        {out && (
          <span className="absolute right-2.5 top-2.5 rounded-md bg-black/60 px-1.5 py-0.5 text-2xs font-medium text-slate-200">{pretty(p.status)}</span>
        )}
      </div>
      <div className="flex flex-1 flex-col p-3">
        <div className="text-2xs font-medium uppercase tracking-wider text-faint">{p.brand}</div>
        <h3 className="mt-0.5 line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-snug text-fg" title={p.product_name}>
          {p.product_name}
        </h3>
        <div className="mt-1.5 flex items-center gap-1 text-2xs">
          <span className="inline-flex items-center gap-0.5 rounded bg-emerald-600 px-1 py-px font-semibold text-white">
            {p.rating.toFixed(1)} <Star className="size-2.5 fill-current" aria-hidden />
          </span>
          <span className="text-faint">({p.review_count.toLocaleString("en-IN")})</span>
        </div>
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="text-base font-semibold text-fg">{inr(p.price)}</span>
          {p.mrp > p.price && <span className="text-xs text-faint line-through">{inr(p.mrp)}</span>}
        </div>
        <div className="mt-1 text-2xs text-muted">
          {p.warranty_months}-month warranty · {p.returnable ? "Easy returns" : "Non-returnable"}
        </div>
        <button
          type="button"
          onClick={() => onAsk(p)}
          className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-xl bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-fg ring-1 ring-inset ring-white/10 transition hover:bg-white/[0.08]"
        >
          <MessageCircle className="size-3.5" aria-hidden /> Ask the assistant
        </button>
      </div>
    </article>
  );
}

// ------------------------------------------------------------ storefront
export function Storefront({
  customer,
  onLogout,
  orders,
  ordersLoading,
  messages,
  sending,
  onSend,
  onNewSession,
  onError,
}: {
  customer: Customer;
  onLogout: () => void;
  orders: Order[];
  ordersLoading: boolean;
  messages: ChatMessage[];
  sending: boolean;
  onSend: (text: string) => void;
  onNewSession: () => void;
  onError: (msg: string) => void;
}) {
  const [tab, setTab] = useState<StoreTab>("shop");
  const [cats, setCats] = useState<Category[]>([]);
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
  const seen = useRef(messages.length);
  const unread = !chatOpen && messages.length > seen.current;

  useEffect(() => {
    api.categories().then(setCats).catch((e: Error) => onError(`Could not load categories: ${e.message}`));
  }, [onError]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    api
      .products(dq.trim(), cat, 24)
      .then((r) => live && setProducts(r))
      .catch((e: Error) => live && onError(`Could not load products: ${e.message}`))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [dq, cat, onError]);

  useEffect(() => {
    if (chatOpen) seen.current = messages.length;
  }, [chatOpen, messages.length]);

  const ask = (text: string) => {
    setChatOpen(false);
    setTab("help");
    onSend(text);
  };

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-bg">
      {/* store header */}
      <div className="shrink-0 border-b border-line bg-surface/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <span className="brand-gradient grid size-8 place-items-center rounded-lg" aria-hidden>
              <ShoppingCart className="size-4 text-white" />
            </span>
            <span className="hidden text-lg font-bold tracking-tight text-fg sm:block">
              Nova<span className="brand-text">Mart</span>
            </span>
          </div>
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">Search products</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" aria-hidden />
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setTab("shop");
              }}
              placeholder="Search for phones, laptops, headphones…"
              className="w-full rounded-xl border border-line bg-elevated py-2 pl-9 pr-3 text-sm text-fg placeholder:text-faint focus:border-orange-500/50 focus:outline-none focus:ring-2 focus:ring-orange-500/20"
            />
          </label>
          <nav className="flex items-center gap-1" aria-label="Store">
            {(
              [
                ["shop", "Shop"],
                ["orders", "My Orders"],
                ["help", "Help & Complaints"],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setTab(k)}
                aria-current={tab === k ? "page" : undefined}
                className={cx(
                  "whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-medium transition",
                  tab === k ? "bg-white/[0.08] text-fg" : "text-muted hover:text-fg",
                )}
              >
                {label}
              </button>
            ))}
          </nav>
          <AccountMenu customer={customer} onLogout={onLogout} goto={setTab} />
          <span className="relative hidden sm:block" aria-label="Cart (demo)">
            <ShoppingCart className="size-5 text-muted" aria-hidden />
          </span>
        </div>
        {tab === "shop" && (
          <div className="no-scrollbar mx-auto flex max-w-6xl gap-1.5 overflow-x-auto px-4 pb-2.5" role="tablist" aria-label="Categories">
            {[{ category: "", count: 0 }, ...cats].map((c) => {
              const Icon = c.category ? CAT_ICON[c.category] ?? Package : BadgePercent;
              return (
                <button
                  key={c.category || "all"}
                  type="button"
                  role="tab"
                  aria-selected={cat === c.category}
                  onClick={() => setCat(c.category)}
                  className={cx(
                    "inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition",
                    cat === c.category ? "brand-gradient text-white ring-transparent" : "bg-white/[0.03] text-muted ring-white/10 hover:text-fg",
                  )}
                >
                  <Icon className="size-3.5" aria-hidden />
                  {c.category || "All deals"}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* body */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-4 py-5">
          {tab === "help" ? (
            <CustomerHelp customer={customer} messages={messages} sending={sending} onSend={onSend} onNewSession={onNewSession} onError={onError} />
          ) : tab === "shop" ? (
            <>
              {!q && !cat && (
                <section className="relative mb-6 overflow-hidden rounded-3xl border border-orange-500/20 bg-[linear-gradient(120deg,rgba(239,68,68,0.22),rgba(249,115,22,0.12)_45%,rgba(17,24,39,0.6))] p-6 sm:p-8">
                  <div className="max-w-lg">
                    <Chip className="bg-white/10 text-orange-100 ring-white/15">Festive Electronics Sale</Chip>
                    <h1 className="mt-3 text-2xl font-bold tracking-tight text-white sm:text-3xl">Up to 40% off top tech</h1>
                    <p className="mt-2 text-sm text-orange-50/80">
                      Phones, laptops, audio and more. Need help with an order? Our assistant checks your real order and policy before it answers.
                    </p>
                    <button
                      type="button"
                      onClick={() => setTab("help")}
                      className="mt-4 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-orange-50"
                    >
                      <LifeBuoy className="size-4" aria-hidden /> Get support
                    </button>
                  </div>
                  <div className="pointer-events-none absolute -right-6 -top-6 hidden size-48 rounded-full bg-orange-500/20 blur-3xl sm:block" aria-hidden />
                  <ShoppingCart className="pointer-events-none absolute bottom-4 right-6 hidden size-28 text-white/10 sm:block" strokeWidth={1.2} aria-hidden />
                </section>
              )}
              {!q && !cat && (
                <div className="mb-6 grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {[
                    [Truck, "Free delivery", "on orders above ₹1,000"],
                    [Undo2, "Easy returns", "7–10 day return window"],
                    [ShieldCheck, "Verified support", "no guesswork, real data"],
                  ].map(([Icon, t, s]) => {
                    const I = Icon as LucideIcon;
                    return (
                      <div key={t as string} className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3">
                        <I className="size-5 text-orange-300" aria-hidden />
                        <div>
                          <div className="text-sm font-medium text-fg">{t as string}</div>
                          <div className="text-2xs text-muted">{s as string}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              <div className="mb-3 flex items-baseline justify-between">
                <h2 className="text-base font-semibold text-fg">{q ? `Results for “${q}”` : cat || "Trending now"}</h2>
                {!loading && <span className="text-2xs text-faint">{products.length} products</span>}
              </div>
              {loading ? (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-72 rounded-2xl" />
                  ))}
                </div>
              ) : products.length === 0 ? (
                <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">No products match your search.</p>
              ) : (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
                  {products.map((p) => (
                    <ProductCard key={p.product_id} p={p} onAsk={(x) => ask(`Tell me about the ${x.product_name}`)} />
                  ))}
                </div>
              )}
            </>
          ) : (
            <section aria-label="My orders">
              <h2 className="mb-3 text-base font-semibold text-fg">My Orders</h2>
              {!customer ? (
                <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">Sign in (top right) to see your orders.</p>
              ) : ordersLoading ? (
                <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}</div>
              ) : orders.length === 0 ? (
                <p className="text-sm text-muted">You have no orders yet.</p>
              ) : (
                <ul className="space-y-2">
                  {orders.slice(0, 20).map((o) => (
                    <li key={o.order_id} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4 sm:flex-row sm:items-center">
                      <div className="grid size-12 shrink-0 place-items-center rounded-xl bg-white/[0.04]">
                        <Package className="size-5 text-muted" aria-hidden />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-fg" title={o.items?.join(", ")}>
                          {o.items?.join(", ") || o.order_id}
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-2xs text-faint">
                          <span className="font-mono">{o.order_id}</span>
                          <span>·</span>
                          <span>Ordered {humanDate(o.order_date)}</span>
                          <Chip className={statusTone(o.order_status)}>{pretty(o.order_status)}</Chip>
                          {o.refund_status !== "none" && <Chip className={statusTone(o.refund_status)}>refund {pretty(o.refund_status)}</Chip>}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="mr-2 text-sm font-semibold tabular-nums text-fg">{inr(o.total_amount)}</span>
                        <button
                          type="button"
                          onClick={() => ask(`Where is my order ${o.order_id}?`)}
                          className="rounded-lg bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-fg ring-1 ring-inset ring-white/10 hover:bg-white/[0.08]"
                        >
                          Track
                        </button>
                        <button
                          type="button"
                          onClick={() => ask(`I need help with my order ${o.order_id}`)}
                          className="brand-gradient rounded-lg px-2.5 py-1.5 text-xs font-semibold text-white hover:brightness-110"
                        >
                          Get help
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </div>
      </div>

      {/* floating support widget */}
      <AnimatePresence>
        {chatOpen && tab !== "help" && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="absolute bottom-20 right-4 z-30 flex h-[min(560px,calc(100%-9rem))] w-[min(400px,calc(100%-2rem))] flex-col overflow-hidden rounded-3xl border border-line-strong bg-bg shadow-2xl"
            role="dialog"
            aria-label="NovaMart support chat"
          >
            <div className="brand-gradient flex shrink-0 items-center gap-3 px-4 py-3 text-white">
              <LifeBuoy className="size-5" aria-hidden />
              <div className="leading-tight">
                <div className="text-sm font-semibold">NovaMart Support</div>
                <div className="text-2xs text-white/80">Verified answers from your real order data</div>
              </div>
              <button type="button" aria-label="Close support chat" onClick={() => setChatOpen(false)} className="ml-auto rounded-lg p-1 hover:bg-white/15">
                <X className="size-4" />
              </button>
            </div>
            {customer ? (
              <div className="min-h-0 flex-1">
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
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
                <User className="size-8 text-faint" aria-hidden />
                <p className="text-sm font-medium text-fg">Sign in to chat with support</p>
                <p className="text-xs text-muted">Use the account menu at the top right to pick a demo customer.</p>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
      {tab !== "help" && (
      <button
        type="button"
        onClick={() => setChatOpen((o) => !o)}
        aria-label={chatOpen ? "Close support chat" : "Open support chat"}
        className="brand-gradient absolute bottom-4 right-4 z-30 grid size-13 place-items-center rounded-full text-white shadow-[0_12px_30px_-8px_rgba(249,115,22,0.8)] transition hover:scale-105"
      >
        {chatOpen ? <X className="size-5" /> : <MessageCircle className="size-6" />}
        {unread && <span className="absolute right-0.5 top-0.5 size-3 rounded-full bg-emerald-400 ring-2 ring-bg" aria-label="New reply" />}
      </button>
      )}
    </div>
  );
}
