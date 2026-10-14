import { Banknote, CheckCircle2, CreditCard, Loader2, Lock, MapPin, Smartphone, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { inr } from "../format";
import type { Customer, PlacedOrder, Product } from "../types";
import { cx } from "./ui/primitives";

type Line = { p: Product; qty: number };
type Method = "UPI" | "credit_card" | "cash_on_delivery";

export const GST_RATE = 0.18;
export function orderTotals(lines: Line[]) {
  const subtotal = lines.reduce((s, l) => s + l.p.price * l.qty, 0);
  const shipping = subtotal === 0 || subtotal >= 1000 ? 0 : 79;
  const tax = Math.round(subtotal * GST_RATE);
  return { subtotal, shipping, tax, total: subtotal + shipping + tax };
}

// Test mode: only the gateway's published test cards are accepted, so nobody types a real card here.
const TEST_CARDS = ["4111111111111111", "5555555555554444"];

const field = "mt-1 w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm text-fg focus:border-amz-orange focus:outline-none focus:ring-2 focus:ring-orange-500/20";

export function Checkout({
  customer,
  lines,
  onClose,
  onPlaced,
  onViewOrders,
}: {
  customer: Customer;
  lines: Line[];
  onClose: () => void;
  onPlaced: (o: PlacedOrder) => void;
  onViewOrders: () => void;
}) {
  const t = orderTotals(lines);
  const [step, setStep] = useState<"address" | "payment" | "processing" | "done">("address");
  const [ship, setShip] = useState({
    name: `${customer.first_name} ${customer.last_name}`.trim(),
    phone: String(customer.phone ?? "").replace(/\D/g, "").slice(-10),
    address: customer.address ?? "",
    city: customer.city ?? "",
    state: customer.state ?? "",
    pincode: String(customer.pincode ?? ""),
  });
  const [method, setMethod] = useState<Method>("UPI");
  const [upi, setUpi] = useState("");
  const [card, setCard] = useState({ number: "4111 1111 1111 1111", expiry: "12/30", cvv: "123" });
  const [error, setError] = useState<string | null>(null);
  const [placed, setPlaced] = useState<PlacedOrder | null>(null);

  useEffect(() => {
    api
      .address(customer.customer_id)
      .then((a) =>
        setShip((s) => ({
          ...s,
          phone: s.phone || a.phone.replace(/\D/g, "").slice(-10),
          address: s.address || a.address,
          city: s.city || a.city,
          state: s.state || a.state,
          pincode: s.pincode || a.pincode,
        })),
      )
      .catch(() => undefined);
  }, [customer.customer_id]);

  const addressOk = ship.name.trim() && /^\d{10}$/.test(ship.phone) && ship.address.trim() && ship.city.trim() && ship.state.trim() && /^\d{6}$/.test(ship.pincode);

  const pay = async () => {
    setError(null);
    let ref: string | undefined;
    if (method === "UPI") {
      if (!/^[\w.-]{2,}@[a-z]{2,}$/i.test(upi.trim())) return setError("Enter a valid UPI ID, e.g. name@okaxis");
      ref = upi.trim();
    } else if (method === "credit_card") {
      const num = card.number.replace(/\s/g, "");
      if (!TEST_CARDS.includes(num)) return setError("Test mode: use the test card 4111 1111 1111 1111. Never enter a real card here.");
      if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test(card.expiry) || !/^\d{3}$/.test(card.cvv)) return setError("Check the expiry (MM/YY) and CVV.");
      ref = `card ending ${num.slice(-4)}`;
    }
    setStep("processing");
    try {
      await new Promise((r) => setTimeout(r, 1400)); // simulated payment gateway
      const o = await api.placeOrder({
        customer_id: customer.customer_id,
        items: lines.map((l) => ({ product_id: l.p.product_id, quantity: l.qty })),
        shipping: ship,
        payment_method: method,
        payment_ref: ref,
      });
      setPlaced(o);
      setStep("done");
      onPlaced(o);
    } catch (e) {
      setError((e as Error).message.replace(/^.*"detail":"?([^"}]+).*$/, "$1"));
      setStep("payment");
    }
  };

  return (
    <div className="absolute inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <div
        role="dialog"
        aria-label="Checkout"
        className="my-6 w-full max-w-3xl overflow-hidden rounded-2xl bg-bg shadow-2xl"
      >
        <div className="flex items-center gap-3 border-b-2 border-amz-orange bg-navy px-5 py-3 text-white">
          <Lock className="size-4 text-amz-orange" aria-hidden />
          <div className="text-sm font-semibold">Secure checkout</div>
          <div className="ml-4 hidden gap-4 text-xs text-slate-300 sm:flex">
            {["address", "payment", "done"].map((s, i) => (
              <span key={s} className={cx(step === s || (s === "payment" && step === "processing") ? "font-semibold text-white" : "")}>
                {i + 1}. {s === "done" ? "Confirmation" : s[0].toUpperCase() + s.slice(1)}
              </span>
            ))}
          </div>
          {step !== "processing" && (
            <button type="button" aria-label="Close checkout" onClick={onClose} className="ml-auto rounded-lg p-1 hover:bg-white/15">
              <X className="size-4" />
            </button>
          )}
        </div>

        {step === "done" && placed ? (
          <div className="flex flex-col items-center p-8 text-center">
            <CheckCircle2 className="size-14 text-emerald-600" aria-hidden />
            <h2 className="mt-3 text-xl font-semibold text-fg">Order placed, thank you!</h2>
            <p className="mt-1 text-sm text-muted">
              Order <span className="font-mono font-semibold text-fg">{placed.order_id}</span> ·{" "}
              {placed.payment_status === "paid" ? `Paid ${inr(placed.total_amount)}` : `Pay ${inr(placed.total_amount)} on delivery`}
            </p>
            <p className="mt-1 text-sm text-muted">
              Arriving by <b className="text-fg">{new Date(placed.estimated_delivery_date).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" })}</b>
            </p>
            <div className="mt-5 flex gap-2">
              <button type="button" onClick={onViewOrders} className="brand-gradient rounded-full px-5 py-2 text-sm font-semibold text-[#0f1111]">View my orders</button>
              <button type="button" onClick={onClose} className="rounded-full border border-line-strong bg-surface px-5 py-2 text-sm font-medium text-fg">Continue shopping</button>
            </div>
          </div>
        ) : (
          <div className="grid gap-5 p-5 md:grid-cols-[minmax(0,1fr)_260px]">
            <div>
              {step === "address" ? (
                <section>
                  <h2 className="flex items-center gap-2 text-base font-semibold text-fg"><MapPin className="size-4" aria-hidden /> Delivery address</h2>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    {(
                      [
                        ["name", "Full name"],
                        ["phone", "Mobile number (10 digits)"],
                        ["address", "Flat, house no., street"],
                        ["city", "City"],
                        ["state", "State"],
                        ["pincode", "PIN code"],
                      ] as const
                    ).map(([k, label]) => (
                      <label key={k} className={cx("text-xs font-medium text-muted", k === "address" && "sm:col-span-2")}>
                        {label}
                        <input value={ship[k]} onChange={(e) => setShip({ ...ship, [k]: e.target.value })} className={field} inputMode={k === "phone" || k === "pincode" ? "numeric" : undefined} />
                      </label>
                    ))}
                  </div>
                  <button type="button" disabled={!addressOk} onClick={() => setStep("payment")} className="brand-gradient mt-4 rounded-full px-6 py-2 text-sm font-semibold text-[#0f1111] disabled:opacity-50">
                    Deliver to this address
                  </button>
                </section>
              ) : (
                <section>
                  <h2 className="text-base font-semibold text-fg">Payment method</h2>
                  <p className="mt-1 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-900 ring-1 ring-inset ring-amber-500/30">
                    Test mode: payments are simulated and no money is charged.
                  </p>
                  <div className="mt-3 space-y-2">
                    {(
                      [
                        ["UPI", Smartphone, "UPI", "Google Pay, PhonePe, Paytm or any UPI app"],
                        ["credit_card", CreditCard, "Credit / Debit card", "Visa, Mastercard, RuPay"],
                        ["cash_on_delivery", Banknote, "Cash on Delivery", "Pay when the order arrives"],
                      ] as const
                    ).map(([m, Icon, label, sub]) => (
                      <label key={m} className={cx("flex cursor-pointer gap-3 rounded-xl border bg-surface p-3", method === m ? "border-amz-orange ring-2 ring-orange-500/20" : "border-line")}>
                        <input type="radio" name="pay" checked={method === m} onChange={() => setMethod(m)} className="mt-1 accent-[#ff9900]" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 text-sm font-medium text-fg"><Icon className="size-4" aria-hidden /> {label}</div>
                          <div className="text-xs text-muted">{sub}</div>
                          {method === m && m === "UPI" && (
                            <input value={upi} onChange={(e) => setUpi(e.target.value)} placeholder="yourname@okaxis" className={field} aria-label="UPI ID" />
                          )}
                          {method === m && m === "credit_card" && (
                            <div className="mt-1 grid grid-cols-[1fr_80px_70px] gap-2">
                              <input value={card.number} onChange={(e) => setCard({ ...card, number: e.target.value })} className={field} aria-label="Test card number" />
                              <input value={card.expiry} onChange={(e) => setCard({ ...card, expiry: e.target.value })} className={field} aria-label="Expiry MM/YY" />
                              <input value={card.cvv} onChange={(e) => setCard({ ...card, cvv: e.target.value })} className={field} aria-label="CVV" />
                            </div>
                          )}
                        </div>
                      </label>
                    ))}
                  </div>
                  {error && <p className="mt-3 text-sm text-rose-700" role="alert">{error}</p>}
                  <div className="mt-4 flex items-center gap-3">
                    <button type="button" disabled={step === "processing"} onClick={pay} className="brand-gradient inline-flex items-center gap-2 rounded-full px-6 py-2 text-sm font-semibold text-[#0f1111] disabled:opacity-70">
                      {step === "processing" && <Loader2 className="size-4 animate-spin" aria-hidden />}
                      {step === "processing" ? "Processing payment…" : method === "cash_on_delivery" ? "Place order" : `Pay ${inr(t.total)}`}
                    </button>
                    {step !== "processing" && (
                      <button type="button" onClick={() => setStep("address")} className="text-sm text-amz-link hover:underline">Change address</button>
                    )}
                  </div>
                </section>
              )}
            </div>

            <aside className="h-fit rounded-xl border border-line bg-surface p-4 text-sm">
              <h3 className="font-semibold text-fg">Order summary</h3>
              <ul className="mt-2 space-y-1.5">
                {lines.map((l) => (
                  <li key={l.p.product_id} className="flex justify-between gap-2 text-xs">
                    <span className="line-clamp-2 text-muted">{l.p.product_name} × {l.qty}</span>
                    <span className="shrink-0 tabular-nums text-fg">{inr(l.p.price * l.qty)}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-3 space-y-1 border-t border-line pt-3 text-muted">
                <div className="flex justify-between"><span>Items</span><span className="tabular-nums text-fg">{inr(t.subtotal)}</span></div>
                <div className="flex justify-between"><span>Delivery</span><span className="tabular-nums text-fg">{t.shipping ? inr(t.shipping) : "FREE"}</span></div>
                <div className="flex justify-between"><span>GST (18%)</span><span className="tabular-nums text-fg">{inr(t.tax)}</span></div>
                <div className="flex justify-between border-t border-line pt-2 text-base font-semibold text-price"><span>Order total</span><span className="tabular-nums">{inr(t.total)}</span></div>
              </div>
              {step !== "address" && (
                <p className="mt-3 border-t border-line pt-3 text-xs text-muted">
                  Delivering to <b className="text-fg">{ship.name}</b>, {ship.address}, {ship.city} - {ship.pincode}
                </p>
              )}
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
