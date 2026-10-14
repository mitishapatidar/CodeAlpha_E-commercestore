import { AnimatePresence, motion } from "framer-motion";
import {
  AudioLines,
  BadgePercent,
  Cable,
  Camera,
  ChevronDown,
  ChevronLeft,
  Gamepad2,
  Headphones,
  Keyboard,
  Laptop,
  LifeBuoy,
  LogOut,
  MessageCircle,
  Minus,
  Plus,
  Trash2,
  Monitor,
  Mouse,
  Package,
  Router,
  Search,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  Smartphone,
  Speaker,
  Star,
  Tablet,
  Truck,
  Undo2,
  Watch,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { humanDate, inr, pretty, statusTone } from "../format";
import type { Category, ChatMessage, Customer, Order, Product } from "../types";
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
const TABS: StoreTab[] = ["shop", "orders", "help"];
const tabFromHash = (): StoreTab => {
  const h = window.location.hash.slice(1) as StoreTab;
  return TABS.includes(h) ? h : "shop";
};

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

  const menuItemClass = "flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-medium !text-slate-200 transition hover:bg-white/10 hover:!text-white";

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-xl px-2 py-1.5 text-left transition hover:bg-white/10"
      >
        <Avatar c={customer} small />
        <span className="hidden leading-tight md:block">
          <span className="block text-2xs text-slate-400">Hello,</span>
          <span className="block max-w-[120px] truncate text-xs font-semibold text-white">{customer.first_name}</span>
        </span>
        <ChevronDown className="size-3.5 text-slate-400" aria-hidden />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full z-50 mt-2 w-64 rounded-2xl border border-slate-700/80 bg-navy-2 p-2 shadow-2xl"
            role="menu"
          >
            <div className="flex items-center gap-2.5 border-b border-slate-700/80 px-2.5 pb-2.5 pt-1.5">
              <Avatar c={customer} />
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold !text-white">{customer.first_name} {customer.last_name}</span>
                <span className="block truncate text-2xs !text-slate-400">{customer.email}</span>
              </span>
            </div>
            <div className="pt-1.5 space-y-0.5">
              <button
                type="button"
                role="menuitem"
                className={menuItemClass}
                onClick={() => { goto("orders"); setOpen(false); }}
              >
                <Package className="size-4 !text-slate-400" aria-hidden />
                <span>My Orders</span>
              </button>
              <button
                type="button"
                role="menuitem"
                className={menuItemClass}
                onClick={() => { goto("help"); setOpen(false); }}
              >
                <LifeBuoy className="size-4 !text-slate-400" aria-hidden />
                <span>Help & Complaints</span>
              </button>
              <div className="my-1 border-t border-slate-700/60" />
              <button
                type="button"
                role="menuitem"
                className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-medium !text-rose-400 transition hover:bg-rose-500/15 hover:!text-rose-300"
                onClick={onLogout}
              >
                <LogOut className="size-4 !text-rose-400" aria-hidden />
                <span>Logout</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ------------------------------------------------------------ product card
function ProductCard({ p, qty, onAsk, onAdd }: { p: Product; qty: number; onAsk: (p: Product) => void; onAdd: (p: Product) => void }) {
  const Icon = CAT_ICON[p.category] ?? Package;
  const out = p.status !== "active";
  return (
    <article className="group flex flex-col overflow-hidden rounded-2xl border border-line bg-surface transition hover:-translate-y-0.5 hover:border-line-strong hover:shadow-card">
      <div className={cx("relative grid aspect-[4/3] place-items-center bg-gradient-to-br", CAT_TINT[p.category] ?? "from-slate-500/20 to-slate-700/10")}>
        <Icon className="size-14 text-navy-2/80 drop-shadow-[0_6px_14px_rgba(15,17,17,0.15)] transition group-hover:scale-105" strokeWidth={1.4} aria-hidden />
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
          disabled={out}
          onClick={() => onAdd(p)}
          className="brand-gradient mt-3 inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-[#0f1111] transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <ShoppingCart className="size-3.5" aria-hidden /> {out ? "Unavailable" : qty > 0 ? `In cart (${qty}) · Add more` : "Add to cart"}
        </button>
        <button
          type="button"
          onClick={() => onAsk(p)}
          className="mt-1.5 inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-1 text-xs font-medium text-amz-link transition hover:bg-black/[0.04] hover:underline"
        >
          <MessageCircle className="size-3.5" aria-hidden /> Ask the assistant
        </button>
      </div>
    </article>
  );
}

// ------------------------------------------------------------ cart
type CartLine = { p: Product; qty: number };
const FREE_SHIP_AT = 1000;
const SHIP_FEE = 79;

function loadCart(key: string): Record<string, CartLine> {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Record<string, CartLine>) : {};
  } catch {
    return {};
  }
}

function CartDrawer({
  lines,
  onQty,
  onClose,
  onCheckout,
}: {
  lines: CartLine[];
  onQty: (id: string, qty: number) => void;
  onClose: () => void;
  onCheckout: () => void;
}) {
  const subtotal = lines.reduce((s, l) => s + l.p.price * l.qty, 0);
  const savings = lines.reduce((s, l) => s + Math.max(0, l.p.mrp - l.p.price) * l.qty, 0);
  const shipping = subtotal === 0 || subtotal >= FREE_SHIP_AT ? 0 : SHIP_FEE;
  const count = lines.reduce((s, l) => s + l.qty, 0);
  const plural = count === 1 ? "" : "s";
  return (
    <motion.div className="absolute inset-0 z-40 flex justify-end bg-black/40" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
      <motion.aside
        initial={{ x: 40, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 40, opacity: 0 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Shopping cart"
        className="flex h-full w-full max-w-md flex-col bg-surface shadow-2xl"
      >
        <div className="flex items-center gap-3 border-b-2 border-amz-orange bg-navy px-4 py-3 text-white">
          <ShoppingCart className="size-5 text-amz-orange" aria-hidden />
          <div className="text-sm font-semibold">Your cart · {count} item{plural}</div>
          <button type="button" aria-label="Close cart" onClick={onClose} className="ml-auto rounded-lg p-1 hover:bg-white/15">
            <X className="size-4" />
          </button>
        </div>
        {lines.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
            <ShoppingBag className="size-10 text-faint" aria-hidden />
            <p className="text-sm font-medium text-fg">Your cart is empty</p>
            <p className="text-xs text-muted">Add products from the shop to see them here.</p>
            <button type="button" onClick={onClose} className="brand-gradient mt-2 rounded-xl px-4 py-2 text-xs font-semibold text-[#0f1111]">
              Continue shopping
            </button>
          </div>
        ) : (
          <>
            <ul className="min-h-0 flex-1 divide-y divide-line overflow-y-auto px-4">
              {lines.map(({ p, qty }) => {
                const Icon = CAT_ICON[p.category] ?? Package;
                return (
                  <li key={p.product_id} className="flex gap-3 py-3">
                    <div className={cx("grid size-16 shrink-0 place-items-center rounded-xl bg-gradient-to-br", CAT_TINT[p.category] ?? "from-slate-500/20 to-slate-700/10")}>
                      <Icon className="size-7 text-navy-2/80" strokeWidth={1.5} aria-hidden />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="line-clamp-2 text-sm font-medium leading-snug text-fg">{p.product_name}</div>
                      <div className="mt-0.5 text-2xs text-emerald-700">In stock · {p.returnable ? "Easy returns" : "Non-returnable"}</div>
                      <div className="mt-2 flex items-center gap-2">
                        <div className="flex items-center rounded-lg ring-1 ring-inset ring-line-strong">
                          <button type="button" aria-label="Decrease quantity" onClick={() => onQty(p.product_id, qty - 1)} className="grid size-7 place-items-center rounded-l-lg hover:bg-black/5">
                            {qty === 1 ? <Trash2 className="size-3.5 text-rose-700" /> : <Minus className="size-3.5" />}
                          </button>
                          <span className="w-7 text-center text-xs font-semibold tabular-nums text-fg">{qty}</span>
                          <button type="button" aria-label="Increase quantity" disabled={qty >= 10} onClick={() => onQty(p.product_id, qty + 1)} className="grid size-7 place-items-center rounded-r-lg hover:bg-black/5 disabled:opacity-40">
                            <Plus className="size-3.5" />
                          </button>
                        </div>
                        <button type="button" onClick={() => onQty(p.product_id, 0)} className="text-2xs font-medium text-amz-link hover:underline">
                          Remove
                        </button>
                        <span className="ml-auto text-sm font-semibold tabular-nums text-fg">{inr(p.price * qty)}</span>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
            <div className="space-y-1.5 border-t border-line bg-bg px-4 py-4 text-sm">
              <div className="flex justify-between text-muted"><span>Subtotal</span><span className="tabular-nums text-fg">{inr(subtotal)}</span></div>
              {savings > 0 && <div className="flex justify-between text-emerald-700"><span>You save</span><span className="tabular-nums">−{inr(savings)}</span></div>}
              <div className="flex justify-between text-muted">
                <span>Delivery</span>
                <span className="tabular-nums text-fg">{shipping === 0 ? "FREE" : inr(shipping)}</span>
              </div>
              {shipping > 0 && <p className="text-2xs text-muted">Add {inr(FREE_SHIP_AT - subtotal)} more for free delivery.</p>}
              <div className="flex justify-between border-t border-line pt-2 text-base font-semibold text-fg">
                <span>Total</span><span className="tabular-nums text-price">{inr(subtotal + shipping)}</span>
              </div>
              <button type="button" onClick={onCheckout} className="brand-gradient mt-2 w-full rounded-xl py-2.5 text-sm font-semibold text-[#0f1111] hover:brightness-105">
                Proceed to buy ({count} item{plural})
              </button>
              <p className="text-center text-2xs text-faint">Demo checkout: no payment is taken.</p>
            </div>
          </>
        )}
      </motion.aside>
    </motion.div>
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
  // each tab is a URL hash (#shop / #orders / #help) so the browser Back button works
  const [tab, setTabState] = useState<StoreTab>(tabFromHash);
  const setTab = useCallback((t: StoreTab) => {
    if (t !== tabFromHash()) window.history.pushState(null, "", `#${t}`);
    setTabState(t);
  }, []);
  const goBack = () => (window.history.length > 1 ? window.history.back() : setTab("shop"));

  useEffect(() => {
    const onPop = () => setTabState(tabFromHash());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const [cats, setCats] = useState<Category[]>([]);
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const cartKey = `novamart.cart.${customer.customer_id}`;
  const [cart, setCart] = useState<Record<string, CartLine>>(() => loadCart(cartKey));
  const [cartOpen, setCartOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const cartLines = useMemo(() => Object.values(cart), [cart]);
  const cartCount = cartLines.reduce((s, l) => s + l.qty, 0);

  useEffect(() => {
    try {
      sessionStorage.setItem(cartKey, JSON.stringify(cart));
    } catch {
      /* storage unavailable: the cart still works for this page view */
    }
  }, [cart, cartKey]);

  useEffect(() => {
    if (!toast) return;
    const h = setTimeout(() => setToast(null), 2600);
    return () => clearTimeout(h);
  }, [toast]);

  const addToCart = (p: Product) => {
    setCart((c) => ({ ...c, [p.product_id]: { p, qty: Math.min(10, (c[p.product_id]?.qty ?? 0) + 1) } }));
    setToast(`Added to cart: ${p.product_name}`);
  };
  const setQty = (id: string, qty: number) =>
    setCart((c) => {
      const next = { ...c };
      if (qty <= 0) delete next[id];
      else next[id] = { ...next[id], qty: Math.min(10, qty) };
      return next;
    });
  const checkout = () => {
    setCart({});
    setCartOpen(false);
    setToast("Order placed (demo). No payment was taken.");
  };

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


  const ask = (text: string) => {
    setTab("help");
    onSend(text);
  };

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-bg">
      {/* store header */}
      <div className="shrink-0 bg-navy text-white [&_.text-fg]:text-white [&_.text-muted]:text-slate-300 [&_.text-faint]:text-slate-400">
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
              className="w-full rounded-xl border-2 border-transparent bg-white py-2 pl-9 pr-3 text-sm text-[#0f1111] placeholder:text-[#6f7373] focus:border-amz-orange focus:outline-none focus:ring-2 focus:ring-orange-500/20"
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
                  tab === k ? "bg-white/15 text-white font-semibold" : "text-slate-300 hover:text-white hover:bg-white/10",
                )}
              >
                {label}
              </button>
            ))}
          </nav>
          <AccountMenu customer={customer} onLogout={onLogout} goto={setTab} />
          <button
            type="button"
            onClick={() => setCartOpen(true)}
            aria-label={`Open cart, ${cartCount} item${cartCount === 1 ? "" : "s"}`}
            className="relative flex shrink-0 items-center gap-1 rounded-xl px-2 py-1.5 transition hover:bg-white/10"
          >
            <ShoppingCart className="size-6 text-white" aria-hidden />
            <span className="hidden text-xs font-semibold text-white lg:inline">Cart</span>
            {cartCount > 0 && (
              <span className="absolute -top-0.5 left-5 grid min-w-5 place-items-center rounded-full bg-amz-orange px-1 text-2xs font-bold text-[#0f1111]">
                {cartCount}
              </span>
            )}
          </button>
        </div>
        {tab === "shop" && (
          <div className="no-scrollbar mx-auto flex max-w-6xl gap-1.5 overflow-x-auto bg-navy-2 px-4 py-2" role="tablist" aria-label="Categories">
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
                    cat === c.category ? "brand-gradient text-[#0f1111] ring-transparent" : "bg-black/[0.03] text-muted ring-black/10 hover:text-fg",
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
          {tab !== "shop" && (
            <button type="button" onClick={goBack} className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-amz-link hover:underline">
              <ChevronLeft className="size-4" aria-hidden /> Back
            </button>
          )}
          {tab === "help" ? (
            <CustomerHelp customer={customer} orders={orders} messages={messages} sending={sending} onSend={onSend} onNewSession={onNewSession} onError={onError} />
          ) : tab === "shop" ? (
            <>
              {!q && !cat && (
                <section className="relative mb-6 overflow-hidden rounded-3xl border border-orange-500/20 bg-[linear-gradient(120deg,#232f3e,#37475a)] p-6 sm:p-8">
                  <div className="max-w-lg">
                    <Chip className="bg-white/10 text-amber-300 ring-white/15">Festive Electronics Sale</Chip>
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
                        <I className="size-5 text-amber-500" aria-hidden />
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
                    <ProductCard key={p.product_id} p={p} qty={cart[p.product_id]?.qty ?? 0} onAdd={addToCart} onAsk={(x) => ask(`Tell me about the ${x.product_name}`)} />
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
                      <div className="grid size-12 shrink-0 place-items-center rounded-xl bg-black/[0.04]">
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
                          className="rounded-lg bg-black/[0.04] px-2.5 py-1.5 text-xs font-medium text-fg ring-1 ring-inset ring-black/10 hover:bg-black/[0.08]"
                        >
                          Track
                        </button>
                        <button
                          type="button"
                          onClick={() => ask(o.items?.length ? `I have a problem with my ${o.items[0]} from order ${o.order_id}` : `I need help with my order ${o.order_id}`)}
                          className="brand-gradient rounded-lg px-2.5 py-1.5 text-xs font-semibold text-[#0f1111] hover:brightness-110"
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

      {/* cart drawer + toast */}
      <AnimatePresence>
        {cartOpen && <CartDrawer lines={cartLines} onQty={setQty} onClose={() => setCartOpen(false)} onCheckout={checkout} />}
      </AnimatePresence>
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            role="status"
            className="absolute inset-x-0 top-16 z-50 mx-auto flex w-fit max-w-[calc(100%-2rem)] items-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-xs font-medium text-white shadow-2xl ring-1 ring-amz-orange/50"
          >
            <ShoppingCart className="size-4 shrink-0 text-amz-orange" aria-hidden />
            <span className="truncate">{toast}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* support button: opens the full Help & Complaints page (same agent, same chat) */}
      {tab !== "help" && (
      <button
        type="button"
        onClick={() => setTab("help")}
        aria-label="Open Help & Complaints"
        title="Help & Complaints"
        className="brand-gradient absolute bottom-4 right-4 z-30 grid size-13 place-items-center rounded-full text-[#0f1111] shadow-[0_12px_30px_-8px_rgba(255,153,0,0.4)] transition hover:scale-105"
      >
        <MessageCircle className="size-6" />
              </button>
      )}
    </div>
  );
}
