"use client";

import Link from "next/link";
import { AlertTriangle, BadgeCheck, Database, ExternalLink, Globe2, Loader2, Play, RefreshCw, Search, Send, ShieldCheck, SlidersHorizontal, XCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { getOpportunities, queueIngestionUrl, runIngestion } from "@/lib/api";
import { applyLinkFor } from "@/lib/apply-link";
import { COUNTRIES } from "@/lib/samples";
import type { JobRecord, OpportunityFeedSummary } from "@/lib/types";
import {
  curationBucket,
  eligibilityCategory,
  evidenceFilterMatches,
  globalFitLens,
  isRestricted,
  scoreFilterMatches,
  whyThisJob,
  type EligibilityFilter,
  type EvidenceFilter,
  type OpportunityBucket,
  type ScoreFilter
} from "@/lib/curation";
import { ScoreRing } from "@/components/ScoreRing";
import { VerdictBadge } from "@/components/VerdictBadge";

const buckets: Array<{ key: OpportunityBucket; label: string; icon: LucideIcon }> = [
  { key: "curated", label: "Curated", icon: BadgeCheck },
  { key: "review", label: "Review", icon: AlertTriangle },
  { key: "rejected", label: "Not recommended", icon: XCircle }
];

const scoreFilters: ScoreFilter[] = ["All", "80+", "60-79", "<60"];
const evidenceFilters: EvidenceFilter[] = ["All", "Strong evidence", "Some evidence", "Limited evidence", "Risk signals"];
const eligibilityFilters: EligibilityFilter[] = ["All", "Worldwide", "Applicant match", "Restricted", "Unclear"];

function bucketTone(bucket: OpportunityBucket) {
  if (bucket === "curated") return "border-mint/35 bg-mint/[0.10] text-mint";
  if (bucket === "review") return "border-amber/35 bg-amber/[0.10] text-amber";
  return "border-rose/35 bg-rose/[0.10] text-rose";
}

function actionTone(action: string) {
  if (action === "Apply") return "border-mint/35 bg-mint/[0.10] text-mint";
  if (action === "Avoid") return "border-rose/35 bg-rose/[0.10] text-rose";
  return "border-amber/35 bg-amber/[0.10] text-amber";
}

function displayRemoteType(job: JobRecord) {
  return job.extracted.remote_type || "Remote unclear";
}

function displayRole(job: JobRecord) {
  return job.desired_role || "Any role";
}

function displayTitle(job: JobRecord) {
  return job.extracted.job_title || job.desired_role || "Untitled role";
}

function includesQuery(job: JobRecord, query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const text = [
    job.extracted.job_title,
    job.extracted.company,
    job.extracted.remote_type,
    job.desired_role,
    job.applicant_country,
    job.classification?.label
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return text.includes(q);
}

function OpportunityCard({ job, bucket }: { job: JobRecord; bucket: OpportunityBucket }) {
  const applyUrl = applyLinkFor(job);

  return (
    <article className="surface rounded-lg p-5">
      <div className="grid gap-5 xl:grid-cols-[112px_1fr_260px] xl:items-start">
        <ScoreRing score={job.final_score} size="sm" />

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold ${bucketTone(bucket)}`}>
              {buckets.find((item) => item.key === bucket)?.label}
            </span>
            <VerdictBadge verdict={job.verdict} compact />
            <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${actionTone(job.recommended_action)}`}>
              {job.recommended_action}
            </span>
          </div>

          <h2 className="mt-3 text-xl font-black text-white">{displayTitle(job)}</h2>
          <p className="mt-1 text-sm text-slate-400">{job.extracted.company || "Company not detected"}</p>

          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-300">{whyThisJob(job, bucket)}</p>

          <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold text-slate-300">
            <span className="rounded-full border border-line bg-white/[0.05] px-2.5 py-1">{displayRemoteType(job)}</span>
            <span className="rounded-full border border-line bg-white/[0.05] px-2.5 py-1">Applicant: {job.applicant_country}</span>
            <span className="rounded-full border border-line bg-white/[0.05] px-2.5 py-1">{displayRole(job)}</span>
          </div>
        </div>

        <aside className="text-sm text-slate-300">
          <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
            <ShieldCheck size={15} aria-hidden="true" /> Trust Passport
          </div>
          <dl className="grid gap-2">
            <div className="flex items-center justify-between gap-3 border-b border-line/70 pb-2">
              <dt className="text-slate-400">Global fit</dt>
              <dd className="text-right font-semibold text-white">{globalFitLens(job)}</dd>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-line/70 pb-2">
              <dt className="text-slate-400">Remote</dt>
              <dd className="text-right font-semibold text-white">{job.scores.remote_authenticity}/100</dd>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-line/70 pb-2">
              <dt className="text-slate-400">Company</dt>
              <dd className="text-right font-semibold text-white">{job.company_verification.status}</dd>
            </div>
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href={`/results/${job.job_id}`} className="btn-secondary px-3 py-2">
              Details
            </Link>
            {applyUrl ? (
              <a href={applyUrl} target="_blank" rel="noreferrer" className="btn-primary px-3 py-2">
                Apply <ExternalLink size={15} aria-hidden="true" />
              </a>
            ) : null}
          </div>
        </aside>
      </div>
    </article>
  );
}

export default function OpportunitiesPage() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [summary, setSummary] = useState<OpportunityFeedSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isQueueing, setIsQueueing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [queueUrl, setQueueUrl] = useState("");
  const [queueCountry, setQueueCountry] = useState("India");
  const [queueRole, setQueueRole] = useState("");
  const [bucket, setBucket] = useState<OpportunityBucket>("curated");
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("All");
  const [role, setRole] = useState("All");
  const [remoteType, setRemoteType] = useState("All");
  const [evidence, setEvidence] = useState<EvidenceFilter>("All");
  const [scoreRange, setScoreRange] = useState<ScoreFilter>("All");
  const [eligibility, setEligibility] = useState<EligibilityFilter>("All");

  async function loadJobs() {
    setIsLoading(true);
    setError("");
    try {
      const feed = await getOpportunities();
      setJobs(feed.jobs);
      setSummary(feed.summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load curated opportunities.");
    } finally {
      setIsLoading(false);
    }
  }

  async function processFeed() {
    setIsProcessing(true);
    setError("");
    setNotice("");
    try {
      const result = await runIngestion();
      setNotice(`Processed ${result.source_records_collected} collected jobs, published ${result.gold_records_published} new opportunities.`);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not process the ingestion feed.");
    } finally {
      setIsProcessing(false);
    }
  }

  async function queueUrlForIngestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const jobUrl = queueUrl.trim();
    if (!jobUrl) return;
    setIsQueueing(true);
    setError("");
    setNotice("");
    try {
      const response = await queueIngestionUrl({
        job_url: jobUrl,
        applicant_country: queueCountry,
        desired_role: queueRole.trim() || null
      });
      setNotice(`${response.message} ${response.queued_count} queued URL${response.queued_count === 1 ? "" : "s"} waiting.`);
      setQueueUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not queue that URL.");
    } finally {
      setIsQueueing(false);
    }
  }

  useEffect(() => {
    void loadJobs();
  }, []);

  const jobsByBucket = useMemo(() => {
    return jobs.reduce<Record<OpportunityBucket, JobRecord[]>>(
      (groups, job) => {
        groups[curationBucket(job)].push(job);
        return groups;
      },
      { curated: [], review: [], rejected: [] }
    );
  }, [jobs]);

  const roleOptions = useMemo(() => Array.from(new Set(jobs.map(displayRole))).sort(), [jobs]);
  const remoteOptions = useMemo(() => Array.from(new Set(jobs.map(displayRemoteType))).sort(), [jobs]);

  const filteredJobs = useMemo(() => {
    return jobsByBucket[bucket].filter((job) => {
      const matchesCountry = country === "All" || job.applicant_country === country;
      const matchesRole = role === "All" || displayRole(job) === role;
      const matchesRemote = remoteType === "All" || displayRemoteType(job) === remoteType;
      const matchesEligibility = eligibility === "All" || eligibilityCategory(job) === eligibility;
      return (
        includesQuery(job, query) &&
        matchesCountry &&
        matchesRole &&
        matchesRemote &&
        matchesEligibility &&
        evidenceFilterMatches(job, evidence) &&
        scoreFilterMatches(job, scoreRange)
      );
    });
  }, [jobsByBucket, bucket, country, role, remoteType, eligibility, evidence, scoreRange, query]);

  const averageScore = jobs.length ? Math.round(jobs.reduce((sum, job) => sum + job.final_score, 0) / jobs.length) : 0;
  const restrictedCount = jobs.filter(isRestricted).length;

  return (
    <main className="px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="label">Curated Opportunities</p>
            <h1 className="mt-3 text-3xl font-black text-white sm:text-4xl">Vetted remote jobs worth a closer look</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-400">A near-real-time lakehouse feed that collects, preprocesses, dedupes, and publishes verified remote opportunities.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="btn-primary" onClick={() => void processFeed()} disabled={isProcessing}>
              {isProcessing ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
              Collect now
            </button>
            <button className="btn-secondary" onClick={() => void loadJobs()} disabled={isLoading}>
              <RefreshCw size={16} aria-hidden="true" /> Refresh
            </button>
          </div>
        </div>

        <section className="mt-8 grid gap-4 md:grid-cols-5">
          <div className="surface rounded-lg p-5">
            <div className="text-sm text-slate-400">Jobs collected</div>
            <div className="mt-2 text-3xl font-black text-white">{summary?.jobs_collected || jobs.length}</div>
          </div>
          <div className="surface rounded-lg p-5">
            <div className="text-sm text-slate-400">Jobs deduped</div>
            <div className="mt-2 text-3xl font-black text-cyan">{summary?.jobs_deduped || jobs.length}</div>
          </div>
          <div className="surface rounded-lg p-5">
            <div className="text-sm text-slate-400">Verified opportunities</div>
            <div className="mt-2 text-3xl font-black text-mint">{summary?.verified_opportunities || jobsByBucket.curated.length}</div>
          </div>
          <div className="surface rounded-lg p-5">
            <div className="text-sm text-slate-400">Risky removed</div>
            <div className="mt-2 text-3xl font-black text-rose">{summary?.risky_jobs_filtered || jobsByBucket.rejected.length}</div>
          </div>
          <div className="surface rounded-lg p-5">
            <div className="text-sm text-slate-400">Average score</div>
            <div className="mt-2 text-3xl font-black text-cyan">{summary?.average_score ?? (averageScore || "N/A")}</div>
          </div>
        </section>

        <section className="mt-6 surface rounded-lg p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
              <span className="inline-flex items-center gap-2 rounded-full border border-line bg-white/[0.05] px-3 py-1.5">
                <Database size={15} aria-hidden="true" />
                {summary?.ingestion_status || "not_run"}
              </span>
              <span className="rounded-full border border-line bg-white/[0.05] px-3 py-1.5">
                Scheduler: {summary?.scheduler_enabled ? "on" : "off"}
              </span>
              <span className="rounded-full border border-line bg-white/[0.05] px-3 py-1.5">
                Last run: {summary?.last_run_at ? new Date(summary.last_run_at).toLocaleString() : "Not yet"}
              </span>
            </div>
            <form onSubmit={queueUrlForIngestion} className="grid gap-3 xl:grid-cols-[minmax(240px,1fr)_150px_180px_auto]">
              <input className="input-shell" placeholder="Queue a job URL" value={queueUrl} onChange={(event) => setQueueUrl(event.target.value)} />
              <select className="input-shell" value={queueCountry} onChange={(event) => setQueueCountry(event.target.value)}>
                {COUNTRIES.map((item) => (
                  <option key={item} value={item} className="bg-ink">{item}</option>
                ))}
              </select>
              <input className="input-shell" placeholder="Role optional" value={queueRole} onChange={(event) => setQueueRole(event.target.value)} />
              <button className="btn-secondary" disabled={isQueueing || !queueUrl.trim()} type="submit">
                {isQueueing ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Send size={16} aria-hidden="true" />}
                Queue
              </button>
            </form>
          </div>
          {notice ? <div className="mt-4 rounded-lg border border-mint/30 bg-mint/[0.10] p-3 text-sm text-mint">{notice}</div> : null}
        </section>

        <section className="mt-6 surface rounded-lg p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex flex-wrap gap-2">
              {buckets.map((item) => {
                const Icon = item.icon;
                const active = bucket === item.key;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setBucket(item.key)}
                    className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-bold transition ${
                      active ? bucketTone(item.key) : "border-line bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]"
                    }`}
                  >
                    <Icon size={16} aria-hidden="true" />
                    {item.label}
                    <span className="text-xs opacity-80">{jobsByBucket[item.key].length}</span>
                  </button>
                );
              })}
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Globe2 size={16} aria-hidden="true" />
              {restrictedCount} jobs include location, authorization, or timezone constraints.
            </div>
          </div>

          <div className="mt-5 grid gap-3 lg:grid-cols-[1.2fr_repeat(3,0.8fr)] xl:grid-cols-[1.3fr_repeat(6,0.7fr)]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={17} aria-hidden="true" />
              <input className="input-shell pl-10" placeholder="Search jobs" value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
            <select className="input-shell" value={country} onChange={(event) => setCountry(event.target.value)}>
              <option value="All" className="bg-ink">All countries</option>
              {COUNTRIES.map((item) => (
                <option key={item} value={item} className="bg-ink">{item}</option>
              ))}
            </select>
            <select className="input-shell" value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="All" className="bg-ink">All roles</option>
              {roleOptions.map((item) => (
                <option key={item} value={item} className="bg-ink">{item}</option>
              ))}
            </select>
            <select className="input-shell" value={remoteType} onChange={(event) => setRemoteType(event.target.value)}>
              <option value="All" className="bg-ink">All remote</option>
              {remoteOptions.map((item) => (
                <option key={item} value={item} className="bg-ink">{item}</option>
              ))}
            </select>
            <select className="input-shell" value={evidence} onChange={(event) => setEvidence(event.target.value as EvidenceFilter)}>
              {evidenceFilters.map((item) => (
                <option key={item} value={item} className="bg-ink">{item === "All" ? "All evidence" : item}</option>
              ))}
            </select>
            <select className="input-shell" value={scoreRange} onChange={(event) => setScoreRange(event.target.value as ScoreFilter)}>
              {scoreFilters.map((item) => (
                <option key={item} value={item} className="bg-ink">{item === "All" ? "All scores" : item}</option>
              ))}
            </select>
            <select className="input-shell" value={eligibility} onChange={(event) => setEligibility(event.target.value as EligibilityFilter)}>
              {eligibilityFilters.map((item) => (
                <option key={item} value={item} className="bg-ink">{item === "All" ? "All fit" : item}</option>
              ))}
            </select>
          </div>
        </section>

        {isLoading ? (
          <div className="mt-8 surface rounded-lg p-8 text-center">
            <Loader2 className="mx-auto animate-spin text-mint" size={32} aria-hidden="true" />
            <p className="mt-4 text-sm font-semibold text-slate-200">Loading opportunities...</p>
          </div>
        ) : null}

        {error ? <div className="mt-8 rounded-lg border border-rose/40 bg-rose/[0.10] p-4 text-sm leading-6 text-rose">{error}</div> : null}

        {!isLoading && !error && filteredJobs.length === 0 ? (
          <div className="mt-8 surface rounded-lg p-8 text-center">
            <SlidersHorizontal className="mx-auto text-slate-500" size={32} aria-hidden="true" />
            <h2 className="mt-4 text-xl font-bold text-white">No jobs match this view</h2>
            <p className="mt-2 text-sm text-slate-400">Seed demo jobs or loosen the filters to rebuild the shortlist.</p>
            <div className="mt-5 flex justify-center gap-3">
              <Link href="/analyze" className="btn-primary">
                Analyze a Job
              </Link>
              <Link href="/dashboard" className="btn-secondary">
                Dashboard
              </Link>
            </div>
          </div>
        ) : null}

        <div className="mt-8 grid gap-4">
          {filteredJobs.map((job) => (
            <OpportunityCard key={job.job_id} job={job} bucket={bucket} />
          ))}
        </div>
      </div>
    </main>
  );
}
