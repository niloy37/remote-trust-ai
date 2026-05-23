import clsx from "clsx";

interface ScoreRingProps {
  score: number;
  label?: string;
  size?: "sm" | "lg";
}

function colorForScore(score: number): string {
  if (score >= 80) return "#3dd6a3";
  if (score >= 60) return "#fbbf24";
  return "#fb7185";
}

export function ScoreRing({ score, label = "Trust Score", size = "lg" }: ScoreRingProps) {
  const diameter = size === "lg" ? "h-44 w-44" : "h-28 w-28";
  const inner = size === "lg" ? "h-32 w-32" : "h-20 w-20";
  const scoreText = size === "lg" ? "text-5xl" : "text-3xl";

  return (
    <div
      className={clsx("relative flex shrink-0 items-center justify-center rounded-full p-2", diameter)}
      style={{
        background: `conic-gradient(${colorForScore(score)} ${score * 3.6}deg, rgba(148, 163, 184, 0.18) 0deg)`
      }}
      aria-label={`${label}: ${score} out of 100`}
    >
      <div className={clsx("flex flex-col items-center justify-center rounded-full bg-ink text-center", inner)}>
        <span className={clsx("font-black leading-none text-white", scoreText)}>{score}</span>
        <span className="mt-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">/ 100</span>
      </div>
    </div>
  );
}

