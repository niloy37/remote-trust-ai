from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import unquote, urlparse

from .schemas import ExtractedJob

try:  # Optional locally; installed in the Docker backend image.
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - fallback is exercised when dependency is absent.
    fuzz = None


SCAM_PHRASES = [
    "pay for training",
    "send money",
    "gift card",
    "gift cards",
    "crypto",
    "wire transfer",
    "telegram",
    "whatsapp only",
    "no interview",
    "guaranteed income",
    "earn $500/day",
    "equipment fee",
    "processing fee",
    "urgent hiring",
    "kindly send your personal details",
    "personal details",
]

GLOBAL_REMOTE_PHRASES = [
    "worldwide",
    "work from anywhere",
    "fully remote",
    "remote-first",
    "distributed team",
    "async team",
    "global applicants welcome",
    "open to global applicants",
]

REMOTE_RESTRICTION_PHRASES = [
    "us only",
    "u.s. only",
    "usa only",
    "canada only",
    "eu only",
    "must be authorized to work in the us",
    "must be authorised to work in the us",
    "must be located in",
    "hybrid",
    "onsite",
    "on-site",
    "commute",
    "within",
    "est hours required",
    "pst overlap required",
]

COUNTRY_ALIASES = {
    "united states": ["united states", "usa", "u.s.", "us"],
    "canada": ["canada"],
    "european union": ["eu", "european union", "europe"],
    "united kingdom": ["united kingdom", "uk", "u.k."],
    "india": ["india"],
    "worldwide": ["worldwide", "global", "anywhere"],
}

SKILL_KEYWORDS = [
    "python",
    "typescript",
    "javascript",
    "react",
    "next.js",
    "fastapi",
    "sql",
    "postgresql",
    "aws",
    "docker",
    "kubernetes",
    "machine learning",
    "data analysis",
    "excel",
    "analytics",
    "api",
    "node.js",
    "communication",
    "customer success",
    "sales",
]

LINKEDIN_SEARCH_CHROME_MARKERS = [
    "how promoted jobs are ranked",
    "promoted jobs are ranked",
    "job alert",
    "set alert",
    "see more jobs",
    "similar jobs",
]

LINKEDIN_REMOTE_FILTER_PATTERN = re.compile(r"\b(?:on-site|onsite)\s+or\s+hybrid\s+or\s+remote\b", re.IGNORECASE)
RESULT_COUNT_PATTERN = re.compile(r"\b\d+\+?\s+results?\b", re.IGNORECASE)
OPTIONAL_REMOTE_CHOICE_PATTERN = re.compile(
    r"\b(?:flexible work options?|work options?|flexible work arrangements?|choose|choice|options?|available)\b"
    r"[^\n\r.]{0,120}\b(?:remote|hybrid|office|onsite|on-site)\b|"
    r"\b(?:office|onsite|on-site|hybrid)\s*(?:,|\bor\b|\band\b)[^\n\r.]{0,60}\bremote\b|"
    r"\bremote\s*(?:,|\bor\b|\band\b)[^\n\r.]{0,60}\b(?:office|onsite|on-site|hybrid)\b",
    re.IGNORECASE,
)
HARD_LOCATION_REQUIREMENT_PATTERN = re.compile(
    r"\b(?:must\s+(?:commute|be\s+based|be\s+located)|commute|"
    r"(?:hybrid|onsite|on-site|office)[^\n\r.]{0,40}\brequir(?:ed|es?)\b|"
    r"\brequir(?:ed|es?)\b[^\n\r.]{0,40}\b(?:hybrid|onsite|on-site|office)\b|"
    r"office\s+attendance|hybrid\s+(?:role|position|schedule)|"
    r"onsite\s+(?:role|position|schedule)|on-site\s+(?:role|position|schedule)|"
    r"remote\s+but|based\s+in|located\s+in|"
    r"\d+\s+days?\s+(?:per|a)\s+week|two\s+days?\s+(?:per|a)\s+week|"
    r"three\s+days?\s+(?:per|a)\s+week|four\s+days?\s+(?:per|a)\s+week)\b",
    re.IGNORECASE,
)

ATS_PROVIDERS = {
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "ashbyhq.com": "Ashby",
    "workable.com": "Workable",
    "smartrecruiters.com": "SmartRecruiters",
}

COMPANY_REJECTION_PHRASES = {
    "software, happy customers",
    "building deep",
    "deep personalized relationships",
    "deep, personalized relationships",
    "our customers",
    "happy customers",
    "meaningful business value",
    "successful candidate",
    "ideal candidate",
    "this role",
    "the role",
    "the job",
}

GENERIC_COMPANY_VALUES = {
    "company",
    "employer",
    "organization",
    "recruiter",
    "hiring team",
    "our team",
    "the company",
    "your company",
    "remote job",
    "job posting",
}

COMPANY_FIELD_STOP = re.compile(
    r"\b(?:job title|title|role|position|location|salary|compensation|description|"
    r"responsibilities|requirements|qualifications|benefits|core competencies|"
    r"key responsibilities|why\s+join)\b\s*[:\-]?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CompanyCandidate:
    name: str
    confidence: float
    evidence: str
    priority: int


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_page_chrome_noise_line(line: str) -> bool:
    normalized = normalize_text(line)
    lower = normalized.lower()
    if not lower:
        return True
    if any(marker in lower for marker in LINKEDIN_SEARCH_CHROME_MARKERS):
        return True
    if RESULT_COUNT_PATTERN.search(lower) and ("job" in lower or "remote" in lower):
        return True
    if LINKEDIN_REMOTE_FILTER_PATTERN.search(lower) and ("results" in lower or "ranked" in lower):
        return True
    return False


def clean_job_text(text: str) -> str:
    lines = re.split(r"[\r\n]+", text or "")
    cleaned_lines = [line for line in lines if not is_page_chrome_noise_line(line)]
    return "\n".join(cleaned_lines).strip()


def has_optional_remote_choice(text: str) -> bool:
    for match in OPTIONAL_REMOTE_CHOICE_PATTERN.finditer(text or ""):
        if not HARD_LOCATION_REQUIREMENT_PATTERN.search(match.group(0)):
            return True
    return False


def has_hard_hybrid_or_onsite_requirement(text: str) -> bool:
    value = text or ""
    if re.search(r"\b(?:must\s+commute|commute|office\s+required|office\s+attendance|remote\s+but)\b", value, re.IGNORECASE):
        return True
    if re.search(r"\b(?:hybrid|onsite|on-site)\b", value, re.IGNORECASE) and HARD_LOCATION_REQUIREMENT_PATTERN.search(value):
        return True
    if re.search(r"\b(?:onsite|on-site)\b", value, re.IGNORECASE) and not has_optional_remote_choice(value):
        return True
    return False


def find_first(patterns: Iterable[str], text: str, flags: int = re.IGNORECASE) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return clean_capture(match.group(1))
    return None


def clean_capture(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" -:|•\t\r\n")
    return value[:160] if value else value


def parse_linkedin_title(text: str) -> tuple[str | None, str | None, str | None]:
    title_line = find_first(
        [
            r"(?:browser title|page title|meta title)\s*[:\-]\s*([^\n\r]+)",
            r"([^\n\r]+?\s+hiring\s+[^\n\r]+?\s+(?:in|at)\s+[^\n\r]+?\s+\|\s+LinkedIn)",
            r"([^\n\r]+?\s+hiring\s+[^\n\r]+?\s+\|\s+LinkedIn)",
        ],
        text,
    )
    if not title_line:
        return None, None, None

    title_line = re.sub(r"\s+[\-|]\s+LinkedIn.*$", "", title_line, flags=re.IGNORECASE).strip()
    match = re.match(r"(.+?)\s+hiring\s+(.+?)\s+in\s+(.+)$", title_line, flags=re.IGNORECASE)
    if match:
        return clean_capture(match.group(2)), clean_capture(match.group(1)), clean_capture(match.group(3))

    match = re.match(r"(.+?)\s+hiring\s+(.+)$", title_line, flags=re.IGNORECASE)
    if match:
        return clean_capture(match.group(2)), clean_capture(match.group(1)), None

    match = re.match(r"(.+?)\s+at\s+(.+)$", title_line, flags=re.IGNORECASE)
    if match:
        return clean_capture(match.group(1)), clean_capture(match.group(2)), None

    return None, None, None


def first_json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return clean_capture(re.sub(r"<[^>]+>", " ", value))
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [first_json_text(item) for item in value]
        return ", ".join(part for part in parts if part) or None
    if isinstance(value, dict):
        for key in ("name", "legalName", "text", "addressLocality", "addressRegion", "addressCountry"):
            text = first_json_text(value.get(key))
            if text:
                return text
    return None


def json_ld_blocks_from_text(text: str) -> list[Any]:
    blocks: list[Any] = []
    script_matches = re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        text or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    raw_blocks = script_matches or ([text.strip()] if (text or "").strip().startswith(("{", "[")) else [])
    for raw in raw_blocks:
        try:
            blocks.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return blocks


def iter_json_nodes(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        graph = node.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from iter_json_nodes(item)
    elif isinstance(node, list):
        for item in node:
            yield from iter_json_nodes(item)


def normalize_company_candidate(value: str) -> str | None:
    cleaned = clean_capture(value)
    if not cleaned:
        return None
    cleaned = re.sub(r"^(?:company|organization|employer|hiring organization)\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = COMPANY_FIELD_STOP.split(cleaned)[0]
    cleaned = re.split(r"\s{2,}|[|•]|\t", cleaned)[0]
    cleaned = re.sub(r"\s+(?:careers?|jobs?|job openings?|hiring)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:'s|\u2019s)\s+.*$", "", cleaned).strip()
    cleaned = cleaned.strip(" \t\r\n-:,.!?\"'")
    return cleaned or None


def company_candidate_rejection_reason(value: str) -> str | None:
    normalized = normalize_company_candidate(value)
    if not normalized:
        return "empty company candidate"

    lower = normalized.lower()
    words = re.findall(r"[A-Za-z][A-Za-z0-9&.'-]*", normalized)
    if lower in GENERIC_COMPANY_VALUES:
        return "generic company noun"
    if len(normalized) < 2:
        return "too short to be a company name"
    if len(normalized) > 70 or len(words) > 7:
        return "too long to be a reliable company name"
    if any(phrase in lower for phrase in COMPANY_REJECTION_PHRASES):
        return "looks like job-description prose, not a company name"
    if "," in normalized and not re.search(r",\s*(?:inc|inc\.|llc|ltd|ltd\.|corp|corp\.|co|co\.)$", lower):
        return "comma-heavy phrase"
    if re.search(r"[.!?;:]", normalized):
        return "sentence punctuation"
    if re.search(
        r"\b(?:we|our|your|their|candidate|applicant|role|job|benefits|vacation|"
        r"responsibilities|requirements|customers|communities|relationships|"
        r"technologies|processes|workflow|workflows|business|value)\b",
        lower,
    ) and not re.search(r"\b(?:inc|llc|ltd|corp|company|labs|systems|group|ai|io)\b", lower):
        return "generic prose words"
    if words:
        capitalized = sum(1 for word in words if word[:1].isupper() or word.isupper())
        if capitalized == 0:
            return "lowercase fragment"
        lowercase_tokens = sum(1 for word in words if word[:1].islower() and not word.isupper())
        if lowercase_tokens > capitalized and not re.search(r"\b(?:of|and|the|for)\b", lower):
            return "mostly lowercase phrase"
    return None


def is_valid_company_candidate(value: str | None) -> bool:
    return bool(value and company_candidate_rejection_reason(value) is None)


def title_company_patterns(text: str) -> list[tuple[str | None, str | None, str]]:
    matches: list[tuple[str | None, str | None, str]] = []
    candidate_lines = []
    for line in re.split(r"[\r\n]+", text or "")[:30]:
        line = clean_capture(line)
        if not line or len(line) > 140:
            continue
        line = re.sub(r"^(?:browser title|page title|meta title|title)\s*[:\-]\s*", "", line, flags=re.IGNORECASE)
        candidate_lines.append(line)

    for line in candidate_lines:
        linkedin_title, linkedin_company, _ = parse_linkedin_title(line)
        if linkedin_title or linkedin_company:
            matches.append((linkedin_title, linkedin_company, "browser title LinkedIn pattern"))

        match = re.match(
            r"(?P<title>[A-Z][A-Za-z0-9 /&,+.'\-]{2,80}?)\s+(?:at|with)\s+"
            r"(?P<company>[A-Z][A-Za-z0-9&.'\- ]{1,70})$",
            line,
        )
        if match:
            matches.append((clean_capture(match.group("title")), clean_capture(match.group("company")), "title pattern: role at company"))

        match = re.match(
            r"(?P<company>[A-Z][A-Za-z0-9&.'\- ]{1,70})\s+(?:is\s+)?hiring\s+"
            r"(?:a|an)?\s*(?P<title>[A-Z][A-Za-z0-9 /&,+.'\-]{2,80})$",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            matches.append((clean_capture(match.group("title")), clean_capture(match.group("company")), "title pattern: company hiring role"))

        match = re.match(
            r"(?P<title>[A-Z][A-Za-z0-9 /&,+.'\-]{2,80}?)\s+[-|]\s+"
            r"(?P<company>[A-Z][A-Za-z0-9&.'\- ]{1,70})(?:\s+careers?)?$",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            matches.append((clean_capture(match.group("title")), clean_capture(match.group("company")), "title metadata pattern"))
    return matches


def company_from_ats_url(job_url: str | None) -> tuple[str | None, str | None]:
    if not job_url:
        return None, None
    parsed = urlparse(job_url if re.match(r"^[a-z]+://", job_url, re.IGNORECASE) else f"https://{job_url}")
    domain = parsed.netloc.lower().removeprefix("www.")
    path_parts = [unquote(part) for part in parsed.path.split("/") if part]
    provider = None
    for ats_domain, label in ATS_PROVIDERS.items():
        if domain == ats_domain or domain.endswith(f".{ats_domain}") or ats_domain in domain:
            provider = label
            break
    if not provider:
        return None, None

    slug_value: str | None = None
    if provider == "Greenhouse" and path_parts:
        slug_value = path_parts[0]
    elif provider in {"Lever", "Ashby", "Workable", "SmartRecruiters"} and path_parts:
        slug_value = path_parts[0]
    if not slug_value:
        subdomain = domain.split(".")[0]
        if subdomain not in {"jobs", "boards", "apply", "job-boards"}:
            slug_value = subdomain
    if not slug_value:
        return None, None

    words = re.split(r"[-_+%20]+", slug_value)
    company = " ".join(word for word in words if word and not word.isdigit()).strip()
    if not company:
        return None, None
    display = company.title()
    display = re.sub(r"\bAi\b", "AI", display)
    return display, f"{provider} URL"


def collect_company_candidates(text: str, job_url: str | None = None) -> list[CompanyCandidate]:
    candidates: list[CompanyCandidate] = []

    for block in json_ld_blocks_from_text(text):
        for node in iter_json_nodes(block):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if "JobPosting" not in types:
                continue
            organization = first_json_text(node.get("hiringOrganization"))
            if organization:
                candidates.append(CompanyCandidate(organization, 0.98, "JSON-LD JobPosting hiringOrganization", 100))

    for match in re.finditer(
        r"(?im)^\s*(?:company|employer|organization|hiring organization)\s*[:\-]\s*([^\n\r]{2,100})",
        text,
    ):
        candidates.append(CompanyCandidate(match.group(1), 0.94, "explicit company label", 90))

    ats_company, ats_evidence = company_from_ats_url(job_url)
    if ats_company and ats_evidence:
        candidates.append(CompanyCandidate(ats_company, 0.78, ats_evidence, 75))

    for _, company, evidence in title_company_patterns(text):
        if company:
            candidates.append(CompanyCandidate(company, 0.84, evidence, 80))

    for meta_name in ("og:site_name", "application-name"):
        pattern = rf"<meta[^>]+(?:name|property)=[\"']{re.escape(meta_name)}[\"'][^>]+content=[\"']([^\"']+)[\"'][^>]*>"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            candidates.append(CompanyCandidate(match.group(1), 0.74, f"page metadata {meta_name}", 65))

    for match in re.finditer(
        r"(?im)^\s*(?:why|about)\s+(?!the\b|this\b|our\b)([A-Z][A-Za-z0-9&.'\- ]{1,60})\??\s*$",
        text,
    ):
        candidates.append(CompanyCandidate(match.group(1), 0.72, "section heading", 70))

    for match in re.finditer(
        r"\b(?:join|at|with)\b\s+([A-Z][A-Za-z0-9&.'\- ]{1,60})(?=\s+(?:as|to|for|and|who|is|we)\b|[,.\n\r])",
        text,
    ):
        candidates.append(CompanyCandidate(match.group(1), 0.58, "bounded text heuristic", 45))

    return candidates


def extract_json_ld_job_title(text: str) -> str | None:
    for block in json_ld_blocks_from_text(text):
        for node in iter_json_nodes(block):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if "JobPosting" in types:
                title = first_json_text(node.get("title"))
                if title:
                    return title[:100]
    return None


def extract_company_metadata(text: str, job_url: str | None = None) -> tuple[str | None, float | None, str | None, list[str]]:
    warnings: list[str] = []
    valid: list[CompanyCandidate] = []
    rejected_examples: list[str] = []

    seen: set[str] = set()
    for candidate in collect_company_candidates(text, job_url):
        normalized = normalize_company_candidate(candidate.name)
        if not normalized:
            continue
        reason = company_candidate_rejection_reason(normalized)
        if reason:
            if len(rejected_examples) < 3:
                rejected_examples.append(f"{normalized} ({reason})")
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        valid.append(CompanyCandidate(normalized, candidate.confidence, candidate.evidence, candidate.priority))

    if rejected_examples:
        warnings.append("Rejected weak company candidate(s): " + "; ".join(rejected_examples))
    if not valid:
        warnings.append("Company name could not be verified from structured fields or reliable posting text.")
        return None, None, None, warnings

    if fuzz and len(valid) > 1:
        best = max(
            valid,
            key=lambda item: (
                item.confidence,
                item.priority,
                max(fuzz.token_set_ratio(item.name, other.name) for other in valid if other is not item) if len(valid) > 1 else 0,
            ),
        )
    else:
        best = max(valid, key=lambda item: (item.confidence, item.priority, len(item.name)))

    if best.confidence < 0.62:
        warnings.append(
            f"Company candidate '{best.name}' came from low-confidence evidence ({best.evidence}); live verification may be limited."
        )
    return best.name, best.confidence, best.evidence, warnings


def extract_company(text: str, job_url: str | None = None) -> str | None:
    company, _, _, _ = extract_company_metadata(text, job_url)
    return company


def extract_job_title(text: str) -> str | None:
    json_ld_title = extract_json_ld_job_title(text)
    if json_ld_title:
        return json_ld_title

    for title, _, _ in title_company_patterns(text):
        if title:
            return title[:100]

    patterns = [
        r"(?:job title|role|position)\s*[:\-]\s*([^\n\r]+)",
        r"we(?:'re| are)\s+hiring\s+(?:a|an)?\s*([A-Z][A-Za-z0-9 /\-+]{3,80})",
        r"we\s+are\s+seeking\s+(?:an|a)?\s*([A-Z][A-Za-z0-9 /\-&+]{3,80}?)(?:\s+who\b|\s+to\b|\.|\n)",
        r"successful candidate will(?:\s+be)?\s+(?:an|a)?\s*([A-Z][A-Za-z0-9 /\-&+]{3,80}?)(?:\s+who\b|\s+with\b|\.|\n)",
        r"\b((?:(?:Senior|Staff|Principal|Lead|Junior)\s+)?(?:Software Engineer|Full Stack Engineer|Frontend Engineer|Backend Engineer|Data Analyst|Product Manager|Customer Success Manager|Sales Representative))\b",
    ]
    title = find_first(patterns, text)
    if title:
        title = re.split(r"\b(?:company|location|salary|compensation|responsibilities)\b\s*[:\-]?", title, flags=re.IGNORECASE)[0]
        title = re.split(r"\s{2,}| at |,|\||[.]", title)[0].strip()
        return title[:100]
    linkedin_title, _, _ = parse_linkedin_title(text)
    if linkedin_title:
        return linkedin_title[:100]
    return None


def extract_salary(text: str) -> str | None:
    money = r"(?:\$|USD\s*|CAD\s*|€|£)\s?\d{2,3}(?:,\d{3})?(?:k|K)?"
    patterns = [
        rf"({money}\s*(?:-|to|–)\s*{money}(?:\s*(?:per year|annually|/year|yr|hour|/hr|monthly))?)",
        rf"((?:salary|compensation|pay)\s*[:\-]?\s*{money}(?:\s*(?:-|to|–)\s*{money})?)",
        r"(\d{2,3}k\s*(?:-|to|–)\s*\d{2,3}k\s*(?:USD|CAD|EUR|GBP)?)",
    ]
    salary = find_first(patterns, text)
    return salary


def extract_location(text: str) -> str | None:
    location = find_first(
        [
            r"(?:location|work location)\s*[:\-]\s*([^\n\r]+)",
            r"(?:based in|located in)\s+([A-Za-z ,.-]{2,80})",
        ],
        text,
    )
    if location:
        return location
    _, _, linkedin_location = parse_linkedin_title(text)
    return linkedin_location


def extract_remote_type(text: str) -> str | None:
    lower = text.lower()
    if has_hard_hybrid_or_onsite_requirement(text):
        if any(phrase in lower for phrase in ["onsite", "on-site", "must commute", "commute"]):
            return "Onsite"
        return "Hybrid"
    if has_optional_remote_choice(text):
        return "Flexible remote option"
    if "hybrid" in lower:
        return "Hybrid"
    if "remote-first" in lower:
        return "Remote-first"
    if "work from anywhere" in lower or "worldwide" in lower:
        return "Work from anywhere"
    if "fully remote" in lower or "100% remote" in lower:
        return "Fully remote"
    if "remote" in lower:
        return "Remote unclear"
    return None


def extract_allowed_countries(text: str) -> list[str]:
    lower = text.lower()
    if any(phrase in lower for phrase in ["worldwide", "work from anywhere", "global applicants welcome", "open to global applicants"]):
        return ["Worldwide"]

    countries: list[str] = []
    restriction_map = {
        "United States": ["us only", "u.s. only", "usa only", "united states only", "authorized to work in the us"],
        "Canada": ["canada only", "authorized to work in canada"],
        "European Union": ["eu only", "europe only", "european union only"],
        "United Kingdom": ["uk only", "united kingdom only"],
    }
    for country, phrases in restriction_map.items():
        if any(phrase in lower for phrase in phrases):
            countries.append(country)

    located_match = re.search(r"must be located in\s+([A-Za-z ,/]+)", lower)
    if located_match:
        raw = located_match.group(1)
        for country, aliases in COUNTRY_ALIASES.items():
            if any(alias in raw for alias in aliases) and country != "worldwide":
                display = "European Union" if country == "european union" else country.title()
                if display not in countries:
                    countries.append(display)

    return countries


def extract_timezone_requirements(text: str) -> str | None:
    patterns = [
        r"((?:EST|PST|CST|MST|UTC|GMT)[\w +/\-]*(?:overlap|required|hours)[^\n\r.]*)",
        r"((?:overlap|available).{0,40}(?:EST|PST|CST|MST|UTC|GMT)[^\n\r.]*)",
        r"((?:within|between)\s+\d{1,2}\s*(?:and|-)\s*\d{1,2}\s+hours?\s+of\s+(?:EST|PST|UTC|GMT)[^\n\r.]*)",
    ]
    return find_first(patterns, text)


def extract_work_authorization(text: str) -> str | None:
    patterns = [
        r"((?:must|requires?|need).{0,45}(?:work authorization|work authorisation|citizenship|permanent residency|visa sponsorship)[^\n\r.]*)",
        r"((?:authorized|authorised)\s+to\s+work\s+in\s+[A-Za-z .]+)",
    ]
    return find_first(patterns, text)


def extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s)>\]]+", text)


def extract_apply_url(text: str, job_url: str | None) -> str | None:
    urls = extract_urls(text)
    trusted_terms = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com", "jobs.", "careers.")
    for url in [job_url, *urls]:
        if not url:
            continue
        lower = url.lower()
        if any(term in lower for term in trusted_terms):
            return url.strip().rstrip(".,")
    return job_url or (urls[0].strip().rstrip(".,") if urls else None)


def extract_contact_methods(text: str) -> tuple[list[str], list[str]]:
    contacts: list[str] = []
    suspicious: list[str] = []
    for email in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
        contacts.append(email)
        domain = email.split("@")[-1].lower()
        if domain in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "proton.me", "protonmail.com"}:
            suspicious.append(email)

    lower = text.lower()
    if "telegram" in lower:
        contacts.append("Telegram")
        suspicious.append("Telegram")
    if "whatsapp" in lower:
        contacts.append("WhatsApp")
        if "whatsapp only" in lower or "only on whatsapp" in lower:
            suspicious.append("WhatsApp only")
    return sorted(set(contacts)), sorted(set(suspicious))


def extract_scam_phrases(text: str) -> list[str]:
    lower = text.lower()
    return sorted({phrase for phrase in SCAM_PHRASES if phrase in lower})


def extract_required_skills(text: str) -> list[str]:
    lower = text.lower()
    return sorted({skill for skill in SKILL_KEYWORDS if skill in lower})


def extract_seniority(text: str) -> str | None:
    lower = text.lower()
    for label in ["principal", "staff", "senior", "lead", "mid-level", "junior", "entry-level", "intern"]:
        if label in lower:
            return label.title()
    if re.search(r"\b[5-9]\+?\s+years", lower):
        return "Senior"
    if re.search(r"\b[0-2]\+?\s+years", lower):
        return "Junior"
    return None


def has_professional_domain(extracted: ExtractedJob) -> bool:
    urls = [extracted.apply_url] if extracted.apply_url else []
    emails = [contact for contact in extracted.contact_methods if "@" in contact]
    for email in emails:
        domain = email.split("@")[-1].lower()
        if domain not in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "proton.me", "protonmail.com"}:
            return True
    for url in urls:
        domain = urlparse(url).netloc.lower()
        if domain and not any(short in domain for short in ["bit.ly", "tinyurl", "t.me", "wa.me"]):
            return True
    return False


def extract_features(job_description: str, job_url: str | None = None) -> ExtractedJob:
    text = clean_job_text(job_description)
    company, company_confidence, company_evidence, extraction_warnings = extract_company_metadata(text, job_url)
    extracted = ExtractedJob(
        job_title=extract_job_title(text),
        company=company,
        company_confidence=company_confidence,
        company_evidence=company_evidence,
        salary=extract_salary(text),
        location=extract_location(text),
        remote_type=extract_remote_type(text),
        allowed_countries=extract_allowed_countries(text),
        timezone_requirements=extract_timezone_requirements(text),
        work_authorization=extract_work_authorization(text),
        apply_url=extract_apply_url(text, job_url),
        required_skills=extract_required_skills(text),
        seniority_level=extract_seniority(text),
        extraction_warnings=extraction_warnings,
    )
    extracted.contact_methods, extracted.suspicious_contact_methods = extract_contact_methods(text)
    extracted.scam_phrases = extract_scam_phrases(text)
    return extracted
