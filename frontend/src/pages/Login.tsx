import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, BadgeCheck, LayoutDashboard, Loader2, Package, RotateCcw, ShieldCheck, ShoppingBag, Store, Truck, UserRound } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/api";
import { Avatar } from "@/components/Sidebar";
import { cn } from "@/lib/utils";
import type { Customer, Scenario, Session } from "@/types";

function generateOtp(): string {
  return String(Math.floor(100000 + Math.random() * 900000));
}

function maskEmail(email: string) {
  const [u, d] = email.split("@");
  return `${u.slice(0, 2)}${"•".repeat(Math.max(2, u.length - 2))}@${d}`;
}

export function Login({ onLogin }: { onLogin: (s: Session) => void }) {
  const [role, setRole] = useState<"customer" | "owner">("customer");
  const [step, setStep] = useState<"id" | "otp">("id");
  const [identifier, setIdentifier] = useState("");
  const [found, setFound] = useState<Customer | null>(null);
  const [activeOtp, setActiveOtp] = useState<string>(() => generateOtp());
  const [otp, setOtp] = useState<string[]>(Array(6).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [demoAccounts, setDemoAccounts] = useState<Customer[]>([]);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

  // a few real customers from the demo scenarios, for one-click demo login
  useEffect(() => {
    api
      .scenarios()
      .then(async (sc: Scenario[]) => {
        const ids = [...new Set(sc.map((s) => s.customer_id))].slice(0, 4);
        const res = await Promise.all(ids.map((id) => api.customers(id, 1).then((r) => r.find((c) => c.customer_id === id))));
        setDemoAccounts(res.filter((c): c is Customer => !!c));
      })
      .catch(() => undefined);
  }, []);

  const lookup = async (e?: FormEvent) => {
    e?.preventDefault();
    const q = identifier.trim();
    if (!q) return setError("Please enter your email address or customer ID.");
    setLoading(true);
    setError(null);
    try {
      const res = await api.customers(q, 5);
      const c = res.find((x) => x.email.toLowerCase() === q.toLowerCase() || x.customer_id.toLowerCase() === q.toLowerCase());
      if (!c) {
        setError("We couldn't find an account with that email or customer ID.");
        return;
      }
      setFound(c);
      const freshOtp = generateOtp();
      setActiveOtp(freshOtp);
      setStep("otp");
      setOtp(Array(6).fill(""));
    } catch (err) {
      setError(`Can't reach the server: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const resendOtp = () => {
    const freshOtp = generateOtp();
    setActiveOtp(freshOtp);
    setOtp(Array(6).fill(""));
    setError(null);
    setTimeout(() => otpRefs.current[0]?.focus(), 50);
  };

  const finish = (code: string) => {
    if (code.length < 6) {
      setError("Please enter all 6 digits of the OTP.");
      otpRefs.current[Math.min(code.length, 5)]?.focus();
      return;
    }
    if (code !== activeOtp) {
      setError(`That OTP is incorrect. Please enter code: ${activeOtp}.`);
      setOtp(Array(6).fill(""));
      setTimeout(() => otpRefs.current[0]?.focus(), 0);
      return;
    }
    if (found) onLogin({ role: "customer", customer: found });
  };

  const verify = (e?: FormEvent) => {
    e?.preventDefault();
    finish(otp.join(""));
  };

  /** Type, paste or autofill: digits are spread across the boxes; the form submits itself once all 6 are in. */
  const setDigit = (i: number, v: string) => {
    const digits = v.replace(/\D/g, "");
    setError(null);
    if (!digits) {
      setOtp((o) => o.map((x, j) => (j === i ? "" : x)));
      return;
    }
    const next = [...otp];
    digits.split("").slice(0, 6 - i).forEach((d, k) => (next[i + k] = d));
    setOtp(next);
    const filled = next.findIndex((x) => !x);
    if (filled === -1) finish(next.join(""));
    else otpRefs.current[filled]?.focus();
  };

  const useDemoOtp = () => {
    setOtp(activeOtp.split(""));
    finish(activeOtp);
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-[radial-gradient(1000px_600px_at_20%_-10%,rgba(239,68,68,0.12),transparent),radial-gradient(900px_600px_at_100%_110%,rgba(249,115,22,0.10),transparent)] p-4 sm:p-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
        className="grid w-full max-w-4xl overflow-hidden rounded-3xl border border-line bg-surface shadow-2xl md:grid-cols-[1fr_1.15fr]"
      >
        {/* brand panel */}
        <div className="relative hidden flex-col justify-between bg-navy-2 p-8 text-white md:flex">
          <div>
            <div className="flex items-center gap-2">
              <span className="grid size-9 place-items-center rounded-xl bg-white/15">
                <ShoppingBag className="size-5" aria-hidden />
              </span>
              <span className="text-xl font-bold tracking-tight">NovaMart</span>
            </div>
            <h1 className="mt-10 text-3xl font-bold leading-tight">{role === "customer" ? "Login" : "Owner sign-in"}</h1>
            <p className="mt-3 text-sm leading-relaxed text-white/85">
              {role === "customer"
                ? "Get access to your Orders, Returns, Refunds and 24×7 verified support."
                : "Review every decision the AI agent made: refunds, escalations and the full reasoning trace."}
            </p>
          </div>
          <ul className="space-y-3 text-sm text-white/90">
            {(role === "customer"
              ? [
                  [Truck, "Track every order in real time"],
                  [RotateCcw, "Easy returns & refunds, checked against policy"],
                  [ShieldCheck, "Support that verifies before it acts"],
                ]
              : [
                  [LayoutDashboard, "Live KPIs: answers, asks, actions, escalations"],
                  [BadgeCheck, "Audit trail for every refund and ticket"],
                  [ShieldCheck, "Injection, legal and safety flags"],
                ]
            ).map(([Icon, t]) => {
              const I = Icon as typeof Truck;
              return (
                <li key={t as string} className="flex items-center gap-2.5">
                  <span className="grid size-7 place-items-center rounded-lg bg-white/15">
                    <I className="size-4" aria-hidden />
                  </span>
                  {t as string}
                </li>
              );
            })}
          </ul>
          <Package className="pointer-events-none absolute -bottom-6 -right-6 size-40 text-white/10" strokeWidth={1} aria-hidden />
        </div>

        {/* form panel */}
        <div className="p-6 sm:p-10">
          <div className="mb-8 flex rounded-xl bg-black/[0.04] p-1 ring-1 ring-inset ring-black/10" role="tablist" aria-label="Sign in as">
            {(
              [
                ["customer", UserRound, "Customer"],
                ["owner", Store, "Owner / Staff"],
              ] as const
            ).map(([k, Icon, label]) => (
              <button
                key={k}
                type="button"
                role="tab"
                aria-selected={role === k}
                onClick={() => {
                  setRole(k);
                  setError(null);
                  setStep("id");
                }}
                className={cn(
                  "flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition",
                  role === k ? "bg-elevated text-fg shadow-card ring-1 ring-inset ring-black/10" : "text-muted hover:text-fg",
                )}
              >
                <Icon className="size-4" aria-hidden /> {label}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            {role === "owner" ? (
              <motion.div key="owner" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.18 }}>
                <h2 className="text-xl font-semibold text-fg">Owner dashboard</h2>
                <p className="mt-1 text-sm text-muted">Monitor and review the AI support agent's decisions.</p>
                <button
                  type="button"
                  onClick={() => onLogin({ role: "owner" })}
                  className="brand-gradient mt-8 w-full rounded-xl py-3 text-sm font-semibold text-[#0f1111] shadow-[0_10px_30px_-12px_rgba(255,153,0,0.45)] transition hover:brightness-110"
                >
                  Continue to owner dashboard
                </button>
                <p className="mt-4 rounded-xl border border-dashed border-line p-3 text-2xs leading-relaxed text-faint">
                  Demo mode: no real authentication. In production this would sit behind staff SSO.
                </p>
              </motion.div>
            ) : step === "id" ? (
              <motion.form key="id" onSubmit={lookup} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.18 }}>
                <h2 className="text-xl font-semibold text-fg">Welcome back</h2>
                <p className="mt-1 text-sm text-muted">Sign in with your registered email or customer ID.</p>
                <label htmlFor="login-id" className="mt-8 block text-xs font-medium text-muted">
                  Email or customer ID
                </label>
                <input
                  id="login-id"
                  autoFocus
                  autoComplete="username"
                  value={identifier}
                  onChange={(e) => {
                    setIdentifier(e.target.value);
                    setError(null);
                  }}
                  placeholder="e.g. ravi.ali@webmail.example"
                  className="mt-1.5 w-full rounded-xl border border-line bg-elevated px-4 py-3 text-sm text-fg placeholder:text-faint focus:border-amz-orange focus:outline-none focus:ring-2 focus:ring-orange-500/20"
                />
                {error && <p className="mt-2 text-xs text-rose-700" role="alert">{error}</p>}
                <button
                  type="submit"
                  disabled={loading}
                  className="brand-gradient mt-6 flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold text-[#0f1111] shadow-[0_10px_30px_-12px_rgba(255,153,0,0.45)] transition hover:brightness-110 disabled:opacity-60"
                >
                  {loading && <Loader2 className="size-4 animate-spin" aria-hidden />} Continue
                </button>
                <p className="mt-3 text-center text-2xs text-faint">By continuing, you agree to NovaMart's Terms of Use and Privacy Policy.</p>

                {demoAccounts.length > 0 && (
                  <div className="mt-8">
                    <div className="mb-2 flex items-center gap-2 text-2xs font-semibold uppercase tracking-[0.08em] text-faint">
                      <span className="h-px flex-1 bg-line" /> Demo accounts <span className="h-px flex-1 bg-line" />
                    </div>
                    <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                      {demoAccounts.map((c) => (
                        <button
                          key={c.customer_id}
                          type="button"
                          onClick={() => {
                            setIdentifier(c.email);
                            setError(null);
                          }}
                          className="flex items-center gap-2 rounded-xl border border-line px-2.5 py-2 text-left transition hover:border-orange-500/40 hover:bg-black/[0.03]"
                        >
                          <Avatar c={c} small />
                          <span className="min-w-0">
                            <span className="block truncate text-xs font-medium text-fg">{c.first_name} {c.last_name}</span>
                            <span className="block truncate text-2xs text-faint">{c.email}</span>
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </motion.form>
            ) : (
              <motion.form key="otp" onSubmit={verify} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.18 }}>
                <button type="button" onClick={() => setStep("id")} className="mb-6 inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
                  <ArrowLeft className="size-3.5" aria-hidden /> Change account
                </button>
                <h2 className="text-xl font-semibold text-fg">Verify it's you</h2>
                <p className="mt-1 text-sm text-muted">
                  Enter the 6-digit OTP sent to <span className="text-fg">{found && maskEmail(found.email)}</span>
                </p>
                <div
                  className="mt-8 flex justify-between gap-2"
                  role="group"
                  aria-label="One-time password"
                  onClick={(e) => {
                    if (e.target === e.currentTarget) otpRefs.current[Math.max(0, otp.findIndex((x) => !x))]?.focus();
                  }}
                >
                  {otp.map((d, i) => (
                    <input
                      key={i}
                      ref={(el) => {
                        otpRefs.current[i] = el;
                      }}
                      value={d}
                      autoFocus={i === 0}
                      inputMode="numeric"
                      autoComplete={i === 0 ? "one-time-code" : "off"}
                      aria-label={`Digit ${i + 1}`}
                      onChange={(e) => setDigit(i, e.target.value)}
                      onKeyDown={(e) => e.key === "Backspace" && !otp[i] && i > 0 && otpRefs.current[i - 1]?.focus()}
                      onPaste={(e) => {
                        e.preventDefault();
                        setDigit(i, e.clipboardData.getData("text"));
                      }}
                      onFocus={(e) => e.target.select()}
                      className="size-12 rounded-xl border border-line-strong bg-elevated text-center text-lg font-semibold text-fg caret-orange-400 focus:border-amz-orange focus:outline-none focus:ring-2 focus:ring-orange-500/20"
                    />
                  ))}
                </div>
                {error && <p className="mt-3 text-xs text-rose-700" role="alert">{error}</p>}
                <button
                  type="submit"
                  className="brand-gradient mt-6 w-full rounded-xl py-3 text-sm font-semibold text-[#0f1111] shadow-[0_10px_30px_-12px_rgba(255,153,0,0.45)] transition hover:brightness-110"
                >
                  Verify & sign in
                </button>
                <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-dashed border-line px-3 py-2.5 text-2xs text-faint">
                  <span>
                    Current OTP: <span className="font-mono text-xs font-bold text-amber-500">{activeOtp}</span>
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={resendOtp}
                      className="shrink-0 rounded-lg border border-line bg-surface px-2.5 py-1 font-medium text-muted transition hover:bg-black/5 hover:text-fg"
                      title="Generate new random OTP"
                    >
                      New OTP
                    </button>
                    <button
                      type="button"
                      onClick={useDemoOtp}
                      className="shrink-0 rounded-lg bg-orange-500/10 px-2.5 py-1 font-semibold text-orange-600 ring-1 ring-inset ring-orange-500/25 transition hover:bg-orange-500/20"
                    >
                      Autofill OTP
                    </button>
                  </div>
                </div>
              </motion.form>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}
