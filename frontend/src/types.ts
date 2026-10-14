// Types mirror API_CONTRACT.md (+ the backend's additive fields, all optional here).

export type Decision = "ANSWER" | "ASK" | "ACT" | "ESCALATE";

export interface Health {
  status: string;
  policy_versions: string[];
  model: string;
  llm_enabled?: boolean;
}

export interface Customer {
  customer_id: string;
  first_name: string;
  last_name: string;
  email: string;
  city: string | null;
  loyalty_tier: string;
  customer_segment: string;
  account_status: string;
  phone?: string | null;
  address?: string | null;
  state?: string | null;
  pincode?: string | number | null;
}

export interface PlacedOrder {
  order_id: string;
  total_amount: number;
  payment_status: string;
  order_status: string;
  estimated_delivery_date: string;
}

export interface Order {
  order_id: string;
  order_date: string;
  total_amount: number;
  order_status: string;
  delivery_status: string;
  payment_status: string;
  refund_status: string;
  items?: string[];
}

export interface Scenario {
  id: string;
  title: string;
  category: string;
  customer_id: string;
  message: string;
  expected_decision: Decision;
}

export interface IntentView {
  type: string;
  order_id: string | null;
  decision?: Decision;
  reason: string | null;
  explanation?: string;
  refund_amount?: number;
  policy_version?: string;
  escalation_team?: string;
  amount_claimed?: number;
  product_hint?: string;
  [key: string]: unknown;
}

export interface ToolCall {
  name: string;
  params: Record<string, unknown>;
  ok: boolean;
  result_summary: string;
  result?: Record<string, unknown>;
}

export interface ChatResponse {
  reply: string;
  decision: Decision;
  intents: IntentView[];
  tool_calls: ToolCall[];
  refund_amount: number | null;
  escalate: boolean;
  ticket_id: string | null;
  policy_version: string | null;
  flags: string[];
  reasoning: string[];
  tokens: { input: number; output: number; llm_calls: number };
  latency_ms: number;
  language?: string;
  parser?: string;
  reply_source?: string;
}

export interface ChatMessage {
  id: string;
  role: "customer" | "agent";
  text: string;
  at: number;
  response?: ChatResponse;
  scenario?: Scenario;
  error?: boolean;
}

export interface Product {
  product_id: string;
  product_name: string;
  brand: string;
  category: string;
  subcategory: string;
  price: number;
  mrp: number;
  discount_percent: number;
  rating: number | null;
  review_count: number;
  warranty_months: number;
  returnable: boolean;
  status: string;
  color: string;
  image_url?: string;
}

export interface ProductDetail extends Product {
  description: string;
  stock_quantity: number | null;
  replacement_available: boolean | null;
  specs: Record<string, string>;
  related: Product[];
}

export interface Category {
  category: string;
  count: number;
}

export interface CustomerTicket {
  id: string;
  source: "agent" | "history";
  type: string;
  order_id: string | null;
  category: string;
  summary: string;
  status: string | null;
  team: string | null;
  amount: number | null;
  created_at: string | null;
}

export interface TurnRecord {
  id: string;
  at: string;
  customer_id: string | null;
  message: string;
  response: ChatResponse;
}

export interface ActionRecord {
  id: string;
  type: "refund" | "return" | "ticket" | "escalation";
  created_at: string;
  customer_id?: string;
  order_id?: string | null;
  amount?: number;
  reason?: string;
  team?: string;
  priority?: string;
  sla?: string;
  category?: string;
  summary?: string;
  status?: string;
  resolution?: string;
  [key: string]: unknown;
}

export type Session =
  | { role: "customer"; customer: Customer }
  | { role: "owner" };
