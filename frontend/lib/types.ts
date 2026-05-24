export type Verdict = "Verified" | "Caution" | "Risky";
export type RecommendedAction = "Apply" | "Review carefully" | "Avoid";
export type FeedbackValue = "applied" | "not_apply" | "reported_suspicious" | "incorrect_score";
export type ClassificationLabel =
  | "LEGIT_REMOTE"
  | "COUNTRY_RESTRICTED_REMOTE"
  | "HYBRID_OR_LOCATION_BOUND"
  | "LOW_QUALITY_UNVERIFIED"
  | "LIKELY_SCAM";
export type LayerStatus = "available" | "skipped" | "unavailable" | "degraded";

export interface AnalyzeRequest {
  job_url: string | null;
  job_description: string;
  applicant_country: string;
  desired_role: string | null;
}

export interface Scores {
  legitimacy: number;
  remote_authenticity: number;
  global_eligibility: number;
  job_quality: number;
}

export interface ExtractedJob {
  job_title: string | null;
  company: string | null;
  company_confidence: number | null;
  company_evidence: string | null;
  salary: string | null;
  location: string | null;
  remote_type: string | null;
  allowed_countries: string[];
  timezone_requirements: string | null;
  work_authorization: string | null;
  apply_url: string | null;
}

export type TitleValidationVerdict = "Recognized" | "Plausible" | "Unusual" | "Suspicious";

export interface TitleValidation {
  original_title: string | null;
  normalized_title: string | null;
  verdict: TitleValidationVerdict;
  score: number;
  closest_known_titles: string[];
  evidence: string[];
  warnings: string[];
}

export type CompanyVerificationStatus = "Strong evidence" | "Some evidence" | "Limited evidence" | "Risk signals";

export interface WebSource {
  title: string;
  url: string;
  snippet: string;
  source_type: string;
}

export interface CompanyVerification {
  company: string | null;
  status: CompanyVerificationStatus;
  score: number;
  searched_at: string;
  search_queries: string[];
  signals: string[];
  warnings: string[];
  sources: WebSource[];
}

export type GraphVerificationStatus = "Strong graph evidence" | "Some graph evidence" | "Limited graph evidence" | "Risk signals";

export interface GraphNode {
  id: string;
  kind: string;
  name: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  evidence: string | null;
}

export interface GraphRelationshipEvidence {
  source_kind: string;
  source_value: string;
  target_kind: string;
  target_value: string;
  relationship_type: string;
  status: "supports" | "conflicts" | "unknown";
  evidence: string | null;
}

export interface GraphVerification {
  status: GraphVerificationStatus;
  score: number;
  entity_confidence: number;
  relationship_status: string | null;
  fallback_backend: "neo4j" | "sqlite" | "none" | null;
  relationships: GraphRelationshipEvidence[];
  signals: string[];
  warnings: string[];
  evidence_paths: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface LayerScore {
  status: LayerStatus;
  probabilities: Partial<Record<ClassificationLabel, number>>;
  score: number | null;
  evidence: string[];
  reason: string | null;
}

export interface RemoteRestrictionEvidence {
  allowed_countries: string[];
  excluded_countries: string[];
  timezone_requirements: string | null;
  work_authorization: string | null;
  onsite_or_hybrid_requirement: string | null;
  ambiguous_location_language: string[];
  source_snippets: string[];
}

export interface ClassificationEvidence {
  top_red_flags: string[];
  positive_signals: string[];
  remote_restrictions: RemoteRestrictionEvidence;
  graph_summary: Record<string, unknown>;
  confidence_factors: string[];
  explanation: string;
}

export interface JobClassification {
  label: ClassificationLabel;
  confidence: number;
  recommendation: string;
  layer_scores: Record<string, LayerScore>;
  evidence: ClassificationEvidence;
  status: "complete" | "degraded" | "fallback";
  fallback_reason: string | null;
}

export interface AnalysisResponse {
  job_id: string;
  final_score: number;
  verdict: Verdict;
  scores: Scores;
  extracted: ExtractedJob;
  title_validation: TitleValidation;
  company_verification: CompanyVerification;
  graph_verification?: GraphVerification;
  classification: JobClassification;
  red_flags: string[];
  positive_signals: string[];
  extraction_warnings: string[];
  explanation: string;
  recommended_action: RecommendedAction;
}

export interface JobRecord extends AnalysisResponse {
  job_url: string | null;
  job_description: string;
  applicant_country: string;
  desired_role: string | null;
  created_at: string;
}

export interface FeedbackRequest {
  job_id: string;
  user_feedback: FeedbackValue;
  notes: string | null;
}

export interface FeedbackResponse extends FeedbackRequest {
  id: string;
  created_at: string;
}
