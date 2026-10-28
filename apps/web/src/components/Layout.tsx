import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useBotStatus, useSystemStatus } from "../lib/queries";
import { Badge } from "./ui";
import { post } from "../lib/api";

const groups: { title: string; links: { to: string; label: string }[] }[] = [
  { title: "Overview", links: [{ to: "/", label: "Market Overview" }] },
  {
    title: "Analysis Engine",
    links: [
      { to: "/scanner", label: "Trenches & Pulse Radar" },
      { to: "/tokens", label: "Token Explorer" },
      { to: "/signals", label: "Signal Center" },
      { to: "/watchlist", label: "Watchlist" },
      { to: "/analysis", label: "Analysis History" },
    ],
  },
  {
    title: "Trading Bot",
    links: [
      { to: "/bot", label: "Bot Control Center" },
      { to: "/orders", label: "Order & Execution" },
      { to: "/risk", label: "Risk Management" },
    ],
  },
  {
    title: "Portfolio",
    links: [
      { to: "/portfolio", label: "Portfolio Overview" },
      { to: "/performance", label: "Performance & Research" },
      { to: "/wallet", label: "Wallets & Sweep" },
      { to: "/alerts", label: "Alerts & Journal" },
    ],
  },
  {
    title: "AI & System",
    links: [
      { to: "/ai", label: "AI & Agent Center" },
      { to: "/providers", label: "Providers" },
      { to: "/settings", label: "Settings & Health" },
    ],
  },
];

export default function Layout() {
  const sys = useSystemStatus();
  const bot = useBotStatus();
  const [pw, setPw] = useState("");
  const [loginMsg, setLoginMsg] = useState<string | null>(null);
  const nav = useNavigate();
  const authed = typeof sessionStorage !== "undefined" && Boolean(sessionStorage.getItem("sofia_token"));
  const authDisabled = sys.data?.auth_disabled ?? true;

  const doLogin = async () => {
    try {
      const r = await post<{ token: string }>("/api/v1/auth/login", { password: pw });
      sessionStorage.setItem("sofia_token", r.token);
      setLoginMsg(null);
      setPw("");
      nav(0);
    } catch {
      setLoginMsg("Password salah.");
    }
  };

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950 p-4 md:flex">
        <Link to="/" className="mb-1 flex items-center gap-2 px-2 text-lg font-bold text-emerald-300">
          <span>◈</span> Next Gent Sofia Trade v1
        </Link>
        <p className="mb-4 px-2 text-xs text-zinc-500">Solana Meme Coin Intelligence · v1</p>
        <div className="mb-4 flex flex-wrap gap-1.5 px-2">
          <Badge level={bot.data?.status === "RUNNING" ? "ok" : "mute"}>{bot.data ? `BOT ${bot.data.status}` : "BOT …"}</Badge>
          <Badge level="info">{bot.data ? bot.data.mode : "…"}</Badge>
          <Badge level="bad">LIVE OFF</Badge>
        </div>
        <nav className="flex-1 space-y-4 overflow-y-auto">
          {groups.map((g) => (
            <div key={g.title}>
              <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">{g.title}</p>
              {g.links.map((l) => (
                <NavLink
                  key={l.to}
                  to={l.to}
                  end={l.to === "/"}
                  className={({ isActive }) =>
                    `block rounded-lg px-3 py-1.5 text-sm ${isActive ? "bg-emerald-950 text-emerald-200" : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"}`
                  }
                >
                  {l.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        {!authDisabled && !authed && (
          <div className="mt-4 rounded-lg border border-zinc-800 p-3">
            <p className="mb-2 text-xs text-zinc-400">Login operator</p>
            <input
              type="password"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              placeholder="Admin password"
              className="mb-2 w-full rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
            />
            <button onClick={doLogin} className="w-full rounded-md bg-emerald-600 px-2 py-1.5 text-sm font-medium hover:bg-emerald-500">
              Login
            </button>
            {loginMsg && <p className="mt-1 text-xs text-red-400">{loginMsg}</p>}
          </div>
        )}
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-zinc-800 bg-zinc-950/80 px-4 py-2.5 backdrop-blur">
          <p className="text-xs text-zinc-400">
            Mode rilis: <span className="font-semibold text-emerald-300">Analysis-only + PAPER</span> · LIVE dinonaktifkan · Engine{" "}
            {sys.data?.engine_version ?? "…"}
          </p>
        </header>
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
