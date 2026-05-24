from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

try:  # Installed in Docker; optional for local smoke tests.
    import httpx
except Exception:  # pragma: no cover
    httpx = None

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

from ml.feature_extractor import (
    is_search_or_collection_url,
    provider_for_url,
    text_looks_like_search_collection,
)

PROTECTED_JOB_BOARDS = ("linkedin.com", "indeed.com")
ATS_HINTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com")
PORTAL_HINTS = ("flexjobs.com", "remoteok.com", "weworkremotely.com", "remotive.com", "wellfound.com")
MAX_FETCH_BYTES = 1_200_000


@dataclass
class FetchResult:
    text: str
    source: str
    warning: str | None = None


class JobFetchError(ValueError):
    pass


def domain_for(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        raise JobFetchError("Job URL is empty.")
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise JobFetchError("Provide a valid http or https job URL.")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", parsed.query, ""))


def looks_like_protected_board(url: str) -> bool:
    domain = domain_for(url)
    return any(board in domain for board in PROTECTED_JOB_BOARDS)


def fetch_html(url: str) -> str:
    normalized_url = normalize_url(url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 RemoteTrustAI/0.1"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if httpx:
        try:
            with httpx.Client(follow_redirects=True, timeout=10, headers=headers) as client:
                response = client.get(normalized_url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "text/plain" not in content_type and "application/xhtml" not in content_type:
                    raise JobFetchError("The URL did not return readable HTML or plain text.")
                return response.content[:MAX_FETCH_BYTES].decode(response.encoding or "utf-8", errors="ignore")
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {401, 403, 429} and looks_like_protected_board(normalized_url):
                raise JobFetchError(
                    "This job board blocks automated crawling. Paste the job description, or use the browser extension path for pages that require login/session access."
                ) from exc
            raise JobFetchError(f"Could not fetch the job URL. HTTP {status_code}.") from exc
        except httpx.RequestError as exc:
            raise JobFetchError(f"Could not fetch the job URL. Paste the job description instead. Details: {exc}") from exc

    request = Request(
        normalized_url,
        headers=headers,
    )
    try:
        with urlopen(request, timeout=10) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                raise JobFetchError("The URL did not return readable HTML or plain text.")
            return response.read(MAX_FETCH_BYTES).decode("utf-8", errors="ignore")
    except HTTPError as exc:
        if exc.code in {401, 403, 429} and looks_like_protected_board(normalized_url):
            raise JobFetchError(
                "This job board blocks automated crawling. Paste the job description, or use the browser extension path for pages that require login/session access."
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
    if BeautifulSoup:
        soup = BeautifulSoup(document, "lxml")
        raw_blocks = [script.get_text(" ", strip=True) for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)})]
    else:
        raw_blocks = [
            match.group(1)
            for match in re.finditer(
                r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
                document,
                flags=re.IGNORECASE | re.DOTALL,
            )
        ]
    for raw_block in raw_blocks:
        raw = html.unescape(raw_block).strip()
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
    if BeautifulSoup:
        soup = BeautifulSoup(document, "lxml")
        for name in ("og:title", "twitter:title", "title", "description", "og:description", "twitter:description", "application-name"):
            node = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
            content = strip_tags(node.get("content", "")) if node else ""
            if content:
                pieces.append(content)
        if soup.title and soup.title.string:
            pieces.append(strip_tags(soup.title.string))
        return "\n".join(dict.fromkeys(pieces)) if pieces else None

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
    if BeautifulSoup:
        soup = BeautifulSoup(document, "lxml")
        for selector in [
            "script",
            "style",
            "noscript",
            "svg",
            "header",
            "footer",
            "nav",
            "aside",
            "form",
            "button",
        ]:
            for node in soup.select(selector):
                node.decompose()
        for node in soup.find_all(True):
            marker = " ".join(
                str(value).lower()
                for value in [
                    node.get("id", ""),
                    " ".join(node.get("class", [])),
                    node.get("aria-label", ""),
                ]
            )
            if any(term in marker for term in ["cookie", "banner", "modal", "newsletter"]):
                node.decompose()
        root = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.body or soup
        return normalize_text(root.get_text("\n", strip=True))

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
    normalized_url = normalize_url(url)
    if is_search_or_collection_url(normalized_url):
        raise JobFetchError("This URL appears to be a search, collection, or listing page. Open an individual job posting URL or paste one full job description.")

    document = fetch_html(normalized_url)
    json_ld_text = extract_json_ld_job(document)
    visible_text = extract_visible_text(document)
    meta_text = extract_meta_summary(document)

    candidates = [visible_text, meta_text]
    best = json_ld_text or max((candidate for candidate in candidates if candidate), key=len, default="")
    best = best[:30_000]

    if len(best) < 120 or page_looks_blocked(best):
        if looks_like_protected_board(normalized_url):
            raise JobFetchError(
                "This page did not expose enough public job text. LinkedIn and Indeed commonly hide content behind login, bot checks, or dynamic rendering. Paste the description for this MVP; a browser extension can read the page with the user's consent later."
            )
        raise JobFetchError("Fetched page did not contain enough readable job text. Paste the job description instead.")

    if text_looks_like_search_collection(best):
        raise JobFetchError("Fetched page looks like search results rather than one job posting. Open an individual job posting URL or paste the full posting text.")

    source = "json-ld JobPosting" if json_ld_text else "cleaned page text"
    warning = None
    if looks_like_protected_board(normalized_url):
        warning = "This is a protected job board, so extraction may be incomplete."
    elif provider_for_url(normalized_url):
        warning = None
    elif not any(hint in domain_for(normalized_url) for hint in (*ATS_HINTS, *PORTAL_HINTS)):
        warning = "Generic page extraction was used; ATS career pages usually extract more accurately."

    return FetchResult(text=best, source=source, warning=warning)
