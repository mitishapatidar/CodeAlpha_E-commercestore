import { CheckCircle2, HelpCircle, ShieldAlert, Zap, type LucideIcon } from "lucide-react";
import type { Decision } from "./types";

const inrFmt = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
export const inr = (n: number | null | undefined) => (n == null ? "—" : inrFmt.format(n));

export function humanDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function timeOf(ms: number): string {
  return new Date(ms).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

export const initials = (first?: string, last?: string) => `${first?.[0] ?? ""}${last?.[0] ?? ""}`.toUpperCase() || "?";

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);

export interface DecisionStyle {
  label: string;
  icon: LucideIcon;
  text: string;
  bg: string;
  ring: string;
  dot: string;
  hint: string;
}

export const DECISION: Record<Decision, DecisionStyle> = {
  ANSWER: { label: "Answer", icon: CheckCircle2, text: "text-emerald-700", bg: "bg-emerald-500/10", ring: "ring-emerald-500/30", dot: "bg-emerald-400", hint: "Verified information, no action needed" },
  ASK: { label: "Ask", icon: HelpCircle, text: "text-sky-700", bg: "bg-sky-500/10", ring: "ring-sky-500/30", dot: "bg-sky-400", hint: "Missing or ambiguous information" },
  ACT: { label: "Act", icon: Zap, text: "text-amber-800", bg: "bg-amber-500/10", ring: "ring-amber-500/30", dot: "bg-amber-400", hint: "Eligible under policy, action taken" },
  ESCALATE: { label: "Escalate", icon: ShieldAlert, text: "text-rose-700", bg: "bg-rose-500/10", ring: "ring-rose-500/30", dot: "bg-rose-400", hint: "Beyond agent authority, handed to a human" },
};

/** Colour for order/payment/delivery status chips. */
export function statusTone(status: string): string {
  const s = status.toLowerCase();
  if (["delivered", "paid", "processed", "active", "none"].includes(s)) return "text-emerald-700 bg-emerald-500/10 ring-emerald-500/20";
  if (["shipped", "out_for_delivery", "in_transit", "confirmed", "placed", "processing"].includes(s)) return "text-sky-700 bg-sky-500/10 ring-sky-500/20";
  if (["pending", "partial", "partially_returned", "partially_refunded", "inactive"].includes(s)) return "text-amber-800 bg-amber-500/10 ring-amber-500/20";
  if (["cancelled", "returned", "refunded"].includes(s)) return "text-slate-700 bg-slate-500/10 ring-slate-500/20";
  if (["lost", "failed", "rejected", "suspended"].includes(s)) return "text-rose-700 bg-rose-500/10 ring-rose-500/20";
  return "text-slate-700 bg-slate-500/10 ring-slate-500/20";
}

export const TIER_TONE: Record<string, string> = {
  platinum: "text-violet-700 bg-violet-500/15 ring-violet-400/30",
  gold: "text-amber-800 bg-amber-500/15 ring-amber-400/30",
  silver: "text-slate-700 bg-slate-400/15 ring-slate-300/30",
  bronze: "text-orange-800 bg-orange-700/20 ring-orange-500/30",
};

export const FLAG_LABEL: Record<string, string> = {
  injection: "Prompt injection",
  legal_threat: "Legal threat",
  safety: "Safety incident",
  self_harm: "Self-harm",
  threat: "Threat",
  abuse: "Abusive language",
  refund_to_other_account: "Refund redirect",
  original_instrument_unavailable: "Instrument unavailable",
  human_request: "Human requested",
  chargeback: "Chargeback",
  authority_claim: "Authority claim",
};

export const WRITE_TOOLS = new Set(["create_refund", "create_return", "create_support_ticket", "escalate_to_human"]);

export const pretty = (s: string) => s.replace(/_/g, " ");
