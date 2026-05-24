from __future__ import annotations

import re
from urllib.parse import urlparse

from .feature_extractor import (
    GLOBAL_REMOTE_PHRASES,
    REMOTE_RESTRICTION_PHRASES,
    clean_job_text,
    extract_features,
    has_hard_hybrid_or_onsite_requirement,
    has_optional_remote_choice,
    has_professional_domain,
)
from .schemas import AnalysisResult, ExtractedJob, ScoreBreakdown, TitleValidation
from .title_validator import validate_job_title


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def has_any(text: str, phrases: list[str]) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in phrases)


def add_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def is_official_apply_url(url: str | None) -> bool:
    if not url:
        return False
    domain = urlparse(url).netloc.lower()
    trusted = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com", "jobs.", "careers.")
    suspicious = ("bit.ly", "tinyurl", "t.me", "wa.me", "forms.gle", "docs.google.com/forms")
    return any(token in domain for token in trusted) and not any(token in domain for token in suspicious)


def detect_unrealistic_salary(text: str, salary: str | None) -> bool:
    lower = text.lower()
    if "earn $500/day" in lower or "guaranteed income" in lower:
        return True
    numbers = [int(n.replace(",", "")) for n in re.findall(r"\$\s?(\d{3,6}(?:,\d{3})?)", text)]
    return any(n >= 300000 for n in numbers) and not any(term in lower for term in ["senior", "staff", "principal", "executive"])


def has_clear_responsibilities(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in ["responsibilities", "you will", "what you will do", "own ", "build ", "collaborate"])


def has_hiring_process(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in ["interview process", "recruiter screen", "technical interview", "take-home", "final interview"])


def is_vague_description(text: str) -> bool:
    words = re.findall(r"\w+", text)
    lower = text.lower()
    vague_terms = ["easy money", "no experience needed", "limited spots", "simple tasks", "work few hours"]
    return len(words) < 70 or sum(term in lower for term in vague_terms) >= 2


def grammar_payment_combo(text: str) -> bool:
    lower = text.lower()
    odd_phrases = ["kindly", "dear applicant", "do the needful", "send your informations"]
    payment_terms = ["send money", "processing fee", "equipment fee", "gift card", "wire transfer", "crypto"]
    return any(term in lower for term in odd_phrases) and any(term in lower for term in payment_terms)


def suspicious_links(text: str, apply_url: str | None) -> bool:
    lower = text.lower()
    url = (apply_url or "").lower()
    risky_domains = ["bit.ly", "tinyurl", "t.me/", "wa.me/", "telegram.me"]
    return any(domain in lower or domain in url for domain in risky_domains)


def country_matches(applicant_country: str, allowed: list[str]) -> bool:
    if not allowed or "Worldwide" in allowed:
        return True
    normalized = applicant_country.strip().lower()
    aliases = {
        "United States": {"united states", "usa", "us", "u.s."},
        "Canada": {"canada"},
        "European Union": {"european union", "eu", "france", "germany", "spain", "italy", "netherlands", "poland", "ireland"},
        "United Kingdom": {"united kingdom", "uk", "u.k."},
    }
    for country in allowed:
        if normalized == country.lower():
            return True
        if normalized in aliases.get(country, set()):
            return True
    return False


def score_legitimacy(text: str, extracted: ExtractedJob, red_flags: list[str], positive_signals: list[str]) -> int:
    score = 70

    if extracted.company:
        score += 8
        add_unique(positive_signals, f"Company detected: {extracted.company}")
    else:
        score -= 15
        add_unique(red_flags, "No company name detected")

    if is_official_apply_url(extracted.apply_url):
        score += 8
        add_unique(positive_signals, "Apply link appears to use a recognized hiring platform")

    if extracted.salary:
        score += 6
        add_unique(positive_signals, "Salary or compensation range is disclosed")

    if has_clear_responsibilities(text):
        score += 7
        add_unique(positive_signals, "Responsibilities are described clearly")
    else:
        score -= 8
        add_unique(red_flags, "Responsibilities are vague or missing")

    if has_professional_domain(extracted):
        score += 5
        add_unique(positive_signals, "Professional domain or company-hosted contact detected")

    if has_hiring_process(text):
        score += 6
        add_unique(positive_signals, "Specific interview or hiring process is mentioned")

    if extracted.suspicious_contact_methods:
        score -= 20
        add_unique(red_flags, "Suspicious personal recruiter contact method detected")

    scam_hits = [phrase for phrase in extracted.scam_phrases if phrase not in {"telegram"}]
    if scam_hits:
        penalty = min(40, 10 + len(scam_hits) * 7)
        score -= penalty
        add_unique(red_flags, "Scam-language detected: " + ", ".join(scam_hits[:4]))

    if detect_unrealistic_salary(text, extracted.salary):
        score -= 18
        add_unique(red_flags, "Compensation appears unusually high for the role context")

    if is_vague_description(text):
        score -= 10
        add_unique(red_flags, "Job description is too vague for confident verification")

    if has_any(text, ["hiring immediately", "urgent hiring", "no interview"]):
        score -= 16
        add_unique(red_flags, "Urgency pressure or no-interview language appears in the posting")

    if grammar_payment_combo(text):
        score -= 18
        add_unique(red_flags, "Poor phrasing appears together with payment requests")

    if suspicious_links(text, extracted.apply_url):
        score -= 14
        add_unique(red_flags, "Suspicious short link or chat-app link detected")

    return clamp(score)


def score_remote_authenticity(text: str, extracted: ExtractedJob, red_flags: list[str], positive_signals: list[str]) -> int:
    lower = text.lower()
    score = 55
    optional_remote_choice = has_optional_remote_choice(text)
    hard_hybrid_or_onsite = has_hard_hybrid_or_onsite_requirement(text)

    if "remote-first" in lower:
        score += 22
        add_unique(positive_signals, "Remote-first policy is explicitly stated")
    if "fully remote" in lower or "100% remote" in lower:
        score += 22
        add_unique(positive_signals, "Fully remote work is explicitly stated")
    if "work from anywhere" in lower or "worldwide" in lower:
        score += 18
        add_unique(positive_signals, "Work-from-anywhere or worldwide language is present")
    if extracted.timezone_requirements:
        score += 6
        add_unique(positive_signals, "Timezone expectations are stated")
    if optional_remote_choice and not hard_hybrid_or_onsite:
        score += 10
        add_unique(positive_signals, "Remote work is listed as a flexible work option")

    if "hybrid" in lower and hard_hybrid_or_onsite:
        score -= 30
        add_unique(red_flags, "Posting is hybrid, not fully remote")
    if hard_hybrid_or_onsite and has_any(text, ["must commute", "commute", "onsite", "on-site"]):
        score -= 28
        add_unique(red_flags, "Onsite or commute requirement conflicts with remote claim")
    if "must be located in" in lower:
        score -= 10
        add_unique(red_flags, "Remote work is location-restricted")
    if hard_hybrid_or_onsite and ("remote but office required" in lower or "office required" in lower):
        score -= 25
        add_unique(red_flags, "Remote policy still requires office attendance")

    if not extracted.remote_type:
        score -= 16
        add_unique(red_flags, "Remote policy is unclear")

    return clamp(score)


def score_global_eligibility(text: str, extracted: ExtractedJob, applicant_country: str, red_flags: list[str], positive_signals: list[str]) -> int:
    lower = text.lower()
    score = 55

    if any(phrase in lower for phrase in GLOBAL_REMOTE_PHRASES):
        score += 28
        add_unique(positive_signals, "Posting welcomes worldwide or work-from-anywhere applicants")

    if "contractor-friendly" in lower or "contractor friendly" in lower:
        score += 8
        add_unique(positive_signals, "Contractor-friendly arrangement is stated")

    if not extracted.allowed_countries and not extracted.work_authorization:
        score += 8
        add_unique(positive_signals, "No explicit country restriction detected")

    if extracted.allowed_countries and country_matches(applicant_country, extracted.allowed_countries):
        score += 14
        add_unique(positive_signals, f"Applicant country appears eligible: {applicant_country}")

    if extracted.allowed_countries and not country_matches(applicant_country, extracted.allowed_countries):
        score -= 35
        add_unique(red_flags, f"Country restriction may exclude applicants from {applicant_country}")

    restriction_hits = [phrase for phrase in REMOTE_RESTRICTION_PHRASES if phrase in lower]
    if any(hit in restriction_hits for hit in ["us only", "u.s. only", "usa only", "canada only", "eu only"]):
        score -= 18
        add_unique(red_flags, "Country-only remote restriction detected")

    if extracted.work_authorization:
        score -= 22
        add_unique(red_flags, "Local work authorization or residency requirement detected")

    if has_any(text, ["citizenship", "permanent residency", "visa sponsorship is not available"]):
        score -= 16
        add_unique(red_flags, "Citizenship, permanent residency, or visa limitation detected")

    return clamp(score)


def score_job_quality(text: str, extracted: ExtractedJob, red_flags: list[str], positive_signals: list[str]) -> int:
    lower = text.lower()
    score = 55

    if has_clear_responsibilities(text):
        score += 14
    else:
        score -= 14

    if extracted.required_skills:
        score += 14
        add_unique(positive_signals, "Required skills are specific: " + ", ".join(extracted.required_skills[:5]))
    else:
        score -= 8
        add_unique(red_flags, "Required skills are unclear")

    if extracted.salary:
        score += 10
    else:
        score -= 4

    if any(term in lower for term in ["benefits", "health insurance", "paid time off", "pto", "learning budget", "home office stipend"]):
        score += 8
        add_unique(positive_signals, "Benefits or support are mentioned")

    if any(term in lower for term in ["3+ years", "5+ years", "experience with", "portfolio", "degree or equivalent", "reasonable accommodation"]):
        score += 5

    if extracted.company:
        score += 5

    if "commission-only" in lower or "commission only" in lower:
        score -= 25
        add_unique(red_flags, "Commission-only compensation lacks stability")

    if "unpaid" in lower or "volunteer role" in lower:
        score -= 30
        add_unique(red_flags, "Role appears unpaid")

    if is_vague_description(text):
        score -= 10

    if detect_unrealistic_salary(text, extracted.salary):
        score -= 12

    if not has_hiring_process(text):
        score -= 4

    return clamp(score)


def build_explanation(scores: ScoreBreakdown, verdict: str, red_flags: list[str], positive_signals: list[str]) -> str:
    strongest = sorted(scores.as_dict().items(), key=lambda item: item[1], reverse=True)
    best_name, best_score = strongest[0]
    weakest_name, weakest_score = strongest[-1]
    red_summary = red_flags[0] if red_flags else "No severe scam indicators were detected"
    positive_summary = positive_signals[0] if positive_signals else "The posting has limited positive verification signals"
    return (
        f"RemoteTrust AI marked this job as {verdict} because its strongest pillar is "
        f"{best_name.replace('_', ' ')} at {best_score}/100, while {weakest_name.replace('_', ' ')} "
        f"is the main constraint at {weakest_score}/100. {positive_summary}. {red_summary}."
    )


def recommend_action(final_score: int) -> str:
    if final_score >= 80:
        return "Apply"
    if final_score >= 60:
        return "Review carefully"
    return "Avoid"


def apply_title_validation_adjustments(
    scores: ScoreBreakdown,
    title_validation: TitleValidation,
    red_flags: list[str],
    positive_signals: list[str],
) -> ScoreBreakdown:
    verdict = title_validation.verdict
    if verdict in {"Recognized", "Plausible"}:
        message = f"Job title legitimacy looks {verdict.lower()} ({title_validation.score}/100)"
        if title_validation.closest_known_titles:
            message += f"; closest match: {title_validation.closest_known_titles[0]}"
        add_unique(positive_signals, message)
        return ScoreBreakdown(
            legitimacy=clamp(scores.legitimacy + (2 if verdict == "Recognized" else 1)),
            remote_authenticity=scores.remote_authenticity,
            global_eligibility=scores.global_eligibility,
            job_quality=clamp(scores.job_quality + 1),
        )

    existing_risk = bool(red_flags)
    if verdict == "Suspicious":
        warning = title_validation.warnings[0] if title_validation.warnings else "Title does not look like a credible occupation"
        add_unique(red_flags, f"Job title may be fabricated or misleading: {warning}")
        legitimacy_penalty = 10 if existing_risk else 5
        quality_penalty = 6 if existing_risk else 3
    else:
        warning = title_validation.warnings[0] if title_validation.warnings else "Title is unusual and should be reviewed"
        add_unique(red_flags, f"Job title is unusual: {warning}")
        legitimacy_penalty = 2
        quality_penalty = 1

    return ScoreBreakdown(
        legitimacy=clamp(scores.legitimacy - legitimacy_penalty),
        remote_authenticity=scores.remote_authenticity,
        global_eligibility=scores.global_eligibility,
        job_quality=clamp(scores.job_quality - quality_penalty),
    )


def analyze_job_text(
    job_description: str,
    applicant_country: str,
    job_url: str | None = None,
    desired_role: str | None = None,
) -> AnalysisResult:
    text = clean_job_text(job_description)
    if desired_role:
        text = f"{text}\nDesired role from applicant: {desired_role}"

    extracted = extract_features(text, job_url)
    title_validation = validate_job_title(extracted.job_title, text)
    red_flags: list[str] = []
    positive_signals: list[str] = []

    scores = ScoreBreakdown(
        legitimacy=score_legitimacy(text, extracted, red_flags, positive_signals),
        remote_authenticity=score_remote_authenticity(text, extracted, red_flags, positive_signals),
        global_eligibility=score_global_eligibility(text, extracted, applicant_country, red_flags, positive_signals),
        job_quality=score_job_quality(text, extracted, red_flags, positive_signals),
    )
    scores = apply_title_validation_adjustments(scores, title_validation, red_flags, positive_signals)
    final_score = round(
        scores.legitimacy * 0.40
        + scores.remote_authenticity * 0.25
        + scores.global_eligibility * 0.20
        + scores.job_quality * 0.15
    )
    verdict = "Verified" if final_score >= 80 else "Caution" if final_score >= 60 else "Risky"
    return AnalysisResult(
        final_score=final_score,
        verdict=verdict,
        scores=scores,
        extracted=extracted,
        title_validation=title_validation,
        red_flags=red_flags,
        positive_signals=positive_signals,
        extraction_warnings=list(extracted.extraction_warnings),
        explanation=build_explanation(scores, verdict, red_flags, positive_signals),
        recommended_action=recommend_action(final_score),
    )
