"use client";

import Link from "next/link";
import { BadgeCheck, BriefcaseBusiness, CheckCircle2, ExternalLink, Flag, Globe2, MapPinned, MessageSquareText, Sparkles, ThumbsDown, ThumbsUp, XCircle } from "lucide-react";
import { useState } from "react";
import { sendFeedback } from "@/lib/api";
import type { AnalysisResponse, FeedbackValue } from "@/lib/types";
import { ScoreCard } from "@/components/ScoreCard";
import { ScoreRing } from "@/components/ScoreRing";
import { VerdictBadge } from "@/components/VerdictBadge";

interface ResultsPanelProps {
  result: AnalysisResponse;
  showOpenResultLink?: boolean;
}

const scoreMeta = [
  ["legitimacy", "Legitimacy", "Company, contact, payment, links, and scam language."],
  ["remote_authenticity", "Remote Authenticity", "Whether remote work is real, clear, and office-free."],
  ["global_eligibility", "Global Eligibility", "Country access, authorization, timezone, and residency limits."],
  ["job_quality", "Job Quality", "Role clarity, skills, compensation, benefits, and hiring process."]
] as const;

function titleValidationClass(verdict: string) {
  if (verdict === "Recognized" || verdict === "Plausible") return "border-mint/30 bg-mint/[0.10] text-mint";
  if (verdict === "Unusual") return "border-amber/30 bg-amber/[0.10] text-amber";
  return "border-rose/30 bg-rose/[0.10] text-rose";
}

function companyVerificationClass(status: string) {
  if (status === "Strong evidence" || status === "Some evidence") return "border-mint/30 bg-mint/[0.10] text-mint";
  if (status === "Risk signals") return "border-rose/30 bg-rose/[0.10] text-rose";
  return "border-amber/30 bg-amber/[0.10] text-amber";
}

function classificationClass(label: string) {
  if (label === "LEGIT_REMOTE") return "border-mint/30 bg-mint/[0.10] text-mint";
  if (label === "LIKELY_SCAM") return "border-rose/30 bg-rose/[0.10] text-rose";
  if (label === "COUNTRY_RESTRICTED_REMOTE" || label === "HYBRID_OR_LOCATION_BOUND") return "border-amber/30 bg-amber/[0.10] text-amber";
  return "border-cyan/30 bg-cyan/[0.10] text-cyan";
}

function readableLabel(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

function readableSourceType(value: string) {
  return value.replaceAll("_", " ");
}

function extractionQuality(result: AnalysisResponse): { label: string; tone: string; detail: string } {
  const confidence = result.extracted.company_confidence ?? 0;
  if (result.extraction_warnings.length || !result.extracted.company) {
    return {
      label: "Limited",
      tone: "text-amber",
      detail: result.extraction_warnings[0] || "Company extraction needs review"
    };
  }
  if (confidence >= 0.9) {
    return { label: "High", tone: "text-mint", detail: "Structured company evidence" };
  }
  if (confidence >= 0.7) {
    return { label: "Good", tone: "text-cyan", detail: "Company evidence is usable" };
  }
  return { label: "Review", tone: "text-amber", detail: "Low company confidence" };
}

function detailRows(result: AnalysisResponse): Array<[string, string]> {
  const extracted = result.extracted;
  const companyConfidence =
    extracted.company_confidence === null || extracted.company_confidence === undefined
      ? "Not available"
      : `${Math.round(extracted.company_confidence * 100)}%`;
  return [
    ["Job title", extracted.job_title || "Not detected"],
    ["Company", extracted.company || "Not detected"],
    ["Company confidence", companyConfidence],
    ["Company evidence", extracted.company_evidence || "Not available"],
    ["Salary", extracted.salary || "Not disclosed"],
    ["Location", extracted.location || "Not detected"],
    ["Remote type", extracted.remote_type || "Unclear"],
    ["Allowed countries", extracted.allowed_countries.length ? extracted.allowed_countries.join(", ") : "No explicit restriction detected"],
    ["Timezone", extracted.timezone_requirements || "Not specified"],
    ["Work authorization", extracted.work_authorization || "Not specified"],
    ["Apply URL", extracted.apply_url || "Not detected"]
  ];
}

export function ResultsPanel({ result, showOpenResultLink = true }: ResultsPanelProps) {
  const [feedbackStatus, setFeedbackStatus] = useState<string>("");
  const [isSending, setIsSending] = useState(false);
  const extraction = extractionQuality(result);

  async function handleFeedback(user_feedback: FeedbackValue) {
    setIsSending(true);
    setFeedbackStatus("");
    try {
      await sendFeedback({ job_id: result.job_id, user_feedback, notes: null });
      setFeedbackStatus("Feedback saved. This will help improve the scoring loop.");
    } catch (error) {
      setFeedbackStatus(error instanceof Error ? error.message : "Could not save feedback.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="surface rounded-lg p-6 sm:p-8">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <ScoreRing score={result.final_score} />
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <VerdictBadge verdict={result.verdict} />
                <span className={`rounded-full border px-3 py-1.5 text-sm font-bold ${classificationClass(result.classification.label)}`}>
                  {readableLabel(result.classification.label)}
                </span>
                <span className="rounded-full border border-line bg-white/[0.06] px-3 py-1.5 text-sm font-semibold text-slate-200">
                  Recommended: {result.recommended_action}
                </span>
              </div>
              <h2 className="mt-5 text-2xl font-black text-white sm:text-3xl">Remote job trust analysis</h2>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">{result.explanation}</p>
              {result.extraction_warnings.length ? (
                <ul className="mt-4 max-w-2xl space-y-2">
                  {result.extraction_warnings.slice(0, 3).map((warning) => (
                    <li key={warning} className="rounded-lg border border-amber/30 bg-amber/[0.08] p-3 text-sm leading-6 text-amber">
                      {warning}
                    </li>
                  ))}
                </ul>
              ) : null}
              {showOpenResultLink ? (
                <Link href={`/results/${result.job_id}`} className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-mint hover:text-emerald-200">
                  Open shareable result <ExternalLink size={16} aria-hidden="true" />
                </Link>
              ) : null}
            </div>
          </div>
          <div className="grid min-w-64 grid-cols-2 gap-3 rounded-lg border border-line bg-white/[0.04] p-3 text-center sm:grid-cols-4 lg:grid-cols-2">
            <div>
              <div className="text-xl font-black text-mint">{result.positive_signals.length}</div>
              <div className="text-xs text-slate-400">Signals</div>
            </div>
            <div>
              <div className="text-xl font-black text-rose">{result.red_flags.length}</div>
              <div className="text-xs text-slate-400">Flags</div>
            </div>
            <div>
              <div className="text-xl font-black text-cyan">{Math.round(result.classification.confidence * 100)}%</div>
              <div className="text-xs text-slate-400">Confidence</div>
            </div>
            <div>
              <div className={`text-xl font-black ${extraction.tone}`}>{extraction.label}</div>
              <div className="text-xs text-slate-400">Extraction</div>
            </div>
          </div>
        </div>
      </div>

      <section className="surface rounded-lg p-6">
        <div className="flex items-center gap-2 text-cyan">
          <BadgeCheck size={18} aria-hidden="true" />
          <h3 className="font-bold text-white">Advanced classification</h3>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-lg border border-line bg-white/[0.04] p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Prediction</div>
            <div className="mt-2 text-xl font-black text-white">{readableLabel(result.classification.label)}</div>
            <div className="mt-2 text-sm text-slate-300">{Math.round(result.classification.confidence * 100)}% confidence</div>
            <p className="mt-3 text-sm leading-6 text-slate-400">{result.classification.evidence.explanation}</p>
            {result.classification.fallback_reason ? (
              <p className="mt-3 rounded-lg border border-amber/20 bg-amber/[0.08] p-3 text-xs leading-5 text-amber">
                {result.classification.fallback_reason}
              </p>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(result.classification.layer_scores).map(([name, layer]) => (
              <div key={name} className="rounded-lg border border-line bg-white/[0.04] p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{name.replaceAll("_", " ")}</div>
                <div className="mt-2 text-sm font-bold text-white">{layer.status}</div>
                <div className="mt-1 text-sm text-slate-400">
                  {layer.score === null || layer.score === undefined ? "No score" : `${Math.round(layer.score * 100)}% layer score`}
                </div>
                {layer.reason ? <p className="mt-2 text-xs leading-5 text-slate-500">{layer.reason}</p> : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {scoreMeta.map(([key, title, description]) => (
          <ScoreCard key={key} title={title} description={description} score={result.scores[key]} />
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="surface rounded-lg p-6">
          <div className="flex items-center gap-2 text-rose">
            <Flag size={18} aria-hidden="true" />
            <h3 className="font-bold text-white">Red flags</h3>
          </div>
          <ul className="mt-4 space-y-3">
            {(result.red_flags.length ? result.red_flags : ["No major red flags detected."]).map((flag) => (
              <li key={flag} className="flex gap-3 rounded-lg border border-line bg-white/[0.04] p-3 text-sm leading-6 text-slate-300">
                <XCircle className="mt-0.5 shrink-0 text-rose" size={17} aria-hidden="true" />
                <span>{flag}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="surface rounded-lg p-6">
          <div className="flex items-center gap-2 text-mint">
            <Sparkles size={18} aria-hidden="true" />
            <h3 className="font-bold text-white">Positive trust signals</h3>
          </div>
          <ul className="mt-4 space-y-3">
            {(result.positive_signals.length ? result.positive_signals : ["Limited positive signals detected."]).map((signal) => (
              <li key={signal} className="flex gap-3 rounded-lg border border-line bg-white/[0.04] p-3 text-sm leading-6 text-slate-300">
                <CheckCircle2 className="mt-0.5 shrink-0 text-mint" size={17} aria-hidden="true" />
                <span>{signal}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="surface rounded-lg p-6">
          <div className="flex items-center gap-2 text-cyan">
            <BriefcaseBusiness size={18} aria-hidden="true" />
            <h3 className="font-bold text-white">Extracted job details</h3>
          </div>
          <div className="mt-5 rounded-lg border border-line bg-white/[0.04] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Extraction quality</div>
                <div className="mt-2 text-sm font-semibold text-white">{extraction.detail}</div>
              </div>
              <span className={`rounded-full border border-line bg-white/[0.06] px-3 py-1.5 text-xs font-bold ${extraction.tone}`}>
                {extraction.label}
              </span>
            </div>
          </div>
          <div className="mt-4 rounded-lg border border-line bg-white/[0.04] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Job title legitimacy</div>
                <div className="mt-2 text-sm font-semibold text-white">
                  {result.title_validation.normalized_title || result.title_validation.original_title || "No title detected"}
                </div>
              </div>
              <span className={`rounded-full border px-3 py-1.5 text-xs font-bold ${titleValidationClass(result.title_validation.verdict)}`}>
                {result.title_validation.verdict} - {result.title_validation.score}/100
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              {(result.title_validation.evidence[0] || result.title_validation.warnings[0] || "No title validation evidence available.")}
            </p>
            {result.title_validation.closest_known_titles.length ? (
              <p className="mt-2 text-xs text-slate-500">Closest known title: {result.title_validation.closest_known_titles[0]}</p>
            ) : null}
          </div>
          <div className="mt-4 rounded-lg border border-line bg-white/[0.04] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  <Globe2 size={14} aria-hidden="true" /> Company web verification
                </div>
                <div className="mt-2 text-sm font-semibold text-white">
                  {result.company_verification.company || result.extracted.company || "Company not detected"}
                </div>
              </div>
              <span className={`rounded-full border px-3 py-1.5 text-xs font-bold ${companyVerificationClass(result.company_verification.status)}`}>
                {result.company_verification.status} - {result.company_verification.score}/100
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              {result.company_verification.signals[0] || result.company_verification.warnings[0] || "No live web evidence available yet."}
            </p>
            {result.company_verification.sources.length ? (
              <div className="mt-4 space-y-2">
                {result.company_verification.sources.slice(0, 3).map((source) => (
                  <a
                    key={source.url}
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="block rounded-lg border border-line bg-ink/40 p-3 transition hover:border-cyan/40"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="text-sm font-semibold text-cyan">{source.title}</span>
                      <ExternalLink size={14} className="mt-0.5 shrink-0 text-slate-500" aria-hidden="true" />
                    </div>
                    <div className="mt-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{readableSourceType(source.source_type)}</div>
                    {source.snippet ? <p className="mt-2 text-xs leading-5 text-slate-400">{source.snippet}</p> : null}
                  </a>
                ))}
              </div>
            ) : null}
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-line bg-white/[0.04] p-4 sm:col-span-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                <MapPinned size={14} aria-hidden="true" /> Remote restrictions
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="text-xs text-slate-500">Allowed countries</div>
                  <div className="mt-1 text-sm font-medium text-slate-100">
                    {result.classification.evidence.remote_restrictions.allowed_countries.length
                      ? result.classification.evidence.remote_restrictions.allowed_countries.join(", ")
                      : "No explicit country allowlist"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Excluded countries</div>
                  <div className="mt-1 text-sm font-medium text-slate-100">
                    {result.classification.evidence.remote_restrictions.excluded_countries.length
                      ? result.classification.evidence.remote_restrictions.excluded_countries.join(", ")
                      : "No explicit country exclusion"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Timezone</div>
                  <div className="mt-1 text-sm font-medium text-slate-100">
                    {result.classification.evidence.remote_restrictions.timezone_requirements || "Not specified"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Hybrid or onsite</div>
                  <div className="mt-1 text-sm font-medium text-slate-100">
                    {result.classification.evidence.remote_restrictions.onsite_or_hybrid_requirement || "No onsite requirement detected"}
                  </div>
                </div>
              </div>
              {result.classification.evidence.remote_restrictions.source_snippets.length ? (
                <ul className="mt-4 space-y-2">
                  {result.classification.evidence.remote_restrictions.source_snippets.slice(0, 3).map((snippet) => (
                    <li key={snippet} className="rounded-lg border border-line bg-ink/40 p-3 text-xs leading-5 text-slate-400">{snippet}</li>
                  ))}
                </ul>
              ) : null}
            </div>
            {detailRows(result).map(([label, value]) => (
              <div key={label} className="rounded-lg border border-line bg-white/[0.04] p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
                <div className="mt-2 break-words text-sm font-medium text-slate-100">{value}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="surface rounded-lg p-6">
          <div className="flex items-center gap-2 text-amber">
            <MessageSquareText size={18} aria-hidden="true" />
            <h3 className="font-bold text-white">Would you apply?</h3>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-400">Save feedback for the demo feedback loop and future active learning.</p>
          <div className="mt-5 grid gap-3">
            <button className="btn-secondary justify-start" disabled={isSending} onClick={() => handleFeedback("applied")}>
              <ThumbsUp size={17} aria-hidden="true" /> I would apply
            </button>
            <button className="btn-secondary justify-start" disabled={isSending} onClick={() => handleFeedback("not_apply")}>
              <ThumbsDown size={17} aria-hidden="true" /> I would not apply
            </button>
            <button className="btn-secondary justify-start" disabled={isSending} onClick={() => handleFeedback("reported_suspicious")}>
              <Flag size={17} aria-hidden="true" /> Report suspicious
            </button>
            <button className="btn-secondary justify-start" disabled={isSending} onClick={() => handleFeedback("incorrect_score")}>
              <MessageSquareText size={17} aria-hidden="true" /> Score seems wrong
            </button>
          </div>
          {feedbackStatus ? <p className="mt-4 text-sm text-slate-300">{feedbackStatus}</p> : null}
        </section>
      </div>
    </section>
  );
}
