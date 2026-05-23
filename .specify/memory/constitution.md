<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- Template principle 1 -> I. Local-First Trust Scoring
- Template principle 2 -> II. Evidence Traceability
- Template principle 3 -> III. Testable User-Slice Delivery
- Template principle 4 -> IV. Privacy and Consent by Default
- Template principle 5 -> V. Resilient, Observable Integrations
Added sections:
- Product and Technology Constraints
- Delivery Workflow and Quality Gates
Removed sections:
- Placeholder SECTION_2_NAME
- Placeholder SECTION_3_NAME
Templates requiring updates:
- Updated: .specify/templates/plan-template.md
- Updated: .specify/templates/spec-template.md
- Updated: .specify/templates/tasks-template.md
- Not present: .specify/templates/commands/*.md
Runtime guidance reviewed:
- Reviewed: README.md
- Reviewed: AGENTS.md
- Reviewed: docs/demo_script.md
- Reviewed: docs/pipeline.md
- Reviewed: docs/pitch.md
Follow-up TODOs:
- None
-->
# RemoteTrust AI Constitution

## Core Principles

### I. Local-First Trust Scoring
RemoteTrust AI MUST remain useful without paid APIs or live LLM calls. Core job
analysis, scoring, title validation, persistence, seeding, and demo workflows MUST
run locally with the documented Next.js frontend, FastAPI backend, SQLite storage,
and optional graph backend. External services MAY enrich evidence only when they
fail gracefully, preserve deterministic local fallback behavior, and do not block
the primary analyze, list, detail, or feedback flows.

Rationale: The product promise is a hackathon MVP that can be demonstrated,
tested, and trusted end-to-end on a local machine.

### II. Evidence Traceability
Every trust verdict MUST expose the signals that shaped it, including red flags,
positive signals, score components, extracted job facts, company verification
status, and graph-derived evidence when available. Features that change scoring
or extraction MUST define how users and reviewers can trace the result from input
text or URL to final verdict. Hidden scoring adjustments, unexplained confidence
changes, and unverifiable labels are not acceptable.

Rationale: Remote job applicants need clear evidence, not only a numeric score.
Traceability also makes model and rule changes reviewable.

### III. Testable User-Slice Delivery
Work MUST be organized as independently testable user slices that preserve the
existing analyze, dashboard, job detail, seed data, and feedback workflows unless
the feature explicitly replaces them. Backend changes MUST include focused tests
for scoring, extraction, API contracts, or persistence when behavior changes.
Frontend changes MUST include verification of the affected user path. Chrome
extension changes MUST preserve explicit user consent before page extraction.

Rationale: The system spans frontend, API, local ML/rules, persistence, and an
extension; isolated changes still need end-to-end confidence at the user path.

### IV. Privacy and Consent by Default
User-provided job descriptions, active browser page content, feedback, and source
URLs MUST be handled as user-controlled data. The Chrome extension MUST read job
page content only after explicit consent in the popup. New data collection MUST
document what is stored, where it is stored, and how it affects scoring or
feedback. Secrets and API keys MUST remain optional configuration and MUST NOT be
committed or required for the local baseline.

Rationale: The product analyzes employment opportunities and browser content, so
privacy expectations must be explicit and testable.

### V. Resilient, Observable Integrations
URL crawling, public web verification, ATS extraction, Neo4j graph integration,
and optional external enrichment MUST degrade to clear user-facing fallbacks when
blocked, unavailable, or timed out. Integration code MUST provide actionable
errors or structured status values rather than silent failures. New long-running
or network-dependent paths MUST define timeout behavior and logging sufficient to
diagnose local demo failures.

Rationale: The MVP depends on public sites and optional local services that may
be unavailable during demos; resilience is a core product behavior.

## Product and Technology Constraints

The canonical application structure is:

- `frontend/`: Next.js App Router, TypeScript, and Tailwind dashboard UI.
- `backend/`: FastAPI REST API, SQLite persistence, crawler, scoring, and graph
  fallback orchestration.
- `ml/`: local feature extraction, rule scoring, and baseline ML scripts.
- `data/`: sample job postings used for deterministic demo seeding.
- `chrome-extension/`: consent-based extraction from supported job pages.
- `docs/`: pipeline, pitch, demo, and operational guidance.

Feature plans MUST identify which of these areas are affected. Plans that add new
runtime dependencies, paid services, persistent stores, or external data sources
MUST justify the need, define local fallback behavior, and update setup
documentation. Score weighting or verdict threshold changes MUST update the
documented scoring contract and include before/after validation against sample
jobs.

## Delivery Workflow and Quality Gates

Every feature specification MUST include user scenarios, independent tests, edge
cases, functional requirements, measurable success criteria, and assumptions.
Every implementation plan MUST pass the Constitution Check before design work and
again after design artifacts are produced.

Tasks MUST be grouped by independently deliverable user story and include exact
file paths. Tests are required for behavior changes in scoring, extraction, API
contracts, persistence, extension consent, or user-visible frontend workflows.
Documentation updates are required when commands, environment variables, scoring
semantics, setup steps, or demo behavior change.

Before a feature is considered complete, contributors MUST run the smallest
relevant verification set and record any commands that could not be run. For local
demo changes, the backend and frontend quickstart paths MUST remain accurate.

## Governance

This constitution supersedes conflicting project conventions, generated templates,
and informal implementation habits. Amendments require a documented Sync Impact
Report in this file, including affected principles, version change, template
updates, and any deferred follow-up items.

Versioning follows semantic versioning:

- MAJOR: backward-incompatible governance changes, principle removals, or
  redefinitions that invalidate existing specs or plans.
- MINOR: new principles, new required sections, or materially expanded quality
  gates.
- PATCH: clarifications, wording improvements, typo fixes, and non-semantic
  refinements.

Compliance review is required during `/speckit-plan`, `/speckit-tasks`, and code
review. Any feature that violates a principle MUST document the violation, why it
is necessary, the simpler alternative considered, and the migration path back to
compliance.

**Version**: 1.0.0 | **Ratified**: 2026-05-22 | **Last Amended**: 2026-05-22
