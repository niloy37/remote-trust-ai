const API_BASE_URL = "https://remote-trust-ai.onrender.com";
const SUPPORTED_HOSTS = [
  "linkedin.com",
  "indeed.com",
  "greenhouse.io",
  "lever.co",
  "ashbyhq.com",
  "workable.com",
  "smartrecruiters.com",
  "flexjobs.com",
  "remoteok.com",
  "weworkremotely.com",
  "remotive.com",
  "wellfound.com"
];

const els = {
  unsupported: document.getElementById("unsupported"),
  country: document.getElementById("country"),
  desiredRole: document.getElementById("desiredRole"),
  consent: document.getElementById("consent"),
  analyze: document.getElementById("analyze"),
  status: document.getElementById("status"),
  result: document.getElementById("result"),
  finalScore: document.getElementById("finalScore"),
  verdict: document.getElementById("verdict"),
  classification: document.getElementById("classification"),
  classificationConfidence: document.getElementById("classificationConfidence"),
  classificationStatus: document.getElementById("classificationStatus"),
  remoteRestrictions: document.getElementById("remoteRestrictions"),
  classificationEvidence: document.getElementById("classificationEvidence"),
  jobTitle: document.getElementById("jobTitle"),
  company: document.getElementById("company"),
  titleValidation: document.getElementById("titleValidation"),
  companyVerification: document.getElementById("companyVerification"),
  legitimacy: document.getElementById("legitimacy"),
  remote: document.getElementById("remote"),
  eligibility: document.getElementById("eligibility"),
  quality: document.getElementById("quality"),
  explanation: document.getElementById("explanation"),
  redFlags: document.getElementById("redFlags"),
  positiveSignals: document.getElementById("positiveSignals"),
  webSources: document.getElementById("webSources")
};

let activeTab = null;
let activeSupported = false;

function isSupportedUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && SUPPORTED_HOSTS.some((host) => parsed.hostname === host || parsed.hostname.endsWith(`.${host}`));
  } catch {
    return false;
  }
}



function setStatus(message, type = "") {
  els.status.textContent = message;
  els.status.className = `status ${type}`.trim();
  els.status.classList.toggle("hidden", !message);
}

function setLoading(isLoading) {
  els.analyze.disabled = isLoading || !els.consent.checked || !activeSupported;
  els.analyze.textContent = isLoading ? "Reading page..." : "Read page & analyze";
}

function renderList(node, items, emptyText) {
  node.innerHTML = "";
  const values = items?.length ? items : [emptyText];
  values.slice(0, 5).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    node.appendChild(li);
  });
}

function renderWebSources(node, sources) {
  node.innerHTML = "";
  const values = sources?.length ? sources.slice(0, 3) : [];
  if (!values.length) {
    const li = document.createElement("li");
    li.textContent = "No web evidence links were returned.";
    node.appendChild(li);
    return;
  }
  values.forEach((source) => {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = source.title;
    li.appendChild(link);
    node.appendChild(li);
  });
}

function scoreColor(score) {
  if (score >= 80) return "#3dd6a3";
  if (score >= 60) return "#fbbf24";
  return "#fb7185";
}

function readableLabel(value) {
  return (value || "UNKNOWN")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function cleanRestrictionText(value) {
  const text = (value || "").replace(/\s+/g, " ").trim();
  if (!text) return null;
  const lower = text.toLowerCase();
  if (
    lower.includes("how promoted jobs are ranked") ||
    lower.includes("promoted jobs are ranked") ||
    /\b\d+\+?\s+results?\b/i.test(text)
  ) {
    return null;
  }
  return text;
}

function classificationClass(label) {
  if (label === "LEGIT_REMOTE") return "classification legit";
  if (label === "LIKELY_SCAM") return "classification scam";
  if (label === "COUNTRY_RESTRICTED_REMOTE" || label === "HYBRID_OR_LOCATION_BOUND") return "classification restricted";
  return "classification unverified";
}

function remoteRestrictionItems(classification) {
  const restrictions = classification?.evidence?.remote_restrictions;
  if (!restrictions) return ["No advanced remote restriction evidence was returned."];

  const items = [];
  const seen = new Set();
  const addText = (label, value) => {
    const text = cleanRestrictionText(value);
    if (!text) return;
    const key = text.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    items.push(`${label}: ${text}`);
  };

  if (restrictions.allowed_countries?.length) items.push(`Allowed: ${restrictions.allowed_countries.join(", ")}`);
  if (restrictions.excluded_countries?.length) items.push(`Excluded: ${restrictions.excluded_countries.join(", ")}`);
  addText("Timezone", restrictions.timezone_requirements);
  addText("Authorization", restrictions.work_authorization);
  addText("Hybrid/onsite", restrictions.onsite_or_hybrid_requirement);
  (restrictions.ambiguous_location_language || []).forEach((value) => addText("Ambiguous", value));
  (restrictions.source_snippets || []).forEach((value) => addText("Evidence", value));
  return items.length ? items : ["No explicit remote restriction detected."];
}

function classificationEvidenceItems(classification) {
  if (!classification?.evidence) return ["Advanced classification evidence was not returned by the backend."];
  return [
    ...(classification.evidence.confidence_factors || []),
    ...(classification.evidence.top_red_flags || []).slice(0, 2),
    ...(classification.evidence.positive_signals || []).slice(0, 2)
  ].filter(Boolean);
}

function renderResult(result) {
  els.result.classList.remove("hidden");
  els.finalScore.textContent = result.final_score;
  els.verdict.textContent = result.verdict;
  els.verdict.className = "badge";
  if (result.verdict === "Caution") els.verdict.classList.add("caution");
  if (result.verdict === "Risky") els.verdict.classList.add("risky");
  els.jobTitle.textContent = result.extracted.job_title || "Untitled role";
  els.company.textContent = result.extracted.company || "Company not detected";
  const classification = result.classification;
  if (classification) {
    els.classification.textContent = `${readableLabel(classification.label)} (${Math.round(classification.confidence * 100)}%)`;
    els.classification.className = classificationClass(classification.label);
    els.classificationConfidence.textContent = `${Math.round(classification.confidence * 100)}%`;
    els.classificationStatus.textContent = classification.status || "fallback";
    renderList(els.remoteRestrictions, remoteRestrictionItems(classification), "No explicit remote restriction detected.");
    renderList(els.classificationEvidence, classificationEvidenceItems(classification), "No ML evidence returned.");
  } else {
    els.classification.textContent = "Advanced classification unavailable";
    els.classification.className = "classification unverified";
    els.classificationConfidence.textContent = "0%";
    els.classificationStatus.textContent = "Unavailable";
    renderList(els.remoteRestrictions, [], "No advanced remote restriction evidence was returned.");
    renderList(els.classificationEvidence, [], "No ML evidence returned.");
  }
  const titleValidation = result.title_validation;
  if (titleValidation) {
    els.titleValidation.textContent = `Title: ${titleValidation.verdict} (${titleValidation.score}/100)`;
    els.titleValidation.className = "title-validation";
    if (titleValidation.verdict === "Unusual") els.titleValidation.classList.add("unusual");
    if (titleValidation.verdict === "Suspicious") els.titleValidation.classList.add("suspicious");
  } else {
    els.titleValidation.textContent = "Title check unavailable";
    els.titleValidation.className = "title-validation unusual";
  }
  const companyVerification = result.company_verification;
  if (companyVerification) {
    els.companyVerification.textContent = `Web: ${companyVerification.status} (${companyVerification.score}/100)`;
    els.companyVerification.className = "company-verification";
    if (companyVerification.status === "Limited evidence") els.companyVerification.classList.add("limited");
    if (companyVerification.status === "Risk signals") els.companyVerification.classList.add("risk");
    renderWebSources(els.webSources, companyVerification.sources);
  } else {
    els.companyVerification.textContent = "Web check unavailable";
    els.companyVerification.className = "company-verification limited";
    renderWebSources(els.webSources, []);
  }
  els.legitimacy.textContent = result.scores.legitimacy;
  els.remote.textContent = result.scores.remote_authenticity;
  els.eligibility.textContent = result.scores.global_eligibility;
  els.quality.textContent = result.scores.job_quality;
  els.explanation.textContent = result.explanation;
  renderList(els.redFlags, result.red_flags, "No major red flags detected.");
  renderList(els.positiveSignals, result.positive_signals, "Limited positive signals detected.");

  const degrees = result.final_score * 3.6;
  document.querySelector(".score-ring").style.background = `conic-gradient(${scoreColor(result.final_score)} ${degrees}deg, rgba(148, 163, 184, 0.18) 0deg)`;
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0] || null;
}

async function extractFromTab(tab) {
  try {
    return await chrome.tabs.sendMessage(tab.id, { type: "REMOTE_TRUST_EXTRACT_JOB" });
  } catch {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content-script.js"] });
    return chrome.tabs.sendMessage(tab.id, { type: "REMOTE_TRUST_EXTRACT_JOB" });
  }
}

function isSearchPage(url) {

  const lower = url.toLowerCase();

  return (
    lower.includes("/jobs/search") ||
    lower.includes("/collections/") ||
    lower.includes("/recommended/") ||
    lower.includes("/results/") ||
    lower.includes("/search") ||
    lower.includes("?search=") ||
    lower.includes("?q=") ||
    lower.includes("&q=") ||
    lower.includes("/remote-jobs/search") ||
    lower.includes("/categories/")
  );
}

async function analyzeCurrentPage() {

  if (!activeTab || !activeSupported) return;

  if (isSearchPage(activeTab.url)) {

    setStatus(
      "Please open an individual job posting for best analysis quality.",
      "error"
    );

    return;
  }

  if (!els.consent.checked) {

    setStatus(
      "Please confirm consent before reading the page.",
      "error"
    );

    return;
  }

  setLoading(true);

  setStatus("Reading visible job content from this page...");

  els.result.classList.add("hidden");

  try {

    const extracted = await extractFromTab(activeTab);

    if (!extracted?.ok) {
      throw new Error(
        extracted?.error || "Could not extract job description."
      );
    }

    setStatus("Analyzing with local RemoteTrust AI backend...");

    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_url: extracted.page_url,
        job_description: extracted.job_description,
        applicant_country: els.country.value,
        desired_role: els.desiredRole.value.trim() || null
      })
    });

    if (!response.ok) {

      const body = await response.json().catch(() => ({}));

      throw new Error(
        body.detail || `Backend returned ${response.status}`
      );
    }

    const result = await response.json();

    result.extracted.job_title ||= extracted.job_title || null;
    result.extracted.company ||= extracted.company || null;
    result.extracted.location ||= extracted.location || null;

    renderResult(result);

    setStatus(
      `Analyzed ${extracted.source} job page successfully.`,
      "success"
    );

  } catch (error) {

    setStatus(
      error instanceof Error
        ? error.message
        : "Could not analyze this page.",
      "error"
    );

  } finally {

    setLoading(false);
  }
}

async function init() {

  activeTab = await getActiveTab();

  const stored = await chrome.storage.local.get([
    "remoteTrustConsent",
    "remoteTrustApplicantCountry",
    "remoteTrustDesiredRole"
  ]);

  els.consent.checked = stored.remoteTrustConsent || false;
  if (stored.remoteTrustApplicantCountry) els.country.value = stored.remoteTrustApplicantCountry;
  if (stored.remoteTrustDesiredRole) els.desiredRole.value = stored.remoteTrustDesiredRole;

  activeSupported = Boolean(
    activeTab?.url &&
    isSupportedUrl(activeTab.url)
  );

  els.unsupported.classList.toggle(
    "hidden",
    activeSupported
  );

  setLoading(false);

  if (!activeSupported) {

    setStatus(
      "Open a job posting page to analyze it.",
      "error"
    );

    return;
  }

  setStatus(
    "Ready to analyze this job page."
  );
}

els.country.addEventListener("change", async () => {
  await chrome.storage.local.set({
    remoteTrustApplicantCountry: els.country.value
  });
});

els.desiredRole.addEventListener("input", async () => {
  await chrome.storage.local.set({
    remoteTrustDesiredRole: els.desiredRole.value
  });
});

els.consent.addEventListener("change", async () => {

  await chrome.storage.local.set({
    remoteTrustConsent: els.consent.checked
  });

  setLoading(false);
});

els.analyze.addEventListener(
  "click",
  analyzeCurrentPage
);

init();
