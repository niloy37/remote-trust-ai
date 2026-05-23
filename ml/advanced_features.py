from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse

from .feature_extractor import clean_job_text, is_page_chrome_noise_line
from .schemas import ExtractedJob, ScoreBreakdown


@dataclass
class RemoteRestrictionEvidence:
    allowed_countries: list[str] = field(default_factory=list)
    excluded_countries: list[str] = field(default_factory=list)
    timezone_requirements: str | None = None
    work_authorization: str | None = None
    onsite_or_hybrid_requirement: str | None = None
    ambiguous_location_language: list[str] = field(default_factory=list)
    source_snippets: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StructuredFeatureRecord:
    job_text: str
    job_title: str | None
    company: str | None
    location: str | None
    remote_type: str | None
    salary: str | None
    allowed_countries: list[str]
    excluded_countries: list[str]
    skills: list[str]
    contact_methods: list[str]
    has_suspicious_contact: bool
    has_payment_request: bool
    has_salary: bool
    has_apply_url: bool
    company_verification_score: int
    graph_trust_score: int
    rule_score: int
    source_type: str | None
    ats_provider: str | None
    recruiter_email_domain: str | None
    apply_domain: str | None
    remote_restrictions: RemoteRestrictionEvidence

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["remote_restrictions"] = self.remote_restrictions.as_dict()
        return data


EXCLUDED_COUNTRY_PATTERNS = [
    (r"(?:not available|not open|cannot hire|unable to hire).{0,60}\b(?:in|from)\s+([A-Za-z ,/]+)", "exclusion"),
    (r"(?:excluding|except)\s+([A-Za-z ,/]+)", "exclusion"),
]

ONSITE_PATTERNS = [
    r"((?:hybrid|onsite|on-site|office required|must commute|commute)[^\n\r.]{0,120})",
    r"((?:remote but|remote, but)[^\n\r.]{0,120})",
]

AMBIGUOUS_REMOTE_PATTERNS = [
    r"((?:remote within|remote in|remote from|based in|must be located in)[^\n\r.]{0,120})",
    r"((?:overlap|available).{0,80}(?:EST|PST|CST|MST|UTC|GMT)[^\n\r.]*)",
]

COUNTRY_WORDS = {
    "United States": ["us", "u.s.", "usa", "united states"],
    "Canada": ["canada"],
    "European Union": ["eu", "europe", "european union"],
    "United Kingdom": ["uk", "u.k.", "united kingdom"],
    "India": ["india"],
    "Australia": ["australia"],
}

ATS_DOMAINS = {
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "ashbyhq.com": "Ashby",
    "workable.com": "Workable",
    "smartrecruiters.com": "SmartRecruiters",
    "bamboohr.com": "BambooHR",
    "icims.com": "iCIMS",
    "jobvite.com": "Jobvite",
    "recruitee.com": "Recruitee",
    "personio.com": "Personio",
}


def _clean_snippet(value: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", value or "").strip(" \t\r\n-:|")
    if not cleaned:
        return None
    lower = cleaned.lower()
    if is_page_chrome_noise_line(cleaned):
        return None
    if (
        "%20" in lower
        or "%2c" in lower
        or "origin=" in lower
        or "currentjobid=" in lower
        or "https://" in lower
        or "http://" in lower
        or "/jobs/" in lower
    ):
        return None
    if len(re.findall(r"[A-Za-z]{2,}", cleaned)) < 2:
        return None
    return cleaned[:160]


def _snippet(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return _clean_snippet(match.group(1))


def _countries_from_text(value: str) -> list[str]:
    lower = value.lower()
    found: list[str] = []
    for country, aliases in COUNTRY_WORDS.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", lower) for alias in aliases):
            found.append(country)
    return found


def extract_remote_restrictions(job_description: str, extracted: ExtractedJob) -> RemoteRestrictionEvidence:
    text = clean_job_text(job_description)
    snippets: list[str] = []
    excluded: list[str] = []
    ambiguous: list[str] = []

    for pattern, _ in EXCLUDED_COUNTRY_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            raw = match.group(1)
            excluded.extend(country for country in _countries_from_text(raw) if country not in excluded)
            cleaned = _clean_snippet(match.group(0))
            if cleaned:
                snippets.append(cleaned)

    onsite = None
    for pattern in ONSITE_PATTERNS:
        onsite = _snippet(text, pattern)
        if onsite:
            snippets.append(onsite)
            break

    for pattern in AMBIGUOUS_REMOTE_PATTERNS:
        hit = _snippet(text, pattern)
        if hit and hit not in ambiguous:
            ambiguous.append(hit)
            snippets.append(hit)

    cleaned_auth = _clean_snippet(extracted.work_authorization or "")
    if cleaned_auth and cleaned_auth not in snippets:
        snippets.append(cleaned_auth)
    cleaned_timezone = _clean_snippet(extracted.timezone_requirements or "")
    if cleaned_timezone and cleaned_timezone not in snippets:
        snippets.append(cleaned_timezone)

    return RemoteRestrictionEvidence(
        allowed_countries=list(extracted.allowed_countries),
        excluded_countries=excluded,
        timezone_requirements=extracted.timezone_requirements,
        work_authorization=extracted.work_authorization,
        onsite_or_hybrid_requirement=onsite,
        ambiguous_location_language=ambiguous[:5],
        source_snippets=snippets[:6],
    )


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url if re.match(r"^[a-z]+://", url, re.IGNORECASE) else f"https://{url}")
    domain = parsed.netloc or parsed.path.split("/")[0]
    return domain.lower().removeprefix("www.") or None


def _ats_provider(domain: str | None) -> str | None:
    if not domain:
        return None
    for ats_domain, provider in ATS_DOMAINS.items():
        if domain == ats_domain or domain.endswith(f".{ats_domain}"):
            return provider
    return None


def _first_email_domain(contacts: list[str]) -> str | None:
    for contact in contacts:
        if "@" in contact:
            return contact.split("@")[-1].lower()
    return None


def has_payment_request(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in ["equipment fee", "processing fee", "send money", "gift card", "wire transfer", "crypto"])


def build_structured_features(
    job_description: str,
    extracted: ExtractedJob,
    scores: ScoreBreakdown,
    company_verification_score: int = 0,
    graph_trust_score: int = 0,
) -> StructuredFeatureRecord:
    apply_domain = _domain(extracted.apply_url)
    final_rule_score = round(
        scores.legitimacy * 0.40
        + scores.remote_authenticity * 0.25
        + scores.global_eligibility * 0.20
        + scores.job_quality * 0.15
    )
    return StructuredFeatureRecord(
        job_text=job_description,
        job_title=extracted.job_title,
        company=extracted.company,
        location=extracted.location,
        remote_type=extracted.remote_type,
        salary=extracted.salary,
        allowed_countries=list(extracted.allowed_countries),
        excluded_countries=[],
        skills=list(extracted.required_skills),
        contact_methods=list(extracted.contact_methods),
        has_suspicious_contact=bool(extracted.suspicious_contact_methods),
        has_payment_request=has_payment_request(job_description),
        has_salary=bool(extracted.salary),
        has_apply_url=bool(extracted.apply_url),
        company_verification_score=company_verification_score,
        graph_trust_score=graph_trust_score,
        rule_score=final_rule_score,
        source_type=None,
        ats_provider=_ats_provider(apply_domain),
        recruiter_email_domain=_first_email_domain(extracted.contact_methods),
        apply_domain=apply_domain,
        remote_restrictions=extract_remote_restrictions(job_description, extracted),
    )
