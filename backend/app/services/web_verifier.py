from __future__ import annotations

import html
import base64
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

try:  # Optional in local ad-hoc test environments; installed in Docker.
    import tldextract
except Exception:  # pragma: no cover
    tldextract = None

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover
    fuzz = None

try:
    from backend.ml.feature_extractor import company_candidate_rejection_reason
except Exception:  # pragma: no cover - keep verifier importable if ml path is unavailable.
    company_candidate_rejection_reason = None


REVIEW_DOMAINS = {
    "glassdoor.com",
    "indeed.com",
    "trustpilot.com",
    "comparably.com",
    "teamblind.com",
    "ambitionbox.com",
    "levels.fyi",
}

PROFILE_DOMAINS = {
    "linkedin.com",
    "crunchbase.com",
    "wellfound.com",
    "ycombinator.com",
    "theorg.com",
    "builtin.com",
}

RISK_TERMS = {
    "scam",
    "fraud",
    "fake",
    "impersonation",
    "lawsuit",
    "warning",
    "complaint",
    "ripoff",
}


@dataclass
class WebSource:
    title: str
    url: str
    snippet: str
    source_type: str


@dataclass
class CompanyVerification:
    company: str | None
    status: str
    score: int
    searched_at: str
    search_queries: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: list[WebSource] = field(default_factory=list)

    def model_dict(self) -> dict[str, object]:
        return {
            "company": self.company,
            "status": self.status,
            "score": self.score,
            "searched_at": self.searched_at,
            "search_queries": self.search_queries,
            "signals": self.signals,
            "warnings": self.warnings,
            "sources": [source.__dict__ for source in self.sources],
        }


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def clean_text(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def domain_for(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def registered_domain_for(url: str) -> str:
    domain = domain_for(url)
    if not domain:
        return ""
    if tldextract:
        extracted = tldextract.extract(domain)
        if extracted.domain and extracted.suffix:
            return f"{extracted.domain}.{extracted.suffix}"
    parts = domain.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain


def token_set_ratio(left: str, right: str) -> int:
    if not left or not right:
        return 0
    if fuzz:
        return int(fuzz.token_set_ratio(left, right))
    left_tokens = set(re.findall(r"[a-z0-9]+", left.lower()))
    right_tokens = set(re.findall(r"[a-z0-9]+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0
    overlap = len(left_tokens & right_tokens)
    return round(200 * overlap / (len(left_tokens) + len(right_tokens)))


def company_candidate_looks_valid(company: str | None) -> bool:
    if not company:
        return False
    if company_candidate_rejection_reason:
        return company_candidate_rejection_reason(company) is None
    return bool(re.search(r"[A-Z]", company)) and "," not in company and len(company) <= 70


def source_matches_company(company: str, title: str, url: str, snippet: str) -> bool:
    company_slug = slug(company)
    if not company_slug or len(company_slug) < 3:
        return False
    domain = registered_domain_for(url)
    domain_slug = slug(domain.split(".")[0])
    host_slug = slug(domain_for(url).split(":")[0])
    text = f"{title} {snippet}".lower()
    text_slug = slug(text)

    if company_slug in host_slug or company_slug in domain_slug:
        return True
    if company_slug in text_slug:
        return True
    return token_set_ratio(company, f"{title} {snippet} {domain}") >= 86


def classify_source(company: str, title: str, url: str, snippet: str) -> str:
    domain = domain_for(url)
    text = f"{title} {snippet} {url}".lower()
    company_related = source_matches_company(company, title, url, snippet)
    if company_related and any(term in text for term in RISK_TERMS):
        return "risk_report"
    if company_related and any(domain.endswith(review_domain) for review_domain in REVIEW_DOMAINS):
        return "employee_or_company_review"
    if company_related and any(domain.endswith(profile_domain) for profile_domain in PROFILE_DOMAINS):
        return "company_profile"
    if company_related and not any(domain.endswith(review_domain) for review_domain in REVIEW_DOMAINS):
        company_slug = slug(company)
        domain_slug = slug(domain.split(":")[0])
        if company_slug and company_slug in domain_slug:
            return "official_company_site"
    if company_related and ("career" in text or "jobs" in text):
        return "career_page"
    return "general_web_result"


def limited_company_verification(company: str | None, searched_at: str, warning: str) -> CompanyVerification:
    return CompanyVerification(
        company=company,
        status="Limited evidence",
        score=35,
        searched_at=searched_at,
        warnings=[warning],
    )


def ddg_results(query: str, timeout: float) -> list[WebSource]:
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 RemoteTrustAI/0.1",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        document = response.read(700_000).decode("utf-8", errors="ignore")

    results: list[WebSource] = []
    blocks = re.split(r'class="result', document)
    for block in blocks[1:]:
        href_match = re.search(r'class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.DOTALL)
        if not href_match:
            continue
        title = clean_text(href_match.group(2))
        result_url = html.unescape(href_match.group(1))
        snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>|class="result__snippet"[^>]*>(.*?)</div>', block, flags=re.DOTALL)
        snippet = clean_text(next((group for group in (snippet_match.groups() if snippet_match else []) if group), ""))
        if title and result_url.startswith("http"):
            results.append(WebSource(title=title, url=result_url, snippet=snippet, source_type="general_web_result"))
        if len(results) >= 6:
            break
    return results


def decode_bing_url(url: str) -> str:
    parsed = urlparse(html.unescape(url))
    query = parse_qs(parsed.query)
    encoded = query.get("u", [""])[0]
    if encoded.startswith("a1"):
        payload = encoded[2:]
        payload += "=" * (-len(payload) % 4)
        try:
            return base64.urlsafe_b64decode(payload).decode("utf-8", errors="ignore")
        except Exception:
            return url
    return unquote(url)


def bing_results(query: str, timeout: float) -> list[WebSource]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 RemoteTrustAI/0.1",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        document = response.read(900_000).decode("utf-8", errors="ignore")

    results: list[WebSource] = []
    for block in re.findall(r'<li class="b_algo".*?</li>', document, flags=re.DOTALL):
        href_match = re.search(r"<h2[^>]*>\s*<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>\s*</h2>", block, flags=re.DOTALL)
        if not href_match:
            continue
        title = clean_text(href_match.group(2))
        result_url = decode_bing_url(href_match.group(1))
        snippet_match = re.search(r"<p[^>]*>(.*?)</p>", block, flags=re.DOTALL)
        snippet = clean_text(snippet_match.group(1)) if snippet_match else ""
        if title and result_url.startswith("http") and "bing.com/search" not in result_url:
            results.append(WebSource(title=title, url=result_url, snippet=snippet, source_type="general_web_result"))
        if len(results) >= 6:
            break
    return results


def search_results(query: str, timeout: float) -> list[WebSource]:
    results = ddg_results(query, timeout)
    if results:
        return results
    return bing_results(query, timeout)


def unique_sources(sources: list[WebSource]) -> list[WebSource]:
    seen: set[str] = set()
    unique: list[WebSource] = []
    for source in sources:
        key = re.sub(r"[?#].*$", "", source.url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def score_sources(company: str, sources: list[WebSource], apply_url: str | None) -> tuple[int, list[str], list[str]]:
    score = 45
    signals: list[str] = []
    warnings: list[str] = []
    types = {source.source_type for source in sources}

    if "official_company_site" in types or "career_page" in types:
        score += 20
        signals.append("Official company or careers page found in live web results")
    if "company_profile" in types:
        score += 12
        signals.append("Company profile found on a recognizable public platform")
    if "employee_or_company_review" in types:
        score += 12
        signals.append("Employee/company review source found")
    if "risk_report" in types:
        score -= 25
        warnings.append("Live search found scam, fraud, complaint, or warning language")

    if apply_url:
        apply_domain = domain_for(apply_url)
        company_slug = slug(company)
        if company_slug and company_slug in slug(apply_domain):
            score += 8
            signals.append("Apply URL domain appears related to the company name")

    if not sources:
        warnings.append("No live web evidence was found or search was blocked")
    elif not ({"official_company_site", "career_page", "company_profile"} & types):
        warnings.append("No official company or recognized company profile result was found")
    if "employee_or_company_review" not in types:
        warnings.append("No employee-review source was found in the first live results")

    return max(0, min(100, score)), signals, warnings


def status_for(score: int, warnings: list[str]) -> str:
    if any("scam, fraud" in warning for warning in warnings) and score < 55:
        return "Risk signals"
    if score >= 75:
        return "Strong evidence"
    if score >= 58:
        return "Some evidence"
    return "Limited evidence"


@lru_cache(maxsize=128)
def verify_company_web_cached(company: str, apply_url: str | None) -> CompanyVerification:
    enabled = os.getenv("WEB_VERIFICATION_ENABLED", "true").lower() not in {"0", "false", "no"}
    timeout = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "5"))
    max_sources = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "7"))
    searched_at = now_iso()

    if not company:
        return CompanyVerification(
            company=None,
            status="Limited evidence",
            score=35,
            searched_at=searched_at,
            warnings=["No company name detected, so live web verification could not run"],
        )

    queries = [
        f'"{company}" official careers',
        f'"{company}" employee reviews Glassdoor Indeed',
        f'"{company}" scam OR fraud OR impersonation',
    ]
    if not enabled:
        return CompanyVerification(
            company=company,
            status="Limited evidence",
            score=45,
            searched_at=searched_at,
            search_queries=queries,
            warnings=["Live web verification is disabled by environment configuration"],
        )

    gathered: list[WebSource] = []
    search_warnings: list[str] = []
    for query in queries:
        try:
            gathered.extend(search_results(query, timeout=timeout))
        except Exception as exc:  # Search engines can rate-limit or block HTML access.
            search_warnings.append(f"Search query failed or was blocked: {query}")
            if os.getenv("REMOTE_TRUST_DEBUG_SEARCH"):
                search_warnings.append(str(exc))

    sources = unique_sources(gathered)
    for source in sources:
        source.source_type = classify_source(company, source.title, source.url, source.snippet)
    sources = sources[:max_sources]
    score, signals, warnings = score_sources(company, sources, apply_url)
    warnings = [*warnings, *search_warnings]
    return CompanyVerification(
        company=company,
        status=status_for(score, warnings),
        score=score,
        searched_at=searched_at,
        search_queries=queries,
        signals=signals,
        warnings=warnings,
        sources=sources,
    )


def verify_company_web(
    company: str | None,
    apply_url: str | None,
    company_confidence: float | None = None,
    company_evidence: str | None = None,
) -> CompanyVerification:
    searched_at = now_iso()
    skip_warning = "Company name could not be verified from the posting, so live company verification was skipped."
    if not company:
        return limited_company_verification(None, searched_at, skip_warning)
    if not company_candidate_looks_valid(company):
        return limited_company_verification(company, searched_at, skip_warning)
    if company_confidence is not None and company_confidence < 0.70:
        return CompanyVerification(
            company=company,
            status="Limited evidence",
            score=40,
            searched_at=searched_at,
            warnings=[
                skip_warning,
                f"Company extraction confidence was {company_confidence:.2f}"
                + (f" from {company_evidence}" if company_evidence else ""),
            ],
        )
    return verify_company_web_cached(company or "", apply_url)
