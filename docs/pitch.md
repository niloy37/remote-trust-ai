# RemoteTrust AI Pitch

## Problem

Remote job seekers face three overlapping risks: fake job scams, postings that claim remote flexibility but require local presence, and low-quality roles that waste applicant time. Global applicants are especially exposed because eligibility rules are often buried in the job description.

## Solution

RemoteTrust AI analyzes a job posting and returns a trust score, verdict, explanation, red flags, positive signals, extracted job details, and recommended action.

## Why It Matters

Job scams cost applicants money and personal data. Misleading remote roles cost time. Clear verification helps job seekers prioritize real opportunities and avoid risky ones.

## Target Users

- global remote job seekers
- career coaches
- bootcamp graduates
- university career centers
- online communities that share remote jobs

## Pipeline

```text
Job Sources / User Input
↓
Job Description Extraction
↓
Preprocessing
↓
Feature Extraction
↓
Legitimacy + Remote + Eligibility + Quality Scoring
↓
Final Trust Score
↓
Dashboard + Feedback Loop
↓
Future Model Fine-Tuning
```

## AI/ML Approach

The MVP uses a hybrid scoring engine:

- rule-based scam detector
- NLP-style keyword and regex feature extraction
- structured pillar scoring
- baseline TF-IDF + Logistic Regression training script
- placeholder Hugging Face transformer fine-tuning path

This keeps the demo free to run locally while leaving a clear path to stronger models.

## What Makes It Different

RemoteTrust AI does not only ask whether a job is fake. It also checks whether the job is actually remote, whether the applicant country is likely eligible, and whether the role is worth applying to.

## Future Improvements

- Browser extension
- LinkedIn/Indeed page reader
- Company career page verification
- ATS verification through Greenhouse/Lever/Ashby
- Domain reputation checks
- Trustpilot/Glassdoor/company review integration
- Graph database for company-recruiter-job relationships
- Fine-tuned transformer model
- Active learning from user feedback
- Multi-language job description support
- Country-specific eligibility engine

## Team Roles

- Full-stack engineer: Next.js frontend, FastAPI backend, SQLite integration
- AI/ML engineer: feature extraction, scoring, baseline classifier, model evaluation
- Product designer: dashboard UX, score presentation, demo flow
- Data lead: labeled job dataset, scam phrase taxonomy, eligibility rules

