# Dataset Contract: Advanced Classification

The advanced classifier training dataset is CSV-first to match the current local
ML workflow. JSON fields are stored as escaped JSON strings when needed.

## Required Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | string | Stable unique example ID |
| `text` | string | Full job posting text |
| `label` | enum | One of `LEGIT_REMOTE`, `COUNTRY_RESTRICTED_REMOTE`, `HYBRID_OR_LOCATION_BOUND`, `LOW_QUALITY_UNVERIFIED`, `LIKELY_SCAM` |
| `split` | enum | `train`, `validation`, or `test` |

## Recommended Columns

| Column | Type | Description |
|--------|------|-------------|
| `source_url` | string | Original source URL, if available |
| `company` | string | Extracted or reviewed company name |
| `job_title` | string | Extracted or reviewed job title |
| `applicant_country` | string | Country used when evaluating eligibility |
| `structured_features_json` | JSON string | Normalized structured features for gradient boosting |
| `graph_evidence_json` | JSON string | Relationship evidence for graph trust scoring |
| `review_notes` | string | Human notes about label choice |

## Validation Rules

- Unknown labels fail validation.
- Empty `id`, `text`, `label`, or `split` fail validation.
- Each split must be reported with row counts.
- Evaluation must report when one of the five labels has zero examples.
- JSON columns must parse if present.
- Secrets, API keys, authentication cookies, and private personal data are not
  allowed in any column.

## Minimal Example

```csv
id,text,label,split,source_url,company,job_title,applicant_country,structured_features_json,graph_evidence_json,review_notes
adv-001,"Remote backend engineer. Global applicants welcome. Apply on example.com/careers.",LEGIT_REMOTE,train,https://example.com/careers,Example Inc,Backend Engineer,Canada,"{""has_apply_url"":true}","{""domain_match"":true}","Official careers page"
adv-002,"Remote assistant needed. Pay equipment fee first. Contact hiringteam@gmail.com.",LIKELY_SCAM,train,,Unknown,Assistant,Canada,"{""has_payment_request"":true}","{""domain_match"":false}","Payment request and free email"
```
