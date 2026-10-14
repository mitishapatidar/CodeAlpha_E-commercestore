import { MessageCircle, RotateCcw, ShieldCheck, ShoppingCart, Star, Truck, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { inr, pretty } from "../format";
import type { Product, ProductDetail } from "../types";
import { Skeleton } from "./ui/primitives";

/** Amazon-style product page: gallery, title/rating/price, specs, buy box and related products. */
export function ProductPage({
  id,
  onAdd,
  onBuyNow,
  onAsk,
  onOpen,
  onError,
}: {
  id: string;
  onAdd: (p: Product, qty: number) => void;
  onBuyNow: (p: Product, qty: number) => void;
  onAsk: (p: Product) => void;
  onOpen: (id: string) => void;
  onError: (msg: string) => void;
}) {
  const [p, setP] = useState<ProductDetail | null>(null);
  const [qty, setQty] = useState(1);

  useEffect(() => {
    let live = true;
    setP(null);
    setQty(1);
    api
      .product(id)
      .then((d) => live && setP(d))
      .catch((e: Error) => live && onError(`Could not load the product: ${e.message}`));
    return () => {
      live = false;
    };
  }, [id, onError]);

  if (!p) return <Skeleton className="h-[520px] rounded-2xl" />;

  const stock = p.stock_quantity ?? 0;
  const available = p.status === "active" && stock > 0;
  const maxQty = Math.min(10, Math.max(stock, 1));
  const big = p.image_url?.replace("w=600", "w=1000");
  const specs = [
    ["Brand", p.brand],
    ["Model", p.product_name],
    ["Category", `${p.category} · ${p.subcategory}`],
    ["Colour", p.color],
    ...Object.entries(p.specs),
    ["Warranty", `${p.warranty_months} months`],
  ].filter(([, v]) => v);

  return (
    <div className="space-y-6">
      <nav className="text-xs text-muted" aria-label="Breadcrumb">
        Shop › {p.category} › <span className="text-fg">{p.subcategory}</span>
      </nav>

      <section className="grid gap-6 rounded-2xl bg-surface p-4 sm:p-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_280px]">
        <div className="overflow-hidden rounded-xl bg-bg">
          {big ? <img src={big} alt={p.product_name} className="aspect-square w-full object-cover" /> : <div className="aspect-square" />}
        </div>

        <div className="min-w-0">
          <div className="text-xs font-medium text-amz-link">Visit the {p.brand} Store</div>
          <h1 className="mt-1 text-xl font-semibold leading-snug text-fg sm:text-2xl">{p.product_name}</h1>
          <div className="mt-2 flex items-center gap-2 text-sm">
            {p.rating != null && p.review_count > 0 ? (
              <>
                <span className="inline-flex items-center gap-0.5 rounded bg-emerald-600 px-1.5 py-0.5 text-xs font-semibold text-white">
                  {p.rating.toFixed(1)} <Star className="size-3 fill-current" aria-hidden />
                </span>
                <span className="text-amz-link">{p.review_count.toLocaleString("en-IN")} ratings</span>
              </>
            ) : (
              <span className="text-muted">No ratings yet</span>
            )}
          </div>
          <hr className="my-4 border-line" />
          <div className="flex items-baseline gap-2">
            {p.discount_percent > 0 && <span className="text-2xl font-light text-rose-600">-{Math.round(p.discount_percent)}%</span>}
            <span className="text-3xl font-medium text-fg">{inr(p.price)}</span>
          </div>
          {p.mrp > p.price && (
            <div className="mt-1 text-xs text-muted">
              M.R.P.: <s>{inr(p.mrp)}</s> · Inclusive of all taxes
            </div>
          )}
          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-2xs text-muted">
            {[
              [Truck, p.price >= 1000 ? "Free delivery" : "Delivery ₹79"],
              [RotateCcw, p.returnable ? "Easy returns" : "Non-returnable"],
              [ShieldCheck, `${p.warranty_months}-month warranty`],
            ].map(([Icon, label]) => {
              const I = Icon as typeof Truck;
              return (
                <div key={label as string} className="flex flex-col items-center gap-1 rounded-xl bg-bg px-2 py-2.5">
                  <I className="size-5 text-amz-link" aria-hidden />
                  {label as string}
                </div>
              );
            })}
          </div>
          {p.description && (
            <>
              <h2 className="mt-5 text-sm font-semibold text-fg">About this item</h2>
              <p className="mt-1 text-sm leading-relaxed text-fg/90">{p.description}</p>
            </>
          )}
          <h2 className="mt-5 text-sm font-semibold text-fg">Product details</h2>
          <table className="mt-1 w-full text-sm">
            <tbody>
              {specs.map(([k, v]) => (
                <tr key={k} className="border-b border-line last:border-0">
                  <th className="w-36 py-1.5 pr-3 text-left align-top font-medium text-muted">{k}</th>
                  <td className="py-1.5 text-fg">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <aside className="h-fit rounded-xl border border-line p-4 lg:sticky lg:top-4">
          <div className="text-2xl font-medium text-fg">{inr(p.price)}</div>
          <p className={available ? "mt-2 text-sm font-semibold text-emerald-700" : "mt-2 text-sm font-semibold text-rose-700"}>
            {available ? (stock < 10 ? `Only ${stock} left in stock` : "In stock") : p.status === "active" ? "Out of stock" : pretty(p.status)}
          </p>
          {available && (
            <>
              <label className="mt-3 flex items-center gap-2 text-sm text-fg">
                Quantity
                <select value={qty} onChange={(e) => setQty(Number(e.target.value))} className="rounded-lg border border-line-strong bg-bg px-2 py-1">
                  {Array.from({ length: maxQty }, (_, i) => i + 1).map((n) => (
                    <option key={n}>{n}</option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={() => onAdd(p, qty)} className="brand-gradient mt-3 flex w-full items-center justify-center gap-1.5 rounded-full py-2 text-sm font-semibold text-[#0f1111]">
                <ShoppingCart className="size-4" aria-hidden /> Add to cart
              </button>
              <button type="button" onClick={() => onBuyNow(p, qty)} className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-full bg-amz-orange py-2 text-sm font-semibold text-[#0f1111] hover:brightness-105">
                <Zap className="size-4" aria-hidden /> Buy now
              </button>
            </>
          )}
          <button type="button" onClick={() => onAsk(p)} className="mt-3 flex w-full items-center justify-center gap-1.5 text-xs font-medium text-amz-link hover:underline">
            <MessageCircle className="size-3.5" aria-hidden /> Ask the assistant about this product
          </button>
        </aside>
      </section>

      {p.related.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-fg">Similar products</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {p.related.map((r) => (
              <button key={r.product_id} type="button" onClick={() => onOpen(r.product_id)} className="overflow-hidden rounded-2xl border border-line bg-surface text-left transition hover:shadow-card">
                {r.image_url && <img src={r.image_url} alt="" loading="lazy" className="aspect-[4/3] w-full object-cover" />}
                <div className="p-3">
                  <div className="line-clamp-2 text-sm font-medium text-fg">{r.product_name}</div>
                  <div className="mt-1 text-sm font-semibold text-fg">{inr(r.price)}</div>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
