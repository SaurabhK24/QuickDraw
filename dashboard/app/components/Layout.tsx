import { NavLink } from "@remix-run/react";
import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Play,
  GitBranch,
  Package,
  MessageSquare,
  Zap,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/", icon: LayoutDashboard, label: "Overview" },
  { to: "/chat", icon: MessageSquare, label: "Swarm Chat" },
  { to: "/run", icon: Play, label: "New Run" },
  { to: "/workflows", icon: GitBranch, label: "Workflows" },
  { to: "/packs", icon: Package, label: "Packs" },
] as const;

function getApiBase(): string {
  if (typeof window === "undefined") return "http://localhost:8080";
  const envBase = (window as any).ENV?.API_BASE;
  if (envBase) return envBase;
  return `${window.location.protocol}//${window.location.hostname}:8080`;
}

export function Layout({ children }: { children: React.ReactNode }) {
  const [healthOk, setHealthOk] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      fetch(`${getApiBase()}/health`)
        .then((r) => { if (!cancelled) setHealthOk(r.ok); })
        .catch(() => { if (!cancelled) setHealthOk(false); });
    };
    check();
    const id = setInterval(check, 15_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-zinc-900/50 border-r border-zinc-800 flex flex-col">
        {/* Logo */}
        <div className="p-5 border-b border-zinc-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sand-400 to-sand-600 flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-zinc-100 tracking-tight">
                QuickDraw
              </h1>
              <p className="text-[10px] text-zinc-500 font-medium uppercase tracking-widest">
                Control Plane
              </p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? "bg-sand-500/15 text-sand-300 border border-sand-500/20"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-800">
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                healthOk === true
                  ? "bg-emerald-500 animate-pulse-slow"
                  : healthOk === false
                  ? "bg-red-500"
                  : "bg-zinc-600"
              }`}
            />
            <span className="text-xs text-zinc-500">
              {healthOk === true
                ? "Control plane connected"
                : healthOk === false
                ? "Control plane offline"
                : "Checking..."}
            </span>
          </div>
          <p className="text-[10px] text-zinc-600 mt-1.5">
            tenant: default
          </p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto p-8">{children}</div>
      </main>
    </div>
  );
}
