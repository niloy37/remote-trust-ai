from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

from app.core.config import settings
from app.db.database import get_connection, utc_now
from app.models import AnalyzeRequest, CompanyVerification, GraphEdge, GraphNode, GraphVerification


try:  # The app must still run when the optional Neo4j driver is not installed.
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover - exercised only when the dependency is absent.
    GraphDatabase = None  # type: ignore[assignment]


FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "icloud.com",
}

RISKY_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.me",
    "telegram.me",
    "wa.me",
    "forms.gle",
    "docs.google.com",
}

JOB_BOARD_DOMAINS = {
    "linkedin.com",
    "indeed.com",
    "wellfound.com",
    "remoteok.com",
    "weworkremotely.com",
    "flexjobs.com",
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

PAYMENT_OR_CHAT_RISKS = {
    "pay for training",
    "send money",
    "gift card",
    "gift cards",
    "crypto",
    "wire transfer",
    "equipment fee",
    "processing fee",
    "telegram",
    "whatsapp only",
}


@dataclass
class GraphContext:
    observations_by_node: dict[str, int] = field(default_factory=dict)
    risk_jobs_by_node: dict[str, int] = field(default_factory=dict)
    warning: str | None = None


class GraphBackend(Protocol):
    name: str

    def fetch_context(self, node_ids: list[str], job_id: str) -> GraphContext:
        ...

    def persist(self, job_id: str, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        ...


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def add_unique(items: list[str], item: str) -> None:
    if item and item not in items:
        items.append(item)


def slug(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def normalize_company_key(company: str | None) -> str | None:
    if not company:
        return None
    value = company.lower()
    value = re.sub(r"\b(?:inc|llc|ltd|limited|corp|corporation|company|co|gmbh|plc|sa|bv)\b\.?", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def domain_for(url: str | None) -> str | None:
    if not url:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate if re.match(r"^[a-z]+://", candidate, flags=re.IGNORECASE) else f"https://{candidate}")
    domain = parsed.netloc or parsed.path.split("/")[0]
    domain = domain.lower().split("@")[-1].split(":")[0].removeprefix("www.")
    return domain or None


def registrable_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    labels = [label for label in domain.lower().split(".") if label]
    if len(labels) <= 2:
        return ".".join(labels)
    two_part_suffixes = {"co.uk", "com.au", "com.br", "co.in", "com.sg", "co.nz"}
    suffix = ".".join(labels[-2:])
    if suffix in two_part_suffixes and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def node_id(kind: str, key: str) -> str:
    return f"{kind.lower()}:{key}"


def edge_key(job_id: str, edge: GraphEdge) -> str:
    return stable_hash(f"{job_id}:{edge.source}:{edge.type}:{edge.target}:{edge.evidence or ''}")


def is_related_domain(company: str | None, domain: str | None) -> bool:
    company_key = normalize_company_key(company)
    if not company_key or not domain:
        return False
    compact_company = slug(company_key)
    compact_domain = slug(registrable_domain(domain) or domain)
    return len(compact_company) >= 3 and compact_company in compact_domain


def is_known_domain(domain: str | None, known: set[str]) -> bool:
    return bool(domain and any(domain == item or domain.endswith(f".{item}") for item in known))


def ats_platform(domain: str | None) -> str | None:
    if not domain:
        return None
    for ats_domain, platform in ATS_DOMAINS.items():
        if domain == ats_domain or domain.endswith(f".{ats_domain}"):
            return platform
    return None


def contact_key(contact: str) -> str:
    return re.sub(r"\s+", " ", contact.lower()).strip()


def extract_emails(text: str) -> list[str]:
    return sorted(set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text or "")))


def source_node_kind(source_type: str) -> str:
    if source_type == "employee_or_company_review":
        return "ReviewSource"
    if source_type == "risk_report":
        return "RiskSignal"
    return "SourcePage"


class SqliteGraphBackend:
    name = "sqlite"

    def _ensure_tables(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                normalized_key TEXT NOT NULL,
                observations INTEGER NOT NULL DEFAULT 0,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_edges (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT NOT NULL,
                evidence TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_nodes_kind_key ON graph_nodes(kind, normalized_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_job ON graph_edges(job_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_source_type ON graph_edges(source_id, type)")
        connection.commit()

    def fetch_context(self, node_ids: list[str], job_id: str) -> GraphContext:
        if not node_ids:
            return GraphContext()
        with get_connection() as connection:
            self._ensure_tables(connection)
            placeholders = ",".join("?" for _ in node_ids)
            node_rows = connection.execute(
                f"SELECT id, observations FROM graph_nodes WHERE id IN ({placeholders})",
                node_ids,
            ).fetchall()
            risk_rows = connection.execute(
                f"""
                SELECT source_id, COUNT(DISTINCT job_id) AS risk_jobs
                FROM graph_edges
                WHERE source_id IN ({placeholders})
                  AND type = 'HAS_RISK_SIGNAL'
                  AND job_id != ?
                GROUP BY source_id
                """,
                [*node_ids, job_id],
            ).fetchall()
        return GraphContext(
            observations_by_node={row["id"]: int(row["observations"]) for row in node_rows},
            risk_jobs_by_node={row["source_id"]: int(row["risk_jobs"]) for row in risk_rows},
        )

    def persist(self, job_id: str, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        now = utc_now()
        with get_connection() as connection:
            self._ensure_tables(connection)
            for node in nodes:
                connection.execute(
                    """
                    INSERT INTO graph_nodes (id, kind, name, normalized_key, observations, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        kind = excluded.kind,
                        name = excluded.name,
                        observations = graph_nodes.observations + 1,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (node.id, node.kind, node.name, slug(node.name), now, now),
                )
            for edge in edges:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO graph_edges (id, job_id, source_id, target_id, type, evidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (edge_key(job_id, edge), job_id, edge.source, edge.target, edge.type, edge.evidence, now),
                )
            connection.commit()


class Neo4jGraphBackend:
    name = "neo4j"

    def __init__(self) -> None:
        if GraphDatabase is None:
            raise RuntimeError("Neo4j driver is not installed")
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            connection_timeout=2,
        )
        self.driver.verify_connectivity()
        self._ensure_schema()

    def close(self) -> None:
        self.driver.close()

    def _ensure_schema(self) -> None:
        now = utc_now()
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE")
            session.run(
                """
                MERGE (schema:Entity {id: '__remote_trust_schema__'})
                SET schema.kind = 'Schema',
                    schema.name = 'RemoteTrust graph schema marker',
                    schema.normalized_key = 'remotetrustgraphschemamarker',
                    schema.observations = coalesce(schema.observations, 0),
                    schema.last_seen_at = $now
                MERGE (risk:Entity {id: '__remote_trust_risk_schema__'})
                SET risk.kind = 'RiskSignal',
                    risk.name = 'RemoteTrust risk schema marker',
                    risk.normalized_key = 'remotetrustriskschemamarker',
                    risk.observations = coalesce(risk.observations, 0),
                    risk.last_seen_at = $now
                MERGE (schema)-[edge:RELATED {id: '__remote_trust_schema_edge__'}]->(risk)
                SET edge.job_id = '__schema__',
                    edge.relation_type = 'HAS_RISK_SIGNAL',
                    edge.evidence = 'Schema marker',
                    edge.created_at = $now
                """,
                now=now,
            )

    def fetch_context(self, node_ids: list[str], job_id: str) -> GraphContext:
        if not node_ids:
            return GraphContext()
        query = """
        UNWIND $ids AS id
        OPTIONAL MATCH (n:Entity {id: id})
        OPTIONAL MATCH (n)-[r:RELATED {relation_type: 'HAS_RISK_SIGNAL'}]->()
        WHERE r.job_id <> $job_id
        RETURN id AS id,
               coalesce(n.observations, 0) AS observations,
               count(DISTINCT r.job_id) AS risk_jobs
        """
        with self.driver.session() as session:
            rows = list(session.run(query, ids=node_ids, job_id=job_id))
        return GraphContext(
            observations_by_node={row["id"]: int(row["observations"] or 0) for row in rows},
            risk_jobs_by_node={row["id"]: int(row["risk_jobs"] or 0) for row in rows if int(row["risk_jobs"] or 0) > 0},
        )

    def persist(self, job_id: str, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        now = utc_now()
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $nodes AS node
                MERGE (n:Entity {id: node.id})
                ON CREATE SET n.first_seen_at = $now, n.observations = 0
                SET n.kind = node.kind,
                    n.name = node.name,
                    n.normalized_key = node.normalized_key,
                    n.observations = coalesce(n.observations, 0) + 1,
                    n.last_seen_at = $now
                """,
                nodes=[{"id": node.id, "kind": node.kind, "name": node.name, "normalized_key": slug(node.name)} for node in nodes],
                now=now,
            )
            session.run(
                """
                UNWIND $edges AS edge
                MATCH (source:Entity {id: edge.source})
                MATCH (target:Entity {id: edge.target})
                MERGE (source)-[r:RELATED {id: edge.id}]->(target)
                SET r.job_id = $job_id,
                    r.relation_type = edge.type,
                    r.evidence = edge.evidence,
                    r.created_at = $now
                """,
                edges=[
                    {
                        "id": edge_key(job_id, edge),
                        "source": edge.source,
                        "target": edge.target,
                        "type": edge.type,
                        "evidence": edge.evidence,
                    }
                    for edge in edges
                ],
                job_id=job_id,
                now=now,
            )


def preferred_backend() -> GraphBackend:
    if settings.graph_backend == "sqlite":
        return SqliteGraphBackend()
    try:
        return Neo4jGraphBackend()
    except Exception as exc:
        backend = SqliteGraphBackend()
        backend.warning = f"Neo4j graph backend unavailable; using SQLite relationship memory ({exc})"  # type: ignore[attr-defined]
        return backend


def build_nodes_and_edges(
    job_id: str,
    request: AnalyzeRequest,
    extracted: Any,
    company_verification: CompanyVerification,
    red_flags: list[str],
    job_description: str,
) -> tuple[list[GraphNode], list[GraphEdge], dict[str, Any]]:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def add_node(kind: str, key: str, name: str) -> str:
        identifier = node_id(kind, key)
        nodes[identifier] = GraphNode(id=identifier, kind=kind, name=name)
        return identifier

    def add_edge(source: str | None, target: str | None, edge_type: str, evidence: str | None = None) -> None:
        if source and target:
            edge = GraphEdge(source=source, target=target, type=edge_type, evidence=evidence)
            if edge not in edges:
                edges.append(edge)

    company = getattr(extracted, "company", None)
    title = getattr(extracted, "job_title", None)
    apply_url = getattr(extracted, "apply_url", None)
    contacts = sorted(set(getattr(extracted, "contact_methods", []) or []) | set(extract_emails(job_description)))
    suspicious_contacts = set(getattr(extracted, "suspicious_contact_methods", []) or [])
    scam_phrases = set(getattr(extracted, "scam_phrases", []) or [])

    job_node = add_node("Job", job_id, title or "Analyzed job")
    company_node = None
    company_key = normalize_company_key(company)
    if company and company_key:
        company_node = add_node("Company", company_key, company)
        add_edge(company_node, job_node, "POSTED_JOB", "Extracted company name from the job posting")

    domains: dict[str, str] = {}
    apply_domain = registrable_domain(domain_for(apply_url))
    job_source_domain = registrable_domain(domain_for(request.job_url))
    for label, url, edge_type in [
        ("apply link", apply_url, "APPLY_URL_ON_DOMAIN"),
        ("source page", request.job_url, "SOURCED_FROM_DOMAIN"),
    ]:
        domain = registrable_domain(domain_for(url))
        if domain:
            domain_node = add_node("Domain", domain, domain)
            domains[label] = domain_node
            add_edge(job_node, domain_node, edge_type, f"Domain observed on {label}")
            if company_node and is_related_domain(company, domain):
                add_edge(company_node, domain_node, "USES_DOMAIN", "Domain text matches the company identity")

            platform = ats_platform(domain)
            if platform:
                ats_node = add_node("ATSPlatform", slug(platform), platform)
                add_edge(job_node, ats_node, "USES_ATS", f"Apply link uses {platform}")
                add_edge(ats_node, domain_node, "USES_DOMAIN", f"{platform} domain")

    for source in company_verification.sources:
        source_key = stable_hash(source.url)
        source_node = add_node(source_node_kind(source.source_type), source_key, source.title[:120] or source.url)
        source_domain = registrable_domain(domain_for(source.url))
        add_edge(company_node, source_node, "MENTIONED_IN_SOURCE", source.source_type)
        if source.source_type == "employee_or_company_review":
            add_edge(company_node, source_node, "HAS_REVIEW_SOURCE", "Employee or company review source")
        if source.source_type == "risk_report":
            add_edge(company_node or job_node, source_node, "HAS_RISK_SIGNAL", "Risk language appeared in live web evidence")
        if source_domain:
            source_domain_node = add_node("Domain", source_domain, source_domain)
            add_edge(source_node, source_domain_node, "ON_DOMAIN", "Source result domain")
            if company_node and is_related_domain(company, source_domain):
                add_edge(company_node, source_domain_node, "USES_DOMAIN", "Search result domain matches company identity")

    for contact in contacts:
        key = contact_key(contact)
        contact_node = add_node("RecruiterContact", key, contact)
        add_edge(job_node, contact_node, "CONTACTED_BY", "Contact method found in the posting")
        if "@" in contact:
            email_domain = contact.split("@")[-1].lower()
            contact_domain_node = add_node("Domain", email_domain, email_domain)
            add_edge(contact_node, contact_domain_node, "USES_DOMAIN", "Recruiter email domain")
            if email_domain in FREE_EMAIL_DOMAINS:
                risk_node = add_node("RiskSignal", "free-email-recruiter", "Free-email recruiter contact")
                add_edge(contact_node, risk_node, "HAS_RISK_SIGNAL", "Recruiter email uses a consumer email provider")
        if contact in suspicious_contacts or key in {item.lower() for item in suspicious_contacts}:
            risk_node = add_node("RiskSignal", f"suspicious-contact-{slug(contact)}", f"Suspicious contact: {contact}")
            add_edge(contact_node, risk_node, "HAS_RISK_SIGNAL", "Contact method is common in job scams")

    for phrase in sorted(scam_phrases | {flag for flag in red_flags if any(term in flag.lower() for term in PAYMENT_OR_CHAT_RISKS)}):
        risk_key = stable_hash(phrase.lower())
        risk_node = add_node("RiskSignal", risk_key, phrase[:120])
        add_edge(job_node, risk_node, "HAS_RISK_SIGNAL", "Risk phrase or warning detected in the analysis")

    for label, domain_node in domains.items():
        domain = domain_node.split(":", 1)[1]
        if is_known_domain(domain, RISKY_DOMAINS):
            risk_node = add_node("RiskSignal", f"risky-domain-{domain}", f"Risky {label} domain")
            add_edge(domain_node, risk_node, "HAS_RISK_SIGNAL", f"{label.title()} uses a high-risk domain")

    metadata = {
        "company": company,
        "company_node": company_node,
        "apply_domain": apply_domain,
        "job_source_domain": job_source_domain,
        "apply_is_ats": bool(ats_platform(apply_domain)),
        "apply_is_job_board": is_known_domain(apply_domain, JOB_BOARD_DOMAINS),
        "apply_is_risky": is_known_domain(apply_domain, RISKY_DOMAINS),
        "apply_related_to_company": is_related_domain(company, apply_domain),
        "contact_nodes": [node_id("RecruiterContact", contact_key(contact)) for contact in contacts],
        "domain_nodes": [node.id for node in nodes.values() if node.kind == "Domain"],
        "source_types": {source.source_type for source in company_verification.sources},
        "scam_phrases": scam_phrases,
    }
    return list(nodes.values()), edges, metadata


def score_graph(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    metadata: dict[str, Any],
    context: GraphContext,
    backend_name: str,
) -> GraphVerification:
    score = 50
    entity_confidence = 35
    signals: list[str] = []
    warnings: list[str] = []
    evidence_paths: list[str] = []
    source_types = metadata["source_types"]

    if metadata["company_node"]:
        entity_confidence += 15
    else:
        add_unique(warnings, "Company identity was not detected, so relationship evidence is limited")

    if metadata["apply_related_to_company"]:
        score += 14
        entity_confidence += 18
        add_unique(signals, "Company, domain, and apply link are connected through consistent public evidence")
        add_unique(evidence_paths, "Company -> apply domain -> job posting")

    if metadata["apply_is_ats"]:
        score += 10
        entity_confidence += 8
        add_unique(signals, "Apply link uses a recognized hiring platform connected to the posting")
        add_unique(evidence_paths, "Job posting -> recognized ATS platform")

    if "official_company_site" in source_types or "career_page" in source_types:
        score += 12
        entity_confidence += 10
        add_unique(signals, "Official company or careers evidence supports the posting")
        add_unique(evidence_paths, "Company -> official/careers source")

    if "company_profile" in source_types:
        score += 7
        entity_confidence += 6
        add_unique(signals, "A recognizable public company profile supports the company identity")

    if "employee_or_company_review" in source_types:
        score += 7
        add_unique(signals, "Employee or company review evidence is connected to the company identity")
        add_unique(evidence_paths, "Company -> employee/company review source")

    if metadata["company_node"] and context.observations_by_node.get(metadata["company_node"], 0) > 0:
        score += 5
        entity_confidence += 5
        add_unique(signals, "This company identity is consistent with a previous local analysis")

    repeated_domain_count = sum(1 for node in metadata["domain_nodes"] if context.observations_by_node.get(node, 0) > 0)
    if repeated_domain_count:
        score += min(5, repeated_domain_count * 2)
        add_unique(signals, "Domain evidence is consistent with previously analyzed postings")

    if metadata["apply_is_risky"]:
        score -= 22
        add_unique(warnings, "Apply link uses a high-risk shortener, chat, or form domain")

    if metadata["apply_domain"] and not (
        metadata["apply_related_to_company"]
        or metadata["apply_is_ats"]
        or metadata["apply_is_job_board"]
    ):
        score -= 10
        add_unique(warnings, "Apply link does not clearly connect back to the company identity")

    if "risk_report" in source_types:
        score -= 22
        add_unique(warnings, "Public web evidence includes scam, fraud, complaint, or warning language")

    repeated_risk_nodes = [
        node
        for node in [*metadata["contact_nodes"], *metadata["domain_nodes"]]
        if context.risk_jobs_by_node.get(node, 0) > 0
    ]
    if repeated_risk_nodes:
        score -= 18
        add_unique(warnings, "This recruiter or domain pattern appears connected to prior suspicious signals")
        add_unique(evidence_paths, "Prior suspicious signal -> reused contact/domain -> current job")

    if metadata["scam_phrases"] & PAYMENT_OR_CHAT_RISKS:
        score -= 15
        add_unique(warnings, "Payment or chat-only scam language is connected to this posting")

    if context.warning:
        add_unique(warnings, context.warning)

    score = clamp(score)
    entity_confidence = clamp(entity_confidence)
    has_risk = any(
        term in warning.lower()
        for warning in warnings
        for term in ["risk", "scam", "fraud", "suspicious", "shortener", "payment", "chat", "does not clearly connect"]
    )
    if has_risk and score < 58:
        status = "Risk signals"
    elif score >= 75 and entity_confidence >= 60:
        status = "Strong graph evidence"
    elif score >= 60:
        status = "Some graph evidence"
    else:
        status = "Limited graph evidence"

    if not signals and status == "Limited graph evidence":
        add_unique(warnings, "Not enough relationship evidence was found to strengthen the company identity")

    if backend_name == "sqlite":
        add_unique(evidence_paths, "Local relationship memory was used for repeat-pattern checks")
    else:
        add_unique(evidence_paths, "Graph database relationship paths were used for repeat-pattern checks")

    return GraphVerification(
        status=status,
        score=score,
        entity_confidence=entity_confidence,
        signals=signals[:6],
        warnings=warnings[:6],
        evidence_paths=evidence_paths[:6],
        nodes=nodes,
        edges=edges,
    )


def verify_relationship_graph(
    job_id: str,
    request: AnalyzeRequest,
    extracted: Any,
    company_verification: CompanyVerification,
    red_flags: list[str],
    job_description: str,
) -> GraphVerification:
    nodes, edges, metadata = build_nodes_and_edges(job_id, request, extracted, company_verification, red_flags, job_description)
    backend = preferred_backend()
    warning = getattr(backend, "warning", None)

    try:
        context = backend.fetch_context([node.id for node in nodes], job_id)
        context.warning = warning
        verification = score_graph(nodes, edges, metadata, context, backend.name)
        backend.persist(job_id, nodes, edges)
        if isinstance(backend, Neo4jGraphBackend):
            backend.close()
        return verification
    except Exception as exc:
        if isinstance(backend, Neo4jGraphBackend):
            backend.close()
        fallback = SqliteGraphBackend()
        context = fallback.fetch_context([node.id for node in nodes], job_id)
        context.warning = f"Graph database unavailable; SQLite relationship memory was used ({exc})"
        verification = score_graph(nodes, edges, metadata, context, fallback.name)
        fallback.persist(job_id, nodes, edges)
        return verification
