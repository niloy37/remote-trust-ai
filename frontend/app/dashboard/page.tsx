"use client";

import Link from "next/link";
import { CalendarDays, ExternalLink, Filter, Loader2, RefreshCw, Search, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getJobs } from "@/lib/api";
import { applyLinkFor } from "@/lib/apply-link";
import { displayVerdict, friendlyErrorMessage } from "@/lib/display";
import { COUNTRIES } from "@/lib/samples";
import type { JobRecord, Verdict } from "@/lib/types";
import { ScoreRing } from "@/components/ScoreRing";
import { VerdictBadge } from "@/components/VerdictBadge";

const verdicts: Array<"All" | Verdict> = ["All", "Verified", "Caution", "Risky"];

function titleBadgeClass(verdict: string) {
  if (verdict === "Recognized" || verdict === "Plausible") return "border-mint/30 bg-mint/[0.10] text-mint";
  if (verdict === "Unusual") return "border-amber/30 bg-amber/[0.10] text-amber";
  return "border-rose/30 bg-rose/[0.10] text-rose";
}

function companyBadgeClass(status: string) {
  if (status === "Strong evidence" || status === "Some evidence") return "border-mint/30 bg-mint/[0.10] text-mint";
  if (status === "Risk signals") return "border-rose/30 bg-rose/[0.10] text-rose";
  return "border-amber/30 bg-amber/[0.10] text-amber";
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [verdict, setVerdict] = useState<"All" | Verdict>("All");
  const [country, setCountry] = useState("All");

  async function loadJobs() {
    setIsLoading(true);
    setError("");
    try {
      setJobs(await getJobs());
    } catch (err) {
      setError(friendlyErrorMessage(err, "We could not load the dashboard right now. Please try again."));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadJobs();
  }, []);

  const filteredJobs = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter((job) => {
      const text = `${job.extracted.job_title || ""} ${job.extracted.company || ""} ${job.extracted.remote_type || ""}`.toLowerCase();
      const matchesQuery = !q || text.includes(q);
      const matchesVerdict = verdict === "All" || job.verdict === verdict;
      const matchesCountry = country === "All" || job.applicant_country === country;
      return matchesQuery && matchesVerdict && matchesCountry;
    });
  }, [jobs, query, verdict, country]);

  const averageScore = jobs.length ? Math.round(jobs.reduce((sum, job) => sum + job.final_score, 0) / jobs.length) : 0;

  return (
    <main className="px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="label">Dashboard</p>
            <h1 className="mt-3 text-3xl font-black text-white sm:text-4xl">Analyzed remote jobs</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-400">Review previous analyses, filter by result and applicant country, and open the full explanation.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/opportunities" className="btn-primary">
              <Sparkles size={16} aria-hidden="true" /> Curated Feed
            </Link>
            <button className="btn-secondary" onClick={() => void loadJobs()}>
              <RefreshCw size={16} aria-hidden="true" /> Refresh
            </button>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="surface rounded-lg p-5">
            <div className="text-sm text-slate-400">Jobs analyzed</div>
            <div className="mt-2 text-3xl font-black text-white">{jobs.length}</div>
          </div>
          <div className="surface rounded-lg p-5">
            <div className="text-sm text-slate-400">Verified jobs</div>
            <div className="mt-2 text-3xl font-black text-mint">{jobs.filter((job) => job.verdict === "Verified").length}</div>
          </div>
          <div className="surface rounded-lg p-5">
            <div className="text-sm text-slate-400">Average score</div>
            <div className="mt-2 text-3xl font-black text-cyan">{averageScore || "N/A"}</div>
          </div>
        </div>

        <section className="mt-6 surface rounded-lg p-5">
          <div className="grid gap-4 lg:grid-cols-[1fr_180px_220px]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={17} aria-hidden="true" />
              <input className="input-shell pl-10" placeholder="Search title, company, or remote type" value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
            <label className="relative block">
              <Filter className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={17} aria-hidden="true" />
              <select className="input-shell pl-10" value={verdict} onChange={(event) => setVerdict(event.target.value as "All" | Verdict)}>
                {verdicts.map((item) => (
                  <option key={item} value={item} className="bg-ink">
                    {item === "All" ? "All" : displayVerdict(item)}
                  </option>
                ))}
              </select>
            </label>
            <select className="input-shell" value={country} onChange={(event) => setCountry(event.target.value)}>
              <option value="All" className="bg-ink">
                All countries
              </option>
              {COUNTRIES.map((item) => (
                <option key={item} value={item} className="bg-ink">
                  {item}
                </option>
              ))}
            </select>
          </div>
        </section>

        {isLoading ? (
          <div className="mt-8 surface rounded-lg p-8 text-center">
            <Loader2 className="mx-auto animate-spin text-mint" size={32} aria-hidden="true" />
            <p className="mt-4 text-sm font-semibold text-slate-200">Loading analyzed jobs...</p>
          </div>
        ) : null}

        {error ? <div className="mt-8 rounded-lg border border-rose/40 bg-rose/[0.10] p-4 text-sm leading-6 text-rose">{error}</div> : null}

        {!isLoading && !error && filteredJobs.length === 0 ? (
          <div className="mt-8 surface rounded-lg p-8 text-center">
            <h2 className="text-xl font-bold text-white">No analyzed jobs yet</h2>
            <p className="mt-2 text-sm text-slate-400">Seed sample data or analyze a posting to populate the dashboard.</p>
            <Link href="/analyze" className="btn-primary mt-5">
              Analyze a Job
            </Link>
          </div>
        ) : null}

        <div className="mt-8 grid gap-4">
          {filteredJobs.map((job) => {
            const applyUrl = applyLinkFor(job);
            return (
            <article key={job.job_id} className="surface rounded-lg p-5 transition hover:border-cyan/40 hover:bg-white/[0.04]">
              <div className="grid gap-5 lg:grid-cols-[120px_1fr_260px] lg:items-center">
                <ScoreRing score={job.final_score} size="sm" />
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <VerdictBadge verdict={job.verdict} compact />
                    <span className="rounded-full border border-line bg-white/[0.05] px-2.5 py-1 text-xs font-semibold text-slate-300">
                      {job.extracted.remote_type || "Remote unclear"}
                    </span>
                    <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${titleBadgeClass(job.title_validation.verdict)}`}>
                      Role title: {job.title_validation.verdict}
                    </span>
                    <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${companyBadgeClass(job.company_verification.status)}`}>
                      Company: {job.company_verification.status}
                    </span>
                  </div>
                  <h2 className="mt-3 text-xl font-bold text-white">{job.extracted.job_title || "Untitled role"}</h2>
                  <p className="mt-1 text-sm text-slate-400">{job.extracted.company || "Company not detected"}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                    <span>Eligibility: {job.extracted.allowed_countries.length ? job.extracted.allowed_countries.join(", ") : "No explicit restriction"}</span>
                    <span>Applicant: {job.applicant_country}</span>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-sm text-slate-400 lg:justify-end">
                  <span className="inline-flex items-center gap-2">
                    <CalendarDays size={16} aria-hidden="true" />
                    {new Date(job.created_at).toLocaleDateString()}
                  </span>
                  <Link href={`/results/${job.job_id}`} className="btn-secondary px-3 py-2">
                    Details
                  </Link>
                  {applyUrl ? (
                    <a href={applyUrl} target="_blank" rel="noreferrer" className="btn-primary px-3 py-2">
                      Apply <ExternalLink size={15} aria-hidden="true" />
                    </a>
                  ) : null}
                </div>
              </div>
            </article>
            );
          })}
        </div>
      </div>
    </main>
  );
}
