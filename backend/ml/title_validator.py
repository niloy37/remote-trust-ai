from __future__ import annotations

import re
from difflib import SequenceMatcher

from .schemas import TitleValidation


SENIORITY_WORDS = {
    "intern",
    "internship",
    "junior",
    "associate",
    "mid",
    "mid-level",
    "senior",
    "staff",
    "principal",
    "lead",
    "head",
    "director",
    "vp",
}

NOISE_WORDS = {
    "remote",
    "hybrid",
    "onsite",
    "on-site",
    "full-time",
    "part-time",
    "contract",
    "contractor",
    "freelance",
    "temporary",
    "worldwide",
    "global",
    "usa",
    "canada",
    "europe",
    "eu",
}

SUSPICIOUS_TITLE_TERMS = {
    "cashflow",
    "cash",
    "money",
    "income",
    "guru",
    "ninja",
    "rockstar",
    "wizard",
    "hustler",
    "boss",
    "millionaire",
    "crypto",
    "trader",
    "telegram",
    "whatsapp",
}

CLICKBAIT_PATTERNS = [
    "earn",
    "daily pay",
    "no interview",
    "guaranteed",
    "urgent",
    "easy money",
    "work few hours",
]

TITLE_FAMILIES = [
    {
        "canonical": "Software Engineer",
        "aliases": ["software developer", "backend engineer", "frontend engineer", "full stack engineer", "application developer"],
        "keywords": ["software", "developer", "engineer", "backend", "frontend", "full stack", "api", "python", "typescript", "react", "java", "code"],
    },
    {
        "canonical": "Engineering Intern",
        "aliases": ["software engineering intern", "engineer intern", "forward deployed engineering intern", "technical intern"],
        "keywords": ["intern", "engineering", "software", "python", "api", "computer science", "student", "mentor", "technical"],
    },
    {
        "canonical": "Data Analyst",
        "aliases": ["business analyst", "analytics analyst", "data analytics specialist", "reporting analyst"],
        "keywords": ["data", "analytics", "sql", "dashboard", "excel", "python", "insights", "metrics", "reporting"],
    },
    {
        "canonical": "Data Scientist",
        "aliases": ["machine learning scientist", "ml scientist", "ai scientist", "applied scientist"],
        "keywords": ["machine learning", "model", "statistics", "python", "experiment", "prediction", "ai", "data"],
    },
    {
        "canonical": "Machine Learning Engineer",
        "aliases": ["ml engineer", "ai engineer", "ai agent engineer", "applied ai engineer"],
        "keywords": ["machine learning", "ml", "ai", "model", "llm", "agent", "python", "deployment", "inference"],
    },
    {
        "canonical": "Product Manager",
        "aliases": ["technical product manager", "product owner", "product lead"],
        "keywords": ["roadmap", "product", "customers", "discovery", "spec", "stakeholder", "analytics"],
    },
    {
        "canonical": "Project Manager",
        "aliases": ["program manager", "delivery manager", "implementation manager"],
        "keywords": ["project", "program", "delivery", "timeline", "stakeholder", "coordination", "implementation"],
    },
    {
        "canonical": "Designer",
        "aliases": ["product designer", "ux designer", "ui designer", "visual designer"],
        "keywords": ["design", "ux", "ui", "prototype", "figma", "research", "user", "interface"],
    },
    {
        "canonical": "Marketing Manager",
        "aliases": ["growth marketer", "digital marketing manager", "campaign manager"],
        "keywords": ["marketing", "campaign", "paid media", "growth", "content", "seo", "analytics"],
    },
    {
        "canonical": "Sales Representative",
        "aliases": ["account executive", "sales development representative", "business development representative"],
        "keywords": ["sales", "pipeline", "customers", "quota", "crm", "prospect", "account"],
    },
    {
        "canonical": "Customer Success Manager",
        "aliases": ["customer support specialist", "support specialist", "customer experience specialist"],
        "keywords": ["customer", "support", "tickets", "success", "communication", "help center", "saas"],
    },
    {
        "canonical": "Administrative Assistant",
        "aliases": ["virtual assistant", "operations assistant", "executive assistant"],
        "keywords": ["administrative", "assistant", "calendar", "scheduling", "documents", "operations", "email"],
    },
    {
        "canonical": "DevOps Engineer",
        "aliases": ["site reliability engineer", "cloud engineer", "platform engineer"],
        "keywords": ["cloud", "aws", "docker", "kubernetes", "infrastructure", "ci", "reliability", "devops"],
    },
    {
        "canonical": "Recruiter",
        "aliases": ["talent acquisition specialist", "technical recruiter", "recruiting coordinator"],
        "keywords": ["recruiting", "talent", "candidate", "sourcing", "interview", "hiring"],
    },
    {
        "canonical": "Finance Analyst",
        "aliases": ["financial analyst", "accounting analyst", "bookkeeper"],
        "keywords": ["finance", "financial", "accounting", "budget", "forecast", "bookkeeping", "excel"],
    },
]


def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9+#]+", value.lower())


def normalize_title(title: str | None) -> str | None:
    if not title:
        return None
    value = title.lower()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\b(remote|hybrid|onsite|on-site)\b", " ", value)
    value = re.sub(r"\b(full[- ]?time|part[- ]?time|contract(or)?|freelance|internship)\b", " ", value)
    value = re.sub(r"[^a-z0-9+# ]+", " ", value)
    tokens = [token for token in tokenize(value) if token not in NOISE_WORDS]
    # Keep intern/seniority in the original evidence, but remove most seniority for canonical matching.
    reduced = [token for token in tokens if token not in SENIORITY_WORDS or token == "intern"]
    return " ".join(reduced).strip() or " ".join(tokens).strip() or None


def title_variants(family: dict[str, object]) -> list[str]:
    return [str(family["canonical"]), *[str(alias) for alias in family["aliases"]]]


def token_overlap(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def similarity(left: str, right: str) -> float:
    return max(token_overlap(left, right), SequenceMatcher(None, left.lower(), right.lower()).ratio())


def best_title_matches(normalized_title: str | None) -> list[tuple[str, float, dict[str, object]]]:
    if not normalized_title:
        return []
    matches: list[tuple[str, float, dict[str, object]]] = []
    for family in TITLE_FAMILIES:
        best_score = 0.0
        best_label = str(family["canonical"])
        for variant in title_variants(family):
            score = similarity(normalized_title, normalize_title(variant) or variant)
            if score > best_score:
                best_score = score
                best_label = str(family["canonical"])
        matches.append((best_label, best_score, family))
    return sorted(matches, key=lambda item: item[1], reverse=True)


def description_support_score(description: str, family: dict[str, object] | None) -> tuple[int, list[str]]:
    if not family:
        return 0, []
    lower = description.lower()
    hits = [keyword for keyword in family["keywords"] if str(keyword).lower() in lower]
    if len(hits) >= 4:
        return 24, [f"Description supports the title family with: {', '.join(hits[:5])}"]
    if len(hits) >= 2:
        return 16, [f"Description partially supports the title family with: {', '.join(hits[:5])}"]
    if len(hits) == 1:
        return 8, [f"Description has one supporting title-family signal: {hits[0]}"]
    return -8, ["Description has limited evidence for the extracted title family"]


def suspicious_shape(title: str, description: str) -> tuple[int, list[str]]:
    warnings: list[str] = []
    penalty = 0
    tokens = tokenize(title)
    lower_title = title.lower()
    lower_description = description.lower()

    suspicious_terms = sorted(term for term in SUSPICIOUS_TITLE_TERMS if term in lower_title)
    if suspicious_terms:
        penalty += 18
        warnings.append("Title contains hype/scam-adjacent terms: " + ", ".join(suspicious_terms[:4]))

    if len(tokens) >= 8:
        penalty += 8
        warnings.append("Title is unusually long for an occupation label")

    if re.search(r"[!?$]{2,}", title) or title.count("/") >= 3:
        penalty += 8
        warnings.append("Title has excessive punctuation or slash-separated fragments")

    clickbait_hits = [pattern for pattern in CLICKBAIT_PATTERNS if pattern in lower_title or pattern in lower_description]
    if clickbait_hits and suspicious_terms:
        penalty += 12
        warnings.append("Title appears together with clickbait hiring language")

    generic_tokens = {"remote", "operator", "specialist", "agent", "assistant", "associate", "manager"}
    meaningful = [token for token in tokens if token not in generic_tokens and token not in SENIORITY_WORDS]
    if len(tokens) >= 3 and not meaningful:
        penalty += 10
        warnings.append("Title is too generic to map to a clear occupation")

    return penalty, warnings


def validate_job_title(title: str | None, description: str) -> TitleValidation:
    normalized = normalize_title(title)
    if not title or not normalized:
        return TitleValidation(
            original_title=title,
            normalized_title=normalized,
            verdict="Unusual",
            score=45,
            evidence=[],
            warnings=["No job title was detected for validation"],
        )

    matches = best_title_matches(normalized)
    best_label, best_match, best_family = matches[0] if matches else ("", 0.0, None)
    support_score, evidence = description_support_score(description, best_family)
    penalty, warnings = suspicious_shape(title, description)

    score = round(48 + best_match * 38 + support_score - penalty)
    score = max(0, min(100, score))
    closest = [label for label, match_score, _ in matches[:3] if match_score >= 0.38]
    lower_title = title.lower()
    emerging_modifier = any(term in lower_title for term in ["forward deployed", "ai agent", "applied ai", "workflow"]) or "(" in title

    if score >= 82 and best_match >= 0.72:
        verdict = "Recognized"
    elif score >= 68 and (best_match >= 0.50 or support_score >= 16):
        verdict = "Plausible"
    elif score < 42 or penalty >= 28:
        verdict = "Suspicious"
    else:
        verdict = "Unusual"

    if best_match >= 0.72:
        evidence.insert(0, f"Title closely matches known occupation: {best_label}")
    elif best_match >= 0.50:
        evidence.insert(0, f"Title is similar to known occupation: {best_label}")
    elif best_label:
        warning = f"Title does not closely match known occupation labels; nearest is {best_label}"
        if warnings:
            warnings.append(warning)
        else:
            warnings.insert(0, warning)

    if verdict == "Recognized" and emerging_modifier and support_score >= 16:
        verdict = "Plausible"
        score = min(score, 88)
        evidence.insert(0, "Emerging or specialized title modifier is supported by the job description")

    return TitleValidation(
        original_title=title,
        normalized_title=normalized,
        verdict=verdict,
        score=score,
        closest_known_titles=closest,
        evidence=evidence,
        warnings=warnings,
    )
