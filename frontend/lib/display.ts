import type { ClassificationLabel, Verdict } from "@/lib/types";

export const CLASSIFICATION_DISPLAY_LABELS: Record<ClassificationLabel, string> = {
  LEGIT_REMOTE: "Looks Trustworthy",
  COUNTRY_RESTRICTED_REMOTE: "Location Requirements",
  HYBRID_OR_LOCATION_BOUND: "Not Fully Remote",
  LOW_QUALITY_UNVERIFIED: "Needs More Evidence",
  LIKELY_SCAM: "High Risk"
};

const classifierPhraseMap: Array<[RegExp, string]> = [
  [/\bLEGIT_REMOTE\b|\bLegit Remote\b/gi, CLASSIFICATION_DISPLAY_LABELS.LEGIT_REMOTE],
  [/\bCOUNTRY_RESTRICTED_REMOTE\b|\bCountry Restricted Remote\b/gi, CLASSIFICATION_DISPLAY_LABELS.COUNTRY_RESTRICTED_REMOTE],
  [/\bHYBRID_OR_LOCATION_BOUND\b|\bHybrid Or Location Bound\b/gi, CLASSIFICATION_DISPLAY_LABELS.HYBRID_OR_LOCATION_BOUND],
  [/\bLOW_QUALITY_UNVERIFIED\b|\bLow Quality Unverified\b/gi, CLASSIFICATION_DISPLAY_LABELS.LOW_QUALITY_UNVERIFIED],
  [/\bLIKELY_SCAM\b|\bLikely Scam\b/gi, CLASSIFICATION_DISPLAY_LABELS.LIKELY_SCAM]
];

const technicalDiagnosticPatterns = [
  /\bNeo4j\b/i,
  /\bSQLite\b/i,
  /\blocal .*backend\b/i,
  /\bRemoteTrust AI backend\b/i,
  /\bbackend returned\b/i,
  /\btraceback\b/i,
  /\bstack trace\b/i,
  /\bmodule not found\b/i,
  /\brequest failed with status\b/i,
  /\bgraph database unavailable\b/i,
  /\bgraph backend unavailable\b/i,
  /\brelationship memory\b/i,
  /\btrained artifacts?\b/i,
  /\btransformer artifact\b/i,
  /\bstructured ML artifact\b/i,
  /\bmeta-classifier\b/i,
  /\blayer_scores?\b/i,
  /\bprobabilities\b/i,
  /\bfallback\b/i
];

export const SCORE_TOOLTIPS = {
  legitimacy: "Checks company identity, contact details, application links, and suspicious requests.",
  remote_authenticity: "Checks whether the role appears genuinely remote and office-free.",
  global_eligibility: "Checks country, timezone, and work authorization fit for the applicant.",
  job_quality: "Checks role clarity, skills, compensation, benefits, and hiring process details."
} as const;

export function displayVerdict(verdict: Verdict | string | null | undefined): string {
  return verdict === "Caution" ? "Proceed with Caution" : verdict || "Review Needed";
}

export function displayClassificationLabel(label: string | null | undefined): string {
  if (!label) return "Review Needed";
  return CLASSIFICATION_DISPLAY_LABELS[label as ClassificationLabel] || toTitleCase(label);
}

export function isTechnicalDiagnostic(value: string | null | undefined): boolean {
  const text = value || "";
  return technicalDiagnosticPatterns.some((pattern) => pattern.test(text));
}

export function sanitizeUserText(value: string | null | undefined, fallback = ""): string {
  if (!value) return fallback;
  if (isTechnicalDiagnostic(value)) return fallback;

  let text = value;
  classifierPhraseMap.forEach(([pattern, replacement]) => {
    text = text.replace(pattern, replacement);
  });

  return text
    .replace(/Company extraction confidence was [\d.]+/gi, "Company details need another look")
    .replace(/\s+with\s+\d+%\s+confidence(?=\.)/gi, "")
    .replace(/\s+with\s+\d+%\s+confidence\b/gi, "")
    .replace(/\b\d+%\s+confidence\b/gi, "supporting evidence")
    .replace(/\bconfidence\b/gi, "evidence")
    .replace(/\s{2,}/g, " ")
    .trim() || fallback;
}

export function cleanEvidenceItems(items: string[] | undefined, emptyText: string): string[] {
  const cleaned = Array.from(
    new Set(
      (items || [])
        .filter((item) => !isTechnicalDiagnostic(item))
        .map((item) => sanitizeUserText(item))
        .filter(Boolean)
    )
  );
  return cleaned.length ? cleaned : [emptyText];
}

export function friendlyErrorMessage(error: unknown, fallback = "We could not complete that request right now. Please try again."): string {
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : "";

  if (!message) return fallback;
  if (/provide either a job url or a job description/i.test(message)) {
    return "Paste a job URL or job description before analyzing.";
  }
  if (/protected|blocked|search\/list|collection|could not fetch|crawler/i.test(message)) {
    return "We could not read that job page directly. Paste the job description text and try again.";
  }
  if (isTechnicalDiagnostic(message) || /status\s+\d+|failed to fetch|network/i.test(message)) {
    return fallback;
  }

  return sanitizeUserText(message, fallback);
}

function toTitleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
