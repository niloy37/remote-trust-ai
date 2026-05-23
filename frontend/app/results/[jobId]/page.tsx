"use client";

import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getJob } from "@/lib/api";
import type { JobRecord } from "@/lib/types";
import { ResultsPanel } from "@/components/ResultsPanel";

export default function ResultPage() {
  const params = useParams<{ jobId: string }>();
  const [job, setJob] = useState<JobRecord | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError("");
      try {
        setJob(await getJob(params.jobId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load result.");
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [params.jobId]);

  return (
    <main className="px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <Link href="/dashboard" className="mb-6 inline-flex items-center gap-2 text-sm font-semibold text-slate-300 hover:text-white">
          <ArrowLeft size={16} aria-hidden="true" /> Back to dashboard
        </Link>

        {isLoading ? (
          <div className="surface rounded-lg p-8 text-center">
            <Loader2 className="mx-auto animate-spin text-mint" size={32} aria-hidden="true" />
            <p className="mt-4 text-sm font-semibold text-slate-200">Loading result...</p>
          </div>
        ) : null}

        {error ? <div className="rounded-lg border border-rose/40 bg-rose/[0.10] p-4 text-sm leading-6 text-rose">{error}</div> : null}

        {job ? <ResultsPanel result={job} showOpenResultLink={false} /> : null}
      </div>
    </main>
  );
}
