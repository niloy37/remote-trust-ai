"use client";

import { ArrowRight, ClipboardPaste, Loader2, Link2, MapPin, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import { analyzeJob } from "@/lib/api";
import { friendlyErrorMessage } from "@/lib/display";
import { COUNTRIES, SAMPLE_JOBS } from "@/lib/samples";
import type { AnalysisResponse, AnalyzeRequest } from "@/lib/types";
import { ResultsPanel } from "@/components/ResultsPanel";

const initialForm: AnalyzeRequest = {
  job_url: "",
  job_description: "",
  applicant_country: "India",
  desired_role: ""
};

export default function AnalyzerPage() {
  const [form, setForm] = useState<AnalyzeRequest>(initialForm);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>("");

  function updateField<K extends keyof AnalyzeRequest>(key: K, value: AnalyzeRequest[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError("");
    setResult(null);
    try {
      const payload: AnalyzeRequest = {
        job_url: form.job_url?.trim() || null,
        job_description: form.job_description.trim(),
        applicant_country: form.applicant_country,
        desired_role: form.desired_role?.trim() || null
      };
      const analysis = await analyzeJob(payload);
      setResult(analysis);
    } catch (err) {
      setError(friendlyErrorMessage(err, "We could not analyze this job right now. Please try again."));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="label">Analyzer</p>
            <h1 className="mt-3 text-3xl font-black text-white sm:text-4xl">Verify a remote job before you apply.</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-400">
              Paste a job URL or job description, choose the applicant country, and get a trust score with concrete reasons.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_JOBS.map((sample) => (
              <button
                key={sample.label}
                type="button"
                className="btn-secondary"
                onClick={() =>
                  setForm({
                    job_url: sample.job_url,
                    job_description: sample.job_description,
                    applicant_country: sample.applicant_country,
                    desired_role: sample.desired_role
                  })
                }
              >
                <Sparkles size={16} aria-hidden="true" /> {sample.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
          <form onSubmit={handleSubmit} className="surface rounded-lg p-6">
            <div className="grid gap-5">
              <label className="block">
                <span className="mb-2 flex items-center justify-between gap-2 text-sm font-semibold text-slate-200">
                  <span className="flex items-center gap-2">
                  <Link2 size={16} aria-hidden="true" /> Job URL
                  </span>
                  <span className="rounded-full border border-cyan/30 bg-cyan/[0.10] px-2.5 py-1 text-xs text-cyan">URL check</span>
                </span>
                <input
                  className="input-shell"
                  placeholder="https://jobs.greenhouse.io/company/job or a public job page"
                  value={form.job_url || ""}
                  onChange={(event) => updateField("job_url", event.target.value)}
                />
                <p className="mt-2 text-xs leading-5 text-slate-500">Best on public career pages and ATS links. LinkedIn and Indeed may require pasted text if they block automated page access.</p>
              </label>

              <label className="block">
                <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200">
                  <ClipboardPaste size={16} aria-hidden="true" /> Job description
                </span>
                <textarea
                  className="input-shell min-h-80 resize-y"
                  placeholder="Paste the full job description here..."
                  value={form.job_description}
                  onChange={(event) => updateField("job_description", event.target.value)}
                />
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200">
                    <MapPin size={16} aria-hidden="true" /> Applicant country
                  </span>
                  <select
                    className="input-shell"
                    value={form.applicant_country}
                    onChange={(event) => updateField("applicant_country", event.target.value)}
                  >
                    {COUNTRIES.map((country) => (
                      <option key={country} value={country} className="bg-ink">
                        {country}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200">
                    <Sparkles size={16} aria-hidden="true" /> Desired role
                  </span>
                  <input
                    className="input-shell"
                    placeholder="Software Engineer"
                    value={form.desired_role || ""}
                    onChange={(event) => updateField("desired_role", event.target.value)}
                  />
                </label>
              </div>

              {error ? <div className="rounded-lg border border-rose/40 bg-rose/[0.10] p-4 text-sm leading-6 text-rose">{error}</div> : null}

              <button className="btn-primary w-full" disabled={isLoading || (!form.job_url && !form.job_description.trim())}>
                {isLoading ? <Loader2 className="animate-spin" size={18} aria-hidden="true" /> : <ArrowRight size={18} aria-hidden="true" />}
                {isLoading ? "Analyzing..." : form.job_url && !form.job_description.trim() ? "Fetch & Analyze Job" : "Analyze Job"}
              </button>
            </div>
          </form>

          <aside className="surface rounded-lg p-6">
            <p className="label">Job review</p>
            <h2 className="mt-3 text-2xl font-black text-white">What we check</h2>
            <div className="mt-6 space-y-4">
              {[
                ["Company and link review", "Looks for official hiring links, suspicious contact methods, and payment requests."],
                ["Remote clarity", "Checks whether the role is fully remote or has office, hybrid, timezone, or country limits."],
                ["Applicant fit", "Compares location and authorization requirements with the selected applicant country."],
                ["Job quality", "Looks for clear responsibilities, skills, pay, benefits, and hiring process details."]
              ].map(([title, body], index) => (
                <div key={title} className="flex gap-4 rounded-lg border border-line bg-white/[0.04] p-4">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-cyan/[0.10] text-sm font-black text-cyan">{index + 1}</div>
                  <div>
                    <div className="font-semibold text-white">{title}</div>
                    <p className="mt-1 text-sm leading-6 text-slate-400">{body}</p>
                  </div>
                </div>
              ))}
            </div>
          </aside>
        </div>

        {isLoading ? (
          <div className="mt-8 surface rounded-lg p-8 text-center">
            <Loader2 className="mx-auto animate-spin text-mint" size={32} aria-hidden="true" />
            <p className="mt-4 text-sm font-semibold text-slate-200">Checking the job details and trust indicators...</p>
          </div>
        ) : null}

        {result ? <div className="mt-8"><ResultsPanel result={result} /></div> : null}
      </div>
    </main>
  );
}
