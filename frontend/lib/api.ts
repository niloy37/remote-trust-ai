import type {
  AnalysisResponse,
  AnalyzeRequest,
  FeedbackRequest,
  FeedbackResponse,
  IngestionQueueRequest,
  IngestionQueueResponse,
  IngestionRunSummary,
  IngestionStatusResponse,
  JobRecord,
  OpportunityFeedResponse
} from "@/lib/types";

const API_BASE_PATH = process.env.NEXT_PUBLIC_API_BASE_PATH || "/api/backend";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_PATH}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    }
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the status-based message when the response body is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function analyzeJob(payload: AnalyzeRequest): Promise<AnalysisResponse> {
  return request<AnalysisResponse>("/analyze", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getJobs(): Promise<JobRecord[]> {
  return request<JobRecord[]>("/jobs", { cache: "no-store" });
}

export function getOpportunities(): Promise<OpportunityFeedResponse> {
  return request<OpportunityFeedResponse>("/opportunities", { cache: "no-store" });
}

export function getJob(jobId: string): Promise<JobRecord> {
  return request<JobRecord>(`/jobs/${jobId}`, { cache: "no-store" });
}

export function runIngestion(): Promise<IngestionRunSummary> {
  return request<IngestionRunSummary>("/ingestion/run", {
    method: "POST"
  });
}

export function getIngestionStatus(): Promise<IngestionStatusResponse> {
  return request<IngestionStatusResponse>("/ingestion/status", { cache: "no-store" });
}

export function queueIngestionUrl(payload: IngestionQueueRequest): Promise<IngestionQueueResponse> {
  return request<IngestionQueueResponse>("/ingestion/queue", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function sendFeedback(payload: FeedbackRequest): Promise<FeedbackResponse> {
  return request<FeedbackResponse>("/feedback", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
