import { WifiOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_URL, api } from "./api";
import { AgentBrain } from "./components/AgentBrain";
import { Chat } from "./components/Chat";
import { Sidebar } from "./components/Sidebar";
import { Storefront } from "./components/Storefront";
import { TopBar, type SessionStats } from "./components/TopBar";
import { Button, Drawer, Toasts, type Toast } from "./components/ui/primitives";
import { uid } from "./format";
import { Login } from "./pages/Login";
import { OwnerReview } from "./pages/OwnerDashboard";
import type { ChatMessage, Customer, Health, Order, Scenario, Session } from "./types";

const AUTH_KEY = "novamart.session";
function loadAuth(): Session | null {
  try {
    const raw = sessionStorage.getItem(AUTH_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenariosLoading, setScenariosLoading] = useState(true);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [view, setView] = useState<"review" | "console">("review");
  const [auth, setAuth] = useState<Session | null>(loadAuth);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [brainOpen, setBrainOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const sessionRef = useRef<string>(uid());

  // ---------------------------------------------------------------- toasts
  const dismiss = useCallback((id: string) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const notify = useCallback((text: string, kind: Toast["kind"] = "error", action?: Toast["action"]) => {
    setToasts((t) => [...t.slice(-3), { id: uid(), kind, text, action }]);
  }, []);
  const onError = useCallback((msg: string, retry?: () => void) => notify(msg, "error", retry ? { label: "Retry", run: retry } : undefined), [notify]);

  // ---------------------------------------------------------------- health + scenarios
  const checkHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
      setOnline(true);
      return true;
    } catch {
      setOnline(false);
      return false;
    }
  }, []);

  const loadScenarios = useCallback(async () => {
    setScenariosLoading(true);
    try {
      setScenarios(await api.scenarios());
    } catch (e) {
      onError(`Could not load demo scenarios: ${(e as Error).message}`, loadScenarios);
    } finally {
      setScenariosLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    checkHealth().then((ok) => (ok ? loadScenarios() : setScenariosLoading(false)));
    const h = setInterval(checkHealth, 15000);
    return () => clearInterval(h);
  }, [checkHealth, loadScenarios]);

  const retryConnection = useCallback(async () => {
    if (await checkHealth()) {
      loadScenarios();
      notify("Backend is back online", "success");
    } else notify(`Still can't reach ${API_URL}`);
  }, [checkHealth, loadScenarios, notify]);

  // ---------------------------------------------------------------- session
  const newSession = useCallback(async (silent = false) => {
    const old = sessionRef.current;
    sessionRef.current = uid();
    setMessages([]);
    setSelectedId(null);
    try {
      await api.reset(old);
    } catch {
      if (!silent) notify("Could not reset the session on the server (a new local session was started).");
    }
  }, [notify]);

  const selectCustomer = useCallback(
    async (c: Customer) => {
      setCustomer(c);
      setSidebarOpen(false);
      await newSession(true);
      setOrdersLoading(true);
      try {
        setOrders(await api.orders(c.customer_id));
      } catch (e) {
        setOrders([]);
        onError(`Could not load orders: ${(e as Error).message}`, () => selectCustomer(c));
      } finally {
        setOrdersLoading(false);
      }
    },
    [newSession, onError],
  );

  // ---------------------------------------------------------------- chat
  const send = useCallback(
    async (text: string, scenario?: Scenario, cust?: Customer) => {
      const who = cust ?? customer;
      if (!who) return;
      const customerMsg: ChatMessage = { id: uid(), role: "customer", text, at: Date.now(), scenario };
      setMessages((m) => [...m, customerMsg]);
      setSending(true);
      try {
        const r = await api.chat({ customer_id: who.customer_id, message: text, session_id: sessionRef.current });
        const agentMsg: ChatMessage = { id: uid(), role: "agent", text: r.reply, at: Date.now(), response: r, scenario };
        setMessages((m) => [...m, agentMsg]);
        setSelectedId(agentMsg.id);
        if (r.tool_calls.some((t) => t.name.startsWith("create_"))) {
          api.orders(who.customer_id).then(setOrders).catch(() => undefined);
        }
      } catch (e) {
        setMessages((m) => m.filter((x) => x.id !== customerMsg.id));
        onError(`Message failed: ${(e as Error).message}`, () => send(text, scenario, who));
        checkHealth();
      } finally {
        setSending(false);
      }
    },
    [customer, onError, checkHealth],
  );

  const runScenario = useCallback(
    async (s: Scenario) => {
      setSidebarOpen(false);
      try {
        const found = (await api.customers(s.customer_id, 1)).find((c) => c.customer_id === s.customer_id);
        if (!found) throw new Error(`customer ${s.customer_id} not found`);
        await selectCustomer(found);
        await send(s.message, s, found);
      } catch (e) {
        onError(`Could not run scenario: ${(e as Error).message}`, () => runScenario(s));
      }
    },
    [selectCustomer, send, onError],
  );

  const resetDemo = useCallback(async () => {
    try {
      await api.resetDemo();
      await newSession(true);
      if (customer) api.orders(customer.customer_id).then(setOrders).catch(() => undefined);
      notify("Demo data reset: agent-created refunds and tickets cleared", "success");
    } catch (e) {
      onError(`Reset failed: ${(e as Error).message}`, resetDemo);
    }
  }, [customer, newSession, notify, onError]);

  // ---------------------------------------------------------------- auth
  const login = useCallback(
    (sess: Session) => {
      setAuth(sess);
      try {
        sessionStorage.setItem(AUTH_KEY, JSON.stringify(sess));
      } catch {
        /* storage unavailable: session lasts until reload */
      }
      if (sess.role === "customer") selectCustomer(sess.customer);
      else {
        setView("review");
        setCustomer(null);
        newSession(true);
      }
    },
    [selectCustomer, newSession],
  );

  const logout = useCallback(() => {
    newSession(true);
    setCustomer(null);
    setOrders([]);
    setAuth(null);
    try {
      sessionStorage.removeItem(AUTH_KEY);
    } catch {
      /* ignore */
    }
  }, [newSession]);

  // restore a customer session after reload
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current || !auth) return;
    restored.current = true;
    if (auth.role === "customer") selectCustomer(auth.customer);
  }, [auth, selectCustomer]);

  // ---------------------------------------------------------------- derived
  const stats: SessionStats = useMemo(() => {
    const rs = messages.flatMap((m) => (m.response ? [m.response] : []));
    return {
      messages: messages.length,
      tokens: rs.reduce((a, r) => a + r.tokens.input + r.tokens.output, 0),
      llmCalls: rs.reduce((a, r) => a + r.tokens.llm_calls, 0),
      avgLatency: rs.length ? Math.round(rs.reduce((a, r) => a + r.latency_ms, 0) / rs.length) : 0,
    };
  }, [messages]);

  const selected = useMemo(
    () => messages.find((m) => m.id === selectedId) ?? [...messages].reverse().find((m) => m.role === "agent") ?? null,
    [messages, selectedId],
  );

  const sidebar = (
    <Sidebar
      customer={customer}
      onSelectCustomer={selectCustomer}
      orders={orders}
      ordersLoading={ordersLoading}
      scenarios={scenarios}
      scenariosLoading={scenariosLoading}
      runScenario={runScenario}
      resetDemo={resetDemo}
      busy={sending}
      onError={onError}
    />
  );

  const offlineBanner = online === false && (
    <div className="flex shrink-0 items-center gap-3 border-b border-rose-500/30 bg-rose-500/10 px-4 py-2 text-sm text-rose-700" role="alert">
      <WifiOff className="size-4 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1 truncate">
        Backend offline. Can't reach <span className="font-mono">{API_URL}</span>. Start it with{" "}
        <span className="font-mono">uvicorn app.main:app --port 8000</span>.
      </span>
      <Button variant="danger" onClick={retryConnection}>
        Retry
      </Button>
    </div>
  );

  // ---------------------------------------------------------------- login
  if (!auth) {
    return (
      <div className="flex h-full flex-col overflow-y-auto">
        {offlineBanner}
        <Login onLogin={login} />
        <Toasts items={toasts} dismiss={dismiss} />
      </div>
    );
  }

  // ---------------------------------------------------------------- customer dashboard
  if (auth.role === "customer") {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        {offlineBanner}
        <Storefront
          customer={customer ?? auth.customer}
          onLogout={logout}
          orders={orders}
          ordersLoading={ordersLoading}
          messages={messages}
          sending={sending}
          onSend={(t) => send(t, undefined, customer ?? auth.customer)}
          onNewSession={() => newSession()}
          onError={onError}
          onOrderPlaced={() => {
            const who = customer ?? auth.customer;
            api.orders(who.customer_id).then(setOrders).catch(() => undefined);
          }}
        />
        <Toasts items={toasts} dismiss={dismiss} />
      </div>
    );
  }

  // ---------------------------------------------------------------- owner dashboard
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <TopBar
        health={health}
        online={online}
        retry={retryConnection}
        stats={stats}
        view={view}
        setView={setView}
        openSidebar={() => setSidebarOpen(true)}
        openBrain={() => setBrainOpen(true)}
        onLogout={logout}
      />
      {offlineBanner}

      {view === "review" ? (
        <OwnerReview onError={onError} />
      ) : (
        <div className="flex min-h-0 flex-1">
          <aside className="hidden w-[300px] shrink-0 border-r border-line bg-bg sm:flex sm:flex-col" aria-label="Customers and scenarios">
            {sidebar}
          </aside>
          <main className="min-w-0 flex-1 bg-[radial-gradient(1200px_500px_at_50%_-200px,rgba(249,115,22,0.06),transparent)]">
            <Chat
              customer={customer}
              messages={messages}
              sending={sending}
              selectedId={selected?.id ?? null}
              onSelect={(id) => {
                setSelectedId(id);
                if (window.matchMedia("(max-width: 1023px)").matches) setBrainOpen(true);
              }}
              onSend={(t) => send(t)}
              onNewSession={() => newSession()}
              view="console"
            />
          </main>
          <aside className="hidden w-[380px] shrink-0 border-l border-line bg-bg lg:flex lg:flex-col" aria-label="Agent Brain">
            <AgentBrain message={selected} />
          </aside>
        </div>
      )}

      <Drawer open={sidebarOpen} side="left" onClose={() => setSidebarOpen(false)} label="Customers and scenarios">
        {sidebar}
      </Drawer>
      <Drawer open={brainOpen} side="right" onClose={() => setBrainOpen(false)} label="Agent Brain">
        <AgentBrain message={selected} onClose={() => setBrainOpen(false)} />
      </Drawer>
      <Toasts items={toasts} dismiss={dismiss} />
    </div>
  );
}
