import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, Link } from "@remix-run/react";
import { getHealth, listAgents } from "~/lib/api.server";
import {
  Activity,
  Package,
  GitBranch,
  Play,
  ArrowUpRight,
  Brain,
  Shield,
  FileSearch,
  Users,
  Receipt,
} from "lucide-react";

const PACK_INFO = [
  {
    id: "govcon",
    name: "GovCon Capture & Proposal",
    icon: Brain,
    agents: 5,
    workflows: 4,
    color: "text-sand-400",
    bg: "bg-sand-500/10",
    border: "border-sand-500/20",
  },
  {
    id: "sales",
    name: "Sales",
    icon: Users,
    agents: 2,
    workflows: 2,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
  },
  {
    id: "billing",
    name: "Billing & Finance",
    icon: Receipt,
    agents: 3,
    workflows: 2,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
  },
  {
    id: "executive-assistant",
    name: "Executive Assistant",
    icon: FileSearch,
    agents: 2,
    workflows: 2,
    color: "text-violet-400",
    bg: "bg-violet-500/10",
    border: "border-violet-500/20",
  },
];

export async function loader({ request }: LoaderFunctionArgs) {
  let health = { status: "unknown", service: "quickdraw", timestamp: "" };
  let agents: { id: string; name: string }[] = [];

  try {
    health = await getHealth();
  } catch {
    health.status = "offline";
  }

  try {
    const res = await listAgents();
    agents = res.agents;
  } catch {
    // offline
  }

  return json({ health, agents });
}

export default function Overview() {
  const { health, agents } = useLoaderData<typeof loader>();
  const online = health.status === "ok";

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-zinc-100 tracking-tight">
          Dashboard
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          QuickDraw agentic workflow control plane
        </p>
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatusCard
          label="Control Plane"
          value={online ? "Online" : "Offline"}
          icon={Activity}
          color={online ? "emerald" : "red"}
        />
        <StatusCard
          label="Registered Agents"
          value={agents.length.toString()}
          icon={Users}
          color="blue"
        />
        <StatusCard
          label="Active Packs"
          value={PACK_INFO.length.toString()}
          icon={Package}
          color="violet"
        />
        <StatusCard
          label="Temporal"
          value={online ? "Connected" : "Disconnected"}
          icon={GitBranch}
          color={online ? "emerald" : "red"}
        />
      </div>

      {/* Quick actions */}
      <div className="card-hover p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-zinc-200">Quick Start</h2>
          <Link
            to="/run"
            className="text-xs text-sand-400 hover:text-sand-300 font-medium flex items-center gap-1"
          >
            New Run <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <QuickAction
            to="/run?mode=routed&prompt=Optimize+this+proposal+section"
            label="Proposal Neural Optimization"
            desc="Score & rewrite proposal text for persuasion"
            icon={Brain}
          />
          <QuickAction
            to="/run?mode=routed&prompt=Review+FAR+DFARS+compliance"
            label="Compliance Review"
            desc="FAR/DFARS gap analysis with remediation"
            icon={Shield}
          />
          <QuickAction
            to="/run?mode=routed&prompt=Research+this+opportunity"
            label="Capture Analysis"
            desc="Competitive intelligence & win strategy"
            icon={FileSearch}
          />
          <QuickAction
            to="/run?mode=routed&prompt=Qualify+this+lead"
            label="Lead Qualification"
            desc="Research, score, and draft outreach"
            icon={Users}
          />
        </div>
      </div>

      {/* Packs grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-zinc-200">
            Installed Packs
          </h2>
          <Link
            to="/packs"
            className="text-xs text-sand-400 hover:text-sand-300 font-medium flex items-center gap-1"
          >
            View all <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {PACK_INFO.map((pack) => (
            <Link key={pack.id} to={`/packs#${pack.id}`}>
              <div
                className={`card-hover p-4 flex items-start gap-4`}
              >
                <div
                  className={`w-10 h-10 rounded-lg ${pack.bg} border ${pack.border} flex items-center justify-center flex-shrink-0`}
                >
                  <pack.icon className={`w-5 h-5 ${pack.color}`} />
                </div>
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-zinc-200 truncate">
                    {pack.name}
                  </h3>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {pack.agents} agents · {pack.workflows} workflows
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatusCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    red: "text-red-400 bg-red-500/10 border-red-500/20",
    blue: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    violet: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  };
  const c = colorMap[color] ?? colorMap.blue;
  const textColor = c.split(" ")[0];

  return (
    <div className="card p-4">
      <div className="flex items-center gap-3 mb-3">
        <div
          className={`w-8 h-8 rounded-lg ${c} border flex items-center justify-center`}
        >
          <Icon className={`w-4 h-4 ${textColor}`} />
        </div>
      </div>
      <p className="text-xs text-zinc-500">{label}</p>
      <p className={`text-lg font-semibold ${textColor} mt-0.5`}>{value}</p>
    </div>
  );
}

function QuickAction({
  to,
  label,
  desc,
  icon: Icon,
}: {
  to: string;
  label: string;
  desc: string;
  icon: React.ElementType;
}) {
  return (
    <Link to={to}>
      <div className="bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 rounded-lg p-3.5 transition-all group">
        <div className="flex items-center gap-2.5 mb-1.5">
          <Icon className="w-4 h-4 text-sand-400" />
          <span className="text-sm font-medium text-zinc-200">{label}</span>
          <Play className="w-3 h-3 text-zinc-600 group-hover:text-sand-400 ml-auto transition-colors" />
        </div>
        <p className="text-xs text-zinc-500">{desc}</p>
      </div>
    </Link>
  );
}
