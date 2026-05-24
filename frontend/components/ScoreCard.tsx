import { Info } from "lucide-react";

interface ScoreCardProps {
  title: string;
  score: number;
  description: string;
}

function barColor(score: number): string {
  if (score >= 80) return "bg-mint";
  if (score >= 60) return "bg-amber";
  return "bg-rose";
}

export function ScoreCard({ title, score, description }: ScoreCardProps) {
  return (
    <article className="surface rounded-lg p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-white">
            {title}
            <span title={description} aria-label={`${title} info`}>
              <Info className="text-slate-500" size={14} aria-hidden="true" />
            </span>
          </h3>
          <p className="mt-1 text-sm leading-6 text-slate-400">{description}</p>
        </div>
        <span className="rounded-md bg-white/[0.07] px-2.5 py-1 text-sm font-bold text-white" title={`${title}: ${score} out of 100`}>
          {score}
        </span>
      </div>
      <div className="mt-5 h-2.5 overflow-hidden rounded-full bg-white/[0.08]">
        <div className={`${barColor(score)} h-full rounded-full transition-all`} style={{ width: `${score}%` }} />
      </div>
    </article>
  );
}
