import type { AnalysisResponse, JobRecord } from "@/lib/types";

export function validApplyLink(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export function applyLinkFor(job: AnalysisResponse | JobRecord): string | null {
  const jobUrl = "job_url" in job ? job.job_url : null;
  return validApplyLink(job.extracted.apply_url) || validApplyLink(jobUrl);
}
