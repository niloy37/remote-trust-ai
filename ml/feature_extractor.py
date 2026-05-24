from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

from .schemas import ExtractedJob


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

GLOBAL_NOISE_PATTERNS = [
    "privacy policy",
    "cookie policy",
    "terms of service",
    "terms and conditions",
    "sign in",
    "log in",
    "create account",
    "join now",
    "apply now",
    "see more jobs",
    "recommended jobs",
    "all rights reserved",
    "do not sell my personal information",
    "by using this site",
    "accept cookies",
    "cookie preferences",
]

LINKEDIN_REMOTE_FILTER_PATTERN = re.compile(r"\b(?:on-site|onsite)\s+or\s+hybrid\s+or\s+remote\b", re.IGNORECASE)
RESULT_COUNT_PATTERN = re.compile(r"\b\d+\+?\s+results?\b", re.IGNORECASE)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_page_chrome_noise_line(line: str) -> bool:
    
    normalized = normalize_text(line)
    lower = normalized.lower()
    if not lower:
        return True
    if any(marker in lower for marker in LINKEDIN_SEARCH_CHROME_MARKERS):
        return True
    if any(pattern in lower for pattern in GLOBAL_NOISE_PATTERNS):
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


def extract_company(text: str) -> str | None:
    patterns = [
        r"(?:company|organization|employer)\s*[:\-]\s*([^\n\r]+)",
        r"(?:join|at)\s+([A-Z][A-Za-z0-9&.,'\- ]{2,60})\s+(?:as|to|and|,)",
        r"about\s+(?!the job\b|the role\b|this role\b)([A-Z][A-Za-z0-9&.,'\- ]{2,60})",
    ]
    company = find_first(patterns, text)
    if company:
        company = re.split(r"\b(?:job title|title|role|position|location|salary)\b\s*[:\-]?", company, flags=re.IGNORECASE)[0]
        company = re.split(r"\s{2,}|[|.]", company)[0].strip()
        if len(company.split()) <= 8 and company.lower() not in {"the job", "the role", "this role"}:
            return company
    _, linkedin_company, _ = parse_linkedin_title(text)
    if linkedin_company and len(linkedin_company.split()) <= 10:
        return linkedin_company
    return None


def extract_job_title(text: str) -> str | None:
    patterns = [
        r"(?:job title|role|position)\s*[:\-]\s*([^\n\r]+)",
        r"we(?:'re| are)\s+hiring\s+(?:a|an)?\s*([A-Z][A-Za-z0-9 /\-+]{3,80})",
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
    if any(phrase in lower for phrase in ["hybrid", "remote but office", "office required"]):
        return "Hybrid"
    if any(phrase in lower for phrase in ["onsite", "on-site", "must commute"]):
        return "Onsite"
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
    extracted = ExtractedJob(
        job_title=extract_job_title(text),
        company=extract_company(text),
        salary=extract_salary(text),
        location=extract_location(text),
        remote_type=extract_remote_type(text),
        allowed_countries=extract_allowed_countries(text),
        timezone_requirements=extract_timezone_requirements(text),
        work_authorization=extract_work_authorization(text),
        apply_url=extract_apply_url(text, job_url),
        required_skills=extract_required_skills(text),
        seniority_level=extract_seniority(text),
    )
    extracted.contact_methods, extracted.suspicious_contact_methods = extract_contact_methods(text)
    extracted.scam_phrases = extract_scam_phrases(text)
    return extracted
