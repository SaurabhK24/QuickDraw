interface NeuralScoreBarProps {
  label: string;
  value: number;
  max?: number;
  color: "trust" | "resistance" | "engagement" | "load" | "salience";
  direction?: "+" | "-" | "~";
}

const COLOR_MAP = {
  trust: { bar: "bg-emerald-500", bg: "bg-emerald-500/10", text: "text-emerald-400" },
  resistance: { bar: "bg-red-500", bg: "bg-red-500/10", text: "text-red-400" },
  engagement: { bar: "bg-blue-500", bg: "bg-blue-500/10", text: "text-blue-400" },
  load: { bar: "bg-yellow-500", bg: "bg-yellow-500/10", text: "text-yellow-400" },
  salience: { bar: "bg-violet-500", bg: "bg-violet-500/10", text: "text-violet-400" },
};

const REGION_MAP = {
  trust: "vmPFC",
  resistance: "ACC",
  engagement: "Precuneus",
  load: "DLPFC",
  salience: "Amygdala",
};

export function NeuralScoreBar({
  label,
  value,
  max = 1,
  color,
  direction = "+",
}: NeuralScoreBarProps) {
  const pct = Math.min((value / max) * 100, 100);
  const c = COLOR_MAP[color];
  const dirIcon = direction === "+" ? "+" : direction === "-" ? "-" : "~";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className={`font-medium ${c.text}`}>{label}</span>
          <span className="text-zinc-600 font-mono text-[10px]">
            {REGION_MAP[color]}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-zinc-500 text-[10px]">{dirIcon}</span>
          <span className={`font-mono font-medium ${c.text}`}>
            {value.toFixed(2)}
          </span>
        </div>
      </div>
      <div className={`h-1.5 rounded-full ${c.bg}`}>
        <div
          className={`h-full rounded-full ${c.bar} transition-all duration-500 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function NeuralScoreCard({
  scores,
  persuasionScore,
}: {
  scores: Record<string, number>;
  persuasionScore?: number;
}) {
  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">
          Neural Persuasion Profile
        </h3>
        {persuasionScore != null && (
          <div
            className={`text-2xl font-bold font-mono ${
              persuasionScore >= 65
                ? "text-emerald-400"
                : persuasionScore >= 45
                ? "text-yellow-400"
                : "text-red-400"
            }`}
          >
            {persuasionScore.toFixed(0)}
            <span className="text-xs text-zinc-500 font-normal">/100</span>
          </div>
        )}
      </div>
      <div className="space-y-3">
        <NeuralScoreBar label="Trust" value={scores.trust ?? 0} color="trust" direction="+" />
        <NeuralScoreBar label="Resistance" value={scores.resistance ?? 0} color="resistance" direction="-" />
        <NeuralScoreBar label="Engagement" value={scores.engagement ?? 0} color="engagement" direction="+" />
        <NeuralScoreBar label="Cognitive Load" value={scores.cognitive_load ?? 0} color="load" direction="-" />
        <NeuralScoreBar label="Salience" value={scores.salience ?? 0} color="salience" direction="~" />
      </div>
    </div>
  );
}
