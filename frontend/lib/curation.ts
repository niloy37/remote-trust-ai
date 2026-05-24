import type { JobRecord } from "@/lib/types";

export type OpportunityBucket = "curated" | "review" | "rejected";
export type EligibilityFilter = "All" | "Worldwide" | "Applicant match" | "Restricted" | "Unclear";
export type ScoreFilter = "All" | "80+" | "60-79" | "<60";
export type EvidenceFilter = "All" | "Strong evidence" | "Some evidence" | "Limited evidence" | "Risk signals";

const rejectedLabels = new Set(["LIKELY_SCAM", "HYBRID_OR_LOCATION_BOUND"]);

function textIncludesCountry(value: string, country: string) {
  return value.toLowerCase().includes(country.toLowerCase());
}

function unique(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((value) => (value || "").trim()).filter(Boolean)));
}

export function curationBucket(job: JobRecord): OpportunityBucket {
  const label = job.classification?.label;
  const isRejected =
    job.recommended_action === "Avoid" ||
    job.verdict === "Risky" ||
    job.final_score < 60 ||
    Boolean(label && rejectedLabels.has(label));

  if (isRejected) return "rejected";

  const needsReview =
    job.verdict === "Caution" ||
    job.recommended_action === "Review carefully" ||
    label === "COUNTRY_RESTRICTED_REMOTE" ||
    label === "LOW_QUALITY_UNVERIFIED";

  if (needsReview) return "review";

  return job.recommended_action === "Apply" || job.final_score >= 80 ? "curated" : "review";
}

export function allowedCountries(job: JobRecord) {
  return unique([
    ...(job.extracted.allowed_countries || []),
    ...(job.classification?.evidence?.remote_restrictions?.allowed_countries || [])
  ]);
}

export function isWorldwideEligible(job: JobRecord) {
  return allowedCountries(job).some((country) => /worldwide|global|anywhere|all countries/i.test(country));
}

export function isRestricted(job: JobRecord) {
  const allowed = allowedCountries(job);
  const restrictions = job.classification?.evidence?.remote_restrictions;
  return (
    job.classification?.label === "COUNTRY_RESTRICTED_REMOTE" ||
    Boolean(restrictions?.work_authorization) ||
    Boolean(restrictions?.timezone_requirements) ||
    Boolean(restrictions?.excluded_countries?.length) ||
    Boolean(allowed.length && !isWorldwideEligible(job))
  );
}

export function eligibilityCategory(job: JobRecord): EligibilityFilter {
  const allowed = allowedCountries(job);
  const excluded = job.classification?.evidence?.remote_restrictions?.excluded_countries || [];
  if (isWorldwideEligible(job)) return "Worldwide";
  if (excluded.some((country) => textIncludesCountry(country, job.applicant_country))) return "Restricted";
  if (allowed.some((country) => textIncludesCountry(country, job.applicant_country))) return "Applicant match";
  if (isRestricted(job)) return "Restricted";
  return "Unclear";
}

export function globalFitLens(job: JobRecord) {
  const restrictions = job.classification?.evidence?.remote_restrictions;
  const allowed = allowedCountries(job);
  const excluded = restrictions?.excluded_countries || [];

  if (restrictions?.onsite_or_hybrid_requirement) return "Location-bound or hybrid";
  if (isWorldwideEligible(job)) {
    return restrictions?.timezone_requirements ? `Worldwide, ${restrictions.timezone_requirements}` : "Worldwide eligible";
  }
  if (excluded.some((country) => textIncludesCountry(country, job.applicant_country))) return `${job.applicant_country} excluded`;
  if (allowed.some((country) => textIncludesCountry(country, job.applicant_country))) return `Good for applicants in ${job.applicant_country}`;
  if (allowed.length) return `${allowed.slice(0, 2).join(", ")} only`;
  if (restrictions?.work_authorization) return restrictions.work_authorization;
  if (restrictions?.timezone_requirements) return restrictions.timezone_requirements;
  return "Eligibility unclear";
}

export function trustPassportSignal(job: JobRecord, bucket: OpportunityBucket) {
  const label = job.classification?.label;
  if (bucket === "rejected") {
    if (label === "HYBRID_OR_LOCATION_BOUND") return "the remote claim conflicts with hybrid or location-bound requirements";
    if (label === "LIKELY_SCAM") return "the posting matches scam-like hiring patterns";
    if (job.recommended_action === "Avoid") return "the recommendation is to avoid this posting";
    if (job.verdict === "Risky" || job.final_score < 60) return "the trust score is below the safe shortlist threshold";
    return job.red_flags[0] || job.classification?.evidence?.top_red_flags?.[0] || "Risk signals outweighed positive evidence";
  }
  if (bucket === "review") {
    if (label === "COUNTRY_RESTRICTED_REMOTE") return "the role has country, authorization, or timezone restrictions";
    if (label === "LOW_QUALITY_UNVERIFIED") return "the posting needs stronger quality or verification evidence";
    return (
      job.red_flags[0] ||
      job.classification?.evidence?.remote_restrictions?.source_snippets?.[0] ||
      job.classification?.evidence?.confidence_factors?.[0] ||
      "Useful opportunity, but some evidence needs review"
    );
  }
  return (
    job.positive_signals[0] ||
    job.company_verification.signals[0] ||
    job.classification?.evidence?.positive_signals?.[0] ||
    "Strong score across trust, remote, eligibility, and quality checks"
  );
}

export function whyThisJob(job: JobRecord, bucket: OpportunityBucket) {
  const signal = trustPassportSignal(job, bucket);
  if (bucket === "curated") return `Vetted because ${signal.toLowerCase()}.`;
  if (bucket === "review") return `Review because ${signal.toLowerCase()}.`;
  return `Removed because ${signal.toLowerCase()}.`;
}

export function scoreFilterMatches(job: JobRecord, filter: ScoreFilter) {
  if (filter === "80+") return job.final_score >= 80;
  if (filter === "60-79") return job.final_score >= 60 && job.final_score < 80;
  if (filter === "<60") return job.final_score < 60;
  return true;
}

export function evidenceFilterMatches(job: JobRecord, filter: EvidenceFilter) {
  return filter === "All" || job.company_verification.status === filter;
}
