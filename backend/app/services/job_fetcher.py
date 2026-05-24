from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PROTECTED_JOB_BOARDS = ("linkedin.com", "indeed.com")
ATS_HINTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com")


@dataclass
class FetchResult:
    text: str
    source: str
    warning: str | None = None


class JobFetchError(ValueError):
    pass


def domain_for(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")

def infer_company_from_domain(url: str) -> str | None:

    domain = domain_for(url)

    ats_patterns = {
        "greenhouse.io": lambda d, u: urlparse(u).path.split("/")[1],
        "lever.co": lambda d, u: urlparse(u).path.split("/")[1],
        "ashbyhq.com": lambda d, u: urlparse(u).path.split("/")[1],
        "workable.com": lambda d, u: urlparse(u).path.split("/")[1],
    }

    for ats, extractor in ats_patterns.items():

        if ats in domain:

            try:

                company = extractor(domain, url)

                company = company.replace("-", " ")

                return company.title()

            except Exception:
                return None

    return None


def looks_like_protected_board(url: str) -> bool:
    domain = domain_for(url)
    return any(board in domain for board in PROTECTED_JOB_BOARDS)


def fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 RemoteTrustAI/0.1"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                raise JobFetchError("The URL did not return readable HTML or plain text.")
            return response.read(1_000_000).decode("utf-8", errors="ignore")
    except HTTPError as exc:
        if exc.code in {401, 403, 429} and looks_like_protected_board(url):
            raise JobFetchError(
                "This job board blocks automated crawling. Paste the job description, or use the future browser extension path for pages that require login/session access."
            ) from exc
        raise JobFetchError(f"Could not fetch the job URL. HTTP {exc.code}.") from exc
    except (URLError, TimeoutError) as exc:
        raise JobFetchError(f"Could not fetch the job URL. Paste the job description instead. Details: {exc}") from exc


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</p\s*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def json_ld_blocks(document: str) -> list[Any]:
    blocks: list[Any] = []
    for match in re.finditer(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        document,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        raw = html.unescape(match.group(1)).strip()
        if not raw:
            continue
        try:
            blocks.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return blocks


def iter_json_nodes(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        children = [node]
        if isinstance(node.get("@graph"), list):
            for item in node["@graph"]:
                children.extend(iter_json_nodes(item))
        return children
    if isinstance(node, list):
        children: list[dict[str, Any]] = []
        for item in node:
            children.extend(iter_json_nodes(item))
        return children
    return []


def first_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return strip_tags(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [first_text(item) for item in value]
        return ", ".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("name", "text", "addressLocality", "addressRegion", "addressCountry"):
            if key in value:
                text = first_text(value[key])
                if text:
                    return text
    return None


def format_salary(base_salary: Any) -> str | None:
    if not isinstance(base_salary, dict):
        return first_text(base_salary)
    currency = base_salary.get("currency") or base_salary.get("salaryCurrency")
    value = base_salary.get("value")
    if isinstance(value, dict):
        minimum = value.get("minValue")
        maximum = value.get("maxValue")
        unit = value.get("unitText")
        if minimum and maximum:
            return f"{currency or ''} {minimum}-{maximum} {unit or ''}".strip()
        if value.get("value"):
            return f"{currency or ''} {value['value']} {unit or ''}".strip()
    return first_text(value)


def extract_json_ld_job(document: str) -> str | None:
    for block in json_ld_blocks(document):
        for node in iter_json_nodes(block):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if "JobPosting" not in types:
                continue

            organization = node.get("hiringOrganization")
            location = node.get("jobLocation") or node.get("applicantLocationRequirements")
            parts = [
                f"Job Title: {first_text(node.get('title'))}" if first_text(node.get("title")) else None,
                f"Company: {first_text(organization)}" if first_text(organization) else None,
                f"Location: {first_text(location)}" if first_text(location) else None,
                f"Salary: {format_salary(node.get('baseSalary'))}" if format_salary(node.get("baseSalary")) else None,
                f"Employment type: {first_text(node.get('employmentType'))}" if first_text(node.get("employmentType")) else None,
                f"Description: {first_text(node.get('description'))}" if first_text(node.get("description")) else None,
                f"Apply URL: {first_text(node.get('url'))}" if first_text(node.get("url")) else None,
            ]
            text = "\n".join(part for part in parts if part)
            if len(text) > 120:
                return text
    return None


def extract_meta_summary(document: str) -> str | None:
    pieces: list[str] = []
    for name in ("og:title", "twitter:title", "title", "description", "og:description", "twitter:description"):
        pattern = rf"<meta[^>]+(?:name|property)=[\"']{re.escape(name)}[\"'][^>]+content=[\"']([^\"']+)[\"'][^>]*>"
        match = re.search(pattern, document, flags=re.IGNORECASE)
        if match:
            pieces.append(strip_tags(match.group(1)))
    if pieces:
        return "\n".join(dict.fromkeys(pieces))
    title_match = re.search(r"<title[^>]*>(.*?)</title>", document, flags=re.IGNORECASE | re.DOTALL)
    return strip_tags(title_match.group(1)) if title_match else None


def extract_visible_text(document: str) -> str:
    cleaned = re.sub(r"<(script|style|noscript|svg|header|footer|nav|aside)[^>]*>.*?</\1>", " ", document, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)
    return normalize_text(strip_tags(cleaned))


def page_looks_blocked(text: str) -> bool:
    lower = text.lower()
    blocked_markers = [
        "sign in to view",
        "login to view",
        "captcha",
        "security check",
        "unusual traffic",
        "enable javascript",
        "access denied",
    ]
    return any(marker in lower for marker in blocked_markers)


def fetch_job_description(url: str) -> FetchResult:
    document = fetch_html(url)

    json_ld_text = extract_json_ld_job(document)

    visible_text = extract_visible_text(document)

    meta_text = extract_meta_summary(document)

    inferred_company = infer_company_from_domain(url)

    candidates = [json_ld_text, visible_text, meta_text]
    best = max((candidate for candidate in candidates if candidate), key=len, default="")
    if inferred_company and "Company:" not in best:
        best = f"Company: {inferred_company}\n" + best
        
    best = best[:30_000]

    if len(best) < 120 or page_looks_blocked(best):
        if looks_like_protected_board(url):
            raise JobFetchError(
                "This page did not expose enough public job text. LinkedIn and Indeed commonly hide content behind login, bot checks, or dynamic rendering. Paste the description for this MVP; a browser extension can read the page with the user's consent later."
            )
        raise JobFetchError("Fetched page did not contain enough readable job text. Paste the job description instead.")

    source = "json-ld JobPosting" if json_ld_text and len(json_ld_text) >= len(visible_text) else "cleaned page text"
    warning = None
    if looks_like_protected_board(url):
        warning = "This is a protected job board, so extraction may be incomplete."
    elif not any(hint in domain_for(url) for hint in ATS_HINTS):
        warning = "Generic page extraction was used; ATS career pages usually extract more accurately."

    return FetchResult(text=best, source=source, warning=warning)
