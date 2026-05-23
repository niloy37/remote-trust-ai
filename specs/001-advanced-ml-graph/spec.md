# Feature Specification: Advanced ML Graph Verification

**Feature Branch**: `001-advanced-ml-graph`

**Created**: 2026-05-23

**Status**: Draft

**Input**: User description: "Extend RemoteTrust AI with an advanced ML classification and Neo4j graph verification layer. The system should classify job advertisements into LEGIT_REMOTE, COUNTRY_RESTRICTED_REMOTE, HYBRID_OR_LOCATION_BOUND, LOW_QUALITY_UNVERIFIED, and LIKELY_SCAM. Build a hybrid classifier pipeline: transformer text classifier for semantic job-post analysis; gradient boosting classifier using structured job/company/recruiter features; Neo4j graph verification layer connecting company, domain, recruiter email, ATS provider, job source, country restrictions, and apply URL; final meta-classifier that combines transformer probability, structured ML probability, rule score, and graph trust score. The system must expose explainable evidence for every prediction, including top red flags, positive signals, graph verification results, extracted remote restrictions, and confidence score. The feature must preserve local-first operation. If Neo4j or external verification is unavailable, the backend must fall back to existing rule-based and ML scoring. No paid API should be required for the baseline. Add training scripts, feature extraction modules, model evaluation, sample dataset format, API response updates, backend integration, and tests."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Classify a Job With Explainable Evidence (Priority: P1)

As a job seeker reviewing a remote posting, I want RemoteTrust AI to assign one
of the five trust categories and show the evidence behind the prediction so that
I can decide whether to apply, investigate, or avoid the job.

**Why this priority**: The primary value is a clearer, more specific verdict than
the existing broad trust score, with evidence that users can inspect.

**Independent Test**: Submit a representative job posting and verify the response
contains exactly one category, confidence score, top red flags, positive signals,
extracted remote restrictions, graph verification summary, and recommendation.

**Acceptance Scenarios**:

1. **Given** a legitimate globally remote posting with strong company evidence,
   **When** the user analyzes it, **Then** the system returns `LEGIT_REMOTE` with
   high confidence, positive signals, and evidence explaining why no country
   restriction was detected.
2. **Given** a posting that claims remote work but restricts applicants to a
   specific country, **When** the user analyzes it, **Then** the system returns
   `COUNTRY_RESTRICTED_REMOTE` and identifies the extracted restriction text.
3. **Given** a posting with scam indicators such as payment requests, personal
   email contact, or urgency pressure, **When** the user analyzes it, **Then** the
   system returns `LIKELY_SCAM` with red flags ranked by importance.

---

### User Story 2 - Verify Job Evidence Through Relationship Graphs (Priority: P2)

As a reviewer or job seeker, I want company, domain, recruiter, ATS, source,
country restriction, and apply URL relationships summarized so that I can see
whether the job posting is consistent with known hiring evidence.

**Why this priority**: Graph verification strengthens the trust decision by
connecting facts that isolated text scoring may miss.

**Independent Test**: Analyze postings with known company-domain-ATS
relationships and verify the graph summary shows matched, missing, conflicting,
or unavailable evidence without blocking classification.

**Acceptance Scenarios**:

1. **Given** a job posted on a recognized ATS with an apply URL matching the
   company domain, **When** the job is analyzed, **Then** graph verification
   reports supporting evidence and increases the trust explanation.
2. **Given** a recruiter email domain that does not match the company or apply
   URL, **When** the job is analyzed, **Then** graph verification reports the
   mismatch as a red flag.
3. **Given** graph verification is unavailable, **When** the job is analyzed,
   **Then** the user still receives a category, confidence score, rule evidence,
   and a clear "graph unavailable" status.

---

### User Story 3 - Train and Evaluate Classification Improvements (Priority: P3)

As a project maintainer, I want a documented sample dataset format, repeatable
training workflow, and evaluation report so that classification changes can be
measured before they affect users.

**Why this priority**: New classification behavior needs measurable quality gates
and a repeatable path for future labeled data.

**Independent Test**: Provide a sample labeled dataset and verify training and
evaluation produce classification metrics, confusion analysis for the five
categories, and saved artifacts that can be used by local analysis.

**Acceptance Scenarios**:

1. **Given** a labeled dataset in the documented format, **When** maintainers run
   training, **Then** the workflow validates required fields and reports class
   distribution before producing model artifacts.
2. **Given** held-out evaluation data, **When** evaluation runs, **Then** the
   report includes per-category precision, recall, F1, confusion matrix, and
   examples of misclassified postings.
3. **Given** no trained advanced artifacts are available locally, **When** the
   backend starts or analyzes a job, **Then** it falls back to the existing local
   scoring path without paid services.

### Edge Cases

- A posting contains contradictory remote language, such as "remote" in the
  title but "must be onsite three days per week" in the body.
- A posting has too little text to classify confidently.
- The company domain, recruiter email domain, and apply URL disagree.
- The posting appears on an ATS provider but the apply URL redirects or is
  missing.
- A posting is legitimate but country-restricted for legal, tax, or payroll
  reasons.
- Graph verification, public web verification, crawling, or optional enrichment
  is unavailable, blocked, timed out, or partially populated.
- The system cannot extract enough job content from a URL and asks the user to
  paste a description while preserving any source URL evidence already known.
- Model artifacts, training data, or graph seed data are missing in a local
  baseline environment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST classify each analyzed job into exactly one of
  `LEGIT_REMOTE`, `COUNTRY_RESTRICTED_REMOTE`, `HYBRID_OR_LOCATION_BOUND`,
  `LOW_QUALITY_UNVERIFIED`, or `LIKELY_SCAM`.
- **FR-002**: System MUST return a confidence score for every classification and
  indicate when confidence is reduced by missing, conflicting, or unavailable
  evidence.
- **FR-003**: System MUST expose user-visible evidence for every classification,
  including top red flags, positive signals, remote restrictions, and an
  explanation of the decision.
- **FR-004**: System MUST include graph verification results showing whether
  company, domain, recruiter email, ATS provider, job source, country
  restrictions, and apply URL evidence supports, conflicts with, or is unavailable
  for the prediction.
- **FR-005**: System MUST combine semantic text evidence, structured job and
  company features, existing rule-based score, and graph trust evidence into the
  final category and explanation.
- **FR-006**: System MUST preserve local operation without paid APIs or live LLM
  calls for the baseline classification path.
- **FR-007**: System MUST fall back to existing rule-based and local ML scoring
  when graph verification, external verification, or advanced model artifacts are
  unavailable.
- **FR-008**: System MUST extract and return remote-work restrictions, including
  eligible countries, excluded countries, timezone constraints, work
  authorization requirements, onsite or hybrid requirements, and ambiguous
  location language when present.
- **FR-009**: System MUST update saved job analysis records so historical results
  can display the new category, confidence, evidence, and graph verification
  status.
- **FR-010**: System MUST document a sample labeled dataset format covering raw
  job text, source metadata, company metadata, recruiter signals, remote
  restrictions, graph evidence fields, labels, and split information.
- **FR-011**: System MUST provide repeatable training and evaluation workflows
  that validate dataset fields, train all required local baseline artifacts, and
  report per-category quality metrics.
- **FR-012**: System MUST surface classification and graph evidence through the
  analysis response and job detail response without removing existing score
  fields used by current dashboard flows.
- **FR-013**: System MUST include tests covering category assignment, evidence
  completeness, fallback behavior, graph verification outcomes, dataset
  validation, and evaluation reporting.
- **FR-014**: System MUST expose clear status values when a layer is skipped,
  unavailable, degraded, or using fallback evidence.
- **FR-015**: System MUST avoid storing secrets in datasets, model artifacts,
  graph seed data, logs, or API responses.

### Key Entities *(include if feature involves data)*

- **Job Classification**: The final category, confidence, recommendation,
  contributing layer scores, and evidence shown for an analyzed job.
- **Classification Evidence**: Ranked red flags, positive signals, remote
  restrictions, source facts, and explanation text tied to a prediction.
- **Graph Verification Result**: Relationship evidence linking company, domain,
  recruiter email, ATS provider, job source, country restrictions, and apply URL,
  including support, conflict, unknown, or unavailable statuses.
- **Structured Feature Record**: Normalized job, company, recruiter, source, and
  restriction fields used for local classification and evaluation.
- **Labeled Training Example**: A job posting and associated metadata with a
  human-reviewed target category, split assignment, and optional notes.
- **Evaluation Report**: Metrics, confusion matrix, class distribution, and
  representative misclassifications for classification quality review.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of completed job analyses return one of the five
  categories, confidence, and evidence fields without requiring paid services.
- **SC-002**: 100% of category responses include at least one explanation item or
  an explicit "insufficient evidence" reason when evidence is sparse.
- **SC-003**: For a representative validation set, every category reports
  precision, recall, and F1, and no category is omitted from the evaluation
  output.
- **SC-004**: When graph verification is unavailable, users still receive a
  completed classification in at least 99% of analyses that have enough job text
  for the existing scoring path.
- **SC-005**: Country-restricted and hybrid/location-bound examples in the sample
  dataset identify extracted restriction evidence in at least 90% of manually
  reviewed cases.
- **SC-006**: Existing analyze, dashboard, job detail, sample seeding, and
  feedback flows continue to work with saved jobs created before this feature.

## Assumptions

- The five requested categories are mutually exclusive, and the final response
  will choose the strongest category while preserving secondary evidence in the
  explanation.
- Local baseline operation may use prepackaged or previously trained artifacts,
  but it must not require a paid API, live LLM call, or available graph service.
- Neo4j and public web search may be unavailable; SQLite/local fallbacks and the
  existing rule-based scorer remain in scope.
- The existing numeric trust score remains available for compatibility while the
  new category becomes the primary classification label.
- Training and evaluation workflows are maintainer-facing and may operate on
  sample data before a larger human-labeled dataset exists.
- API consumers can tolerate additive response fields as long as existing fields
  are preserved.
