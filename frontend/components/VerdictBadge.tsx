import clsx from "clsx";
import { AlertTriangle, ShieldCheck, ShieldX } from "lucide-react";
import type { Verdict } from "@/lib/types";

interface VerdictBadgeProps {
  verdict: Verdict;
  compact?: boolean;
}

export function VerdictBadge({ verdict, compact = false }: VerdictBadgeProps) {
  const Icon = verdict === "Verified" ? ShieldCheck : verdict === "Caution" ? AlertTriangle : ShieldX;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border font-semibold",
        compact ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-sm",
        verdict === "Verified" && "border-mint/30 bg-mint/[0.12] text-mint",
        verdict === "Caution" && "border-amber/30 bg-amber/[0.12] text-amber",
        verdict === "Risky" && "border-rose/30 bg-rose/[0.12] text-rose"
      )}
    >
      <Icon size={compact ? 14 : 16} aria-hidden="true" />
      {verdict}
    </span>
  );
}
