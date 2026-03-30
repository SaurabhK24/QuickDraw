import {
  Brain,
  Users,
  Receipt,
  FileSearch,
  Wrench,
  GitBranch,
  ChevronRight,
  Bot,
  Sparkles,
  Shield,
  Target,
  FileText,
  Search,
  BarChart3,
} from "lucide-react";

interface PackDef {
  id: string;
  name: string;
  description: string;
  icon: React.ElementType;
  color: string;
  bg: string;
  border: string;
  agents: AgentDef[];
  workflows: WorkflowDef[];
  customTools?: string[];
}

interface AgentDef {
  id: string;
  name: string;
  icon: React.ElementType;
  tools: string[];
  description: string;
}

interface WorkflowDef {
  id: string;
  name: string;
  steps: string[];
  trigger: string;
  hasApproval?: boolean;
}

const PACKS: PackDef[] = [
  {
    id: "govcon",
    name: "GovCon Capture & Proposal",
    description:
      "End-to-end government contracting — proposal neural optimization, FAR/DFARS compliance, DCAA invoicing, capture management, and competitive intelligence.",
    icon: Brain,
    color: "text-sand-400",
    bg: "bg-sand-500/10",
    border: "border-sand-500/20",
    customTools: ["neuroscore"],
    agents: [
      {
        id: "proposal-analyst",
        name: "Proposal Neural Analyst",
        icon: BarChart3,
        tools: ["neuroscore", "web_search", "filesystem", "memory"],
        description:
          "Scores proposal text across 5 neural dimensions (trust, resistance, engagement, cognitive load, salience) using neuroscience-backed ROI mapping.",
      },
      {
        id: "proposal-writer",
        name: "Proposal Writer",
        icon: FileText,
        tools: ["neuroscore", "filesystem", "memory", "web_search"],
        description:
          "Rewrites flagged sentences using 10 neural rewriting principles derived from fMRI persuasion research.",
      },
      {
        id: "compliance-checker",
        name: "Compliance Checker",
        icon: Shield,
        tools: ["web_search", "filesystem", "memory"],
        description:
          "FAR/DFARS, DCAA, CMMC, GSA AI clause review with insertion-ready corrective language.",
      },
      {
        id: "capture-strategist",
        name: "Capture Strategist",
        icon: Target,
        tools: ["web_search", "filesystem", "memory", "shell"],
        description:
          "Pwin modeling, competitive ghosting, teaming strategy, and win theme development.",
      },
      {
        id: "invoice-auditor",
        name: "DCAA Invoice Auditor",
        icon: Receipt,
        tools: ["filesystem", "memory"],
        description:
          "DCAA-compliant audit — FAR 31.2 cost allowability, indirect rates, unallowable cost detection.",
      },
    ],
    workflows: [
      {
        id: "proposal-optimization",
        name: "Proposal Neural Optimization",
        steps: ["proposal-analyst", "proposal-writer", "proposal-analyst"],
        trigger: "Optimize proposal text for evaluator persuasion",
        hasApproval: false,
      },
      {
        id: "compliance-review",
        name: "FAR/DFARS Compliance Review",
        steps: ["compliance-checker", "proposal-writer"],
        trigger: "Check document against federal regulations",
      },
      {
        id: "capture-analysis",
        name: "Capture & Competitive Intelligence",
        steps: ["capture-strategist", "capture-strategist"],
        trigger: "Research opportunity and build win strategy",
      },
      {
        id: "invoice-audit",
        name: "DCAA Invoice Audit",
        steps: ["invoice-auditor", "compliance-checker"],
        trigger: "Audit invoices for DCAA compliance",
        hasApproval: true,
      },
    ],
  },
  {
    id: "sales",
    name: "Sales",
    description:
      "Lead qualification, outreach automation, pipeline tracking, and deal analysis.",
    icon: Users,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
    agents: [
      {
        id: "sales-rep",
        name: "Sales Rep",
        icon: Users,
        tools: ["web_search", "filesystem", "memory", "shell"],
        description: "Enterprise B2B SDR — research, qualification, personalized outreach.",
      },
      {
        id: "sales-analyst",
        name: "Sales Analyst",
        icon: BarChart3,
        tools: ["web_search", "filesystem", "memory"],
        description: "Pipeline analytics, lead scoring, and deal intelligence.",
      },
    ],
    workflows: [
      {
        id: "lead-qualification",
        name: "Lead Qualification Pipeline",
        steps: ["sales-rep", "sales-analyst", "sales-rep"],
        trigger: "Qualify a lead or research a prospect",
      },
      {
        id: "deal-review",
        name: "Deal Review",
        steps: ["sales-analyst"],
        trigger: "Analyze a deal or assess deal health",
      },
    ],
  },
  {
    id: "billing",
    name: "Billing & Finance",
    description:
      "Invoice processing, collections, expense management, and financial analysis.",
    icon: Receipt,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
    agents: [
      {
        id: "invoice-processor",
        name: "Invoice Processor",
        icon: FileText,
        tools: ["filesystem", "memory", "shell"],
        description: "AP specialist — invoice extraction, validation, duplicate detection.",
      },
      {
        id: "collections-agent",
        name: "Collections Specialist",
        icon: Users,
        tools: ["filesystem", "memory", "web_search"],
        description: "Professional AR collections with severity-calibrated communications.",
      },
      {
        id: "finance-analyst",
        name: "Finance Analyst",
        icon: BarChart3,
        tools: ["filesystem", "memory", "web_search", "shell"],
        description: "Spend categorization, GL coding, approval routing, and cash flow analysis.",
      },
    ],
    workflows: [
      {
        id: "invoice-processing",
        name: "Invoice Processing Pipeline",
        steps: ["invoice-processor", "finance-analyst"],
        trigger: "Process an invoice or validate billing",
        hasApproval: true,
      },
      {
        id: "collections-workflow",
        name: "Collections Workflow",
        steps: ["collections-agent", "finance-analyst"],
        trigger: "Collect overdue invoices",
      },
    ],
  },
  {
    id: "executive-assistant",
    name: "Executive Assistant",
    description:
      "Task management, research briefings, meeting prep, and executive support.",
    icon: FileSearch,
    color: "text-violet-400",
    bg: "bg-violet-500/10",
    border: "border-violet-500/20",
    agents: [
      {
        id: "ea",
        name: "Executive Assistant",
        icon: Sparkles,
        tools: ["web_search", "filesystem", "memory", "shell"],
        description: "Elite EA — synthesis, drafting, prioritization, and anticipation.",
      },
      {
        id: "researcher",
        name: "Research Specialist",
        icon: Search,
        tools: ["web_search", "filesystem", "memory"],
        description: "Deep research with source evaluation and structured output.",
      },
    ],
    workflows: [
      {
        id: "meeting-prep",
        name: "Meeting Preparation",
        steps: ["researcher", "ea"],
        trigger: "Prepare for a meeting or create a briefing",
      },
      {
        id: "research-brief",
        name: "Research Brief",
        steps: ["researcher", "ea"],
        trigger: "Research a topic or create a brief",
      },
    ],
  },
];

export default function PacksPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100 tracking-tight">
          Packs
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          Vertical agent configurations — each pack defines specialized agents,
          tools, and multi-step workflows
        </p>
      </div>

      <div className="space-y-6">
        {PACKS.map((pack) => (
          <PackCard key={pack.id} pack={pack} />
        ))}
      </div>
    </div>
  );
}

function PackCard({ pack }: { pack: PackDef }) {
  return (
    <div id={pack.id} className="card overflow-hidden scroll-mt-8">
      {/* Header */}
      <div className="p-5 border-b border-zinc-800/50">
        <div className="flex items-start gap-4">
          <div
            className={`w-11 h-11 rounded-xl ${pack.bg} border ${pack.border} flex items-center justify-center flex-shrink-0`}
          >
            <pack.icon className={`w-5 h-5 ${pack.color}`} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold text-zinc-100">
                {pack.name}
              </h2>
              {pack.customTools && pack.customTools.length > 0 && (
                <span className="badge bg-sand-500/15 text-sand-400 border border-sand-500/20">
                  <Wrench className="w-3 h-3 mr-1" />
                  Custom Tools
                </span>
              )}
            </div>
            <p className="text-sm text-zinc-400 mt-1">{pack.description}</p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-xs text-zinc-500">
              {pack.agents.length} agents · {pack.workflows.length} workflows
            </p>
          </div>
        </div>
      </div>

      {/* Agents */}
      <div className="p-5 border-b border-zinc-800/50">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <Bot className="w-3.5 h-3.5" />
          Agents
        </h3>
        <div className="grid grid-cols-1 gap-2">
          {pack.agents.map((agent) => (
            <div
              key={agent.id}
              className="bg-zinc-800/30 rounded-lg p-3 flex items-start gap-3"
            >
              <agent.icon
                className={`w-4 h-4 ${pack.color} mt-0.5 flex-shrink-0`}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-200">
                    {agent.name}
                  </span>
                  <span className="text-[10px] text-zinc-600 font-mono">
                    {pack.id}.{agent.id}
                  </span>
                </div>
                <p className="text-xs text-zinc-500 mt-0.5">
                  {agent.description}
                </p>
                <div className="flex items-center gap-1.5 mt-2">
                  {agent.tools.map((tool) => (
                    <span
                      key={tool}
                      className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                        tool === "neuroscore"
                          ? "bg-sand-500/15 text-sand-400 border border-sand-500/20"
                          : "bg-zinc-800 text-zinc-500 border border-zinc-700"
                      }`}
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Workflows */}
      <div className="p-5">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <GitBranch className="w-3.5 h-3.5" />
          Workflows
        </h3>
        <div className="space-y-2">
          {pack.workflows.map((wf) => (
            <div
              key={wf.id}
              className="bg-zinc-800/30 rounded-lg p-3"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-sm font-medium text-zinc-200">
                  {wf.name}
                </span>
                {wf.hasApproval && (
                  <span className="badge bg-yellow-500/15 text-yellow-400 border border-yellow-500/20">
                    <Shield className="w-3 h-3 mr-1" />
                    Approval Gate
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-500 mb-2">{wf.trigger}</p>
              <div className="flex items-center gap-1">
                {wf.steps.map((step, i) => (
                  <div key={i} className="flex items-center gap-1">
                    <span className="text-[10px] font-mono bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded border border-zinc-700">
                      {step}
                    </span>
                    {i < wf.steps.length - 1 && (
                      <ChevronRight className="w-3 h-3 text-zinc-600" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
