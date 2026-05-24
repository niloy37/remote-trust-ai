(() => {
  if (window.__REMOTE_TRUST_AI_CONTENT_READY__) return;
  window.__REMOTE_TRUST_AI_CONTENT_READY__ = true;

  const MAX_DESCRIPTION_LENGTH = 30000;

  function sourceFromUrl(url) {
    const hostname = new URL(url).hostname.toLowerCase();
    if (hostname.endsWith("linkedin.com")) return "LinkedIn";
    if (hostname.endsWith("indeed.com")) return "Indeed";
    if (hostname.endsWith("greenhouse.io")) return "Greenhouse";
    if (hostname.endsWith("lever.co")) return "Lever";
    if (hostname.endsWith("ashbyhq.com")) return "Ashby";
    if (hostname.endsWith("workable.com")) return "Workable";
    if (hostname.endsWith("smartrecruiters.com")) return "SmartRecruiters";
    if (hostname.endsWith("flexjobs.com")) return "FlexJobs";
    if (hostname.endsWith("remoteok.com")) return "RemoteOK";
    if (hostname.endsWith("weworkremotely.com")) return "We Work Remotely";
    if (hostname.endsWith("remotive.com")) return "Remotive";
    if (hostname.endsWith("wellfound.com")) return "Wellfound";
    return null;
  }

  function isSearchOrListingPage(url) {
    const parsed = new URL(url);
    const lower = `${parsed.pathname}?${parsed.searchParams.toString()}`.toLowerCase();
    const hostname = parsed.hostname.toLowerCase();
    if (
      lower.includes("/jobs/search") ||
      lower.includes("/collections/") ||
      lower.includes("/recommended/") ||
      lower.includes("/results/") ||
      lower.includes("/search") ||
      lower.includes("search=") ||
      lower.includes("q=") ||
      lower.includes("/remote-jobs/search") ||
      lower.includes("/categories/")
    ) {
      return true;
    }
    if (hostname.endsWith("flexjobs.com") && !/\/(?:remote-jobs|jobs)\/[^/?#]+/i.test(parsed.pathname)) return true;
    if (hostname.endsWith("remoteok.com") && /^\/(?:remote-[^/?#]+-jobs)?\/?$/i.test(parsed.pathname)) return true;
    if (hostname.endsWith("weworkremotely.com") && /^\/(?:categories|remote-jobs)?\/?$/i.test(parsed.pathname)) return true;
    return false;
  }

  function normalizeText(value) {
    return (value || "")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function isLinkedInChromeLine(value) {
    const text = normalizeText(value).toLowerCase();
    if (!text) return true;
    if (
      text.includes("how promoted jobs are ranked") ||
      text.includes("promoted jobs are ranked") ||
      text.includes("job alert") ||
      text.includes("set alert") ||
      text.includes("similar jobs")
    ) {
      return true;
    }
    if (/\b\d+\+?\s+results?\b/i.test(text) && (text.includes("job") || text.includes("remote"))) {
      return true;
    }
    if (/\b(?:on-site|onsite)\s+or\s+hybrid\s+or\s+remote\b/i.test(text) && /results?|ranked/i.test(text)) {
      return true;
    }
    return false;
  }

  function cleanLinkedInText(value) {
    return normalizeText(
      (value || "")
        .split(/\n+/)
        .filter((line) => !isLinkedInChromeLine(line))
        .join("\n")
    );
  }

  function compactLine(value) {
    return normalizeText(value)
      .split(/\n|·|\|/)
      .map((line) => line.trim())
      .filter(Boolean)
      .find((line) => !/^(promoted|actively hiring|reposted|view|follow|apply|save)$/i.test(line)) || null;
  }

  function isVisible(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE) return false;
    const style = window.getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 1 && rect.height > 1;
  }

  function visibleText(node) {
    if (!node || !isVisible(node)) return "";
    return normalizeText(node.innerText || node.textContent || "");
  }

  function getMetaContent(names) {
    for (const name of names) {
      const escaped = CSS.escape(name);
      const node = document.querySelector(`meta[property="${escaped}"], meta[name="${escaped}"]`);
      const value = normalizeText(node?.getAttribute("content") || "");
      if (value) return value;
    }
    return null;
  }

  function traverseJson(value, results = []) {
    if (Array.isArray(value)) {
      value.forEach((item) => traverseJson(item, results));
      return results;
    }
    if (value && typeof value === "object") {
      results.push(value);
      if (Array.isArray(value["@graph"])) traverseJson(value["@graph"], results);
    }
    return results;
  }

  function firstJsonText(value) {
    if (!value) return null;
    if (typeof value === "string") return normalizeText(value.replace(/<[^>]+>/g, " "));
    if (Array.isArray(value)) return value.map(firstJsonText).filter(Boolean).join(", ") || null;
    if (typeof value === "object") {
      for (const key of ["name", "text", "addressLocality", "addressRegion", "addressCountry"]) {
        const text = firstJsonText(value[key]);
        if (text) return text;
      }
    }
    return null;
  }

  function extractGenericJobPage(sourceLabel = "Generic Portal") {
    const jsonLd = extractJsonLdJob();
    const title =
      jsonLd.title ||
      firstText(["h1", "h2", "[data-testid*='title' i]", "[class*='title' i]", "[itemprop='title']"]) ||
      document.title;
    const company =
      jsonLd.company ||
      getMetaContent(["og:site_name", "application-name"]) ||
      firstText(["[data-testid*='company' i]", "[class*='company' i]", "[class*='organization' i]", "[class*='department' i]", "[itemprop='hiringOrganization']"]);
    const location =
      jsonLd.location ||
      firstText(["[data-testid*='location' i]", "[class*='location' i]", "[class*='office' i]"]);
    const bodyText = fallbackMainText();
    const description = normalizeText([jsonLd.description, bodyText].filter(Boolean).join("\n\n"));

    return { source: sourceLabel, title, company, location, description };
  }

  function extractJsonLdJob() {
    const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
    for (const script of scripts) {
      try {
        const parsed = JSON.parse(script.textContent || "{}");
        const job = traverseJson(parsed).find((node) => {
          const type = node["@type"];
          return Array.isArray(type) ? type.includes("JobPosting") : type === "JobPosting";
        });
        if (!job) continue;
        return {
          title: firstJsonText(job.title),
          company: firstJsonText(job.hiringOrganization),
          location: firstJsonText(job.jobLocation || job.applicantLocationRequirements),
          description: firstJsonText(job.description)
        };
      } catch {
        // Ignore malformed JSON-LD blocks; many large sites include unrelated scripts.
      }
    }
    return {};
  }

  function parseLinkedInTitle(rawTitle) {
    const title = normalizeText(rawTitle || "").replace(/\s+\|\s+LinkedIn.*$/i, "").replace(/\s+-\s+LinkedIn.*$/i, "");
    let match = title.match(/^(.+?)\s+hiring\s+(.+?)\s+in\s+(.+)$/i);
    if (match) return { company: match[1].trim(), title: match[2].trim(), location: match[3].trim() };
    match = title.match(/^(.+?)\s+hiring\s+(.+)$/i);
    if (match) return { company: match[1].trim(), title: match[2].trim() };
    match = title.match(/^(.+?)\s+at\s+(.+)$/i);
    if (match) return { title: match[1].trim(), company: match[2].trim() };
    return { title: compactLine(title) };
  }

  function topCardRoot() {
    return document.querySelector(
      ".job-details-jobs-unified-top-card, .jobs-unified-top-card, .top-card-layout, .jobs-details__main-content, .job-view-layout"
    );
  }

  function textFromSelectors(selectors) {
    for (const selector of selectors) {
      const nodes = Array.from(document.querySelectorAll(selector)).filter(isVisible);
      for (const node of nodes) {
        const text = visibleText(node);
        if (text.length > 80) return text;
      }
    }
    return "";
  }

  function firstText(selectors) {
    for (const selector of selectors) {
      const nodes = Array.from(document.querySelectorAll(selector)).filter(isVisible);
      for (const node of nodes) {
        const text = compactLine(node.innerText || node.textContent || "");
        if (text) return text;
      }
    }
    return null;
  }

  function firstTextWithin(root, selectors) {
    if (!root) return null;
    for (const selector of selectors) {
      const nodes = Array.from(root.querySelectorAll(selector)).filter(isVisible);
      for (const node of nodes) {
        const text = compactLine(node.innerText || node.textContent || "");
        if (text) return text;
      }
    }
    return null;
  }

  function textWithin(root, selectors) {
    if (!root) return "";
    for (const selector of selectors) {
      const nodes = Array.from(root.querySelectorAll(selector)).filter(isVisible);
      for (const node of nodes) {
        const text = visibleText(node);
        if (text.length > 80) return text;
      }
    }
    return "";
  }

  function currentLinkedInJobId() {
    const pathMatch = location.pathname.match(/\/jobs\/view\/(\d+)/i);
    if (pathMatch) return pathMatch[1];
    return new URLSearchParams(location.search).get("currentJobId");
  }

  function firstTopCardLinkText(hrefPattern) {
    const root = topCardRoot() || document;
    const links = Array.from(root.querySelectorAll("a[href]"));
    for (const link of links) {
      const href = link.getAttribute("href") || "";
      if (!isVisible(link)) continue;
      const text = compactLine(link.innerText || link.textContent || "");
      if (href.includes(hrefPattern) && text) return text;
    }
    return null;
  }

  function firstTopCardLinkTextWithin(root, hrefPattern) {
    const links = Array.from((root || document).querySelectorAll("a[href]"));
    for (const link of links) {
      const href = link.getAttribute("href") || "";
      if (!isVisible(link)) continue;
      const text = compactLine(link.innerText || link.textContent || "");
      if (href.includes(hrefPattern) && text) return text;
    }
    return null;
  }

  function findLinkedInSelectedCard(jobId) {
    const selectors = [
      jobId ? `[data-job-id="${jobId}"]` : null,
      jobId ? `[data-occludable-job-id="${jobId}"]` : null,
      jobId ? `a[href*="/jobs/view/${jobId}"]` : null,
      ".jobs-search-results__list-item--active",
      ".jobs-search-results-list__list-item--active",
      ".job-card-container--clickable[aria-current='page']",
      "[aria-current='page']"
    ].filter(Boolean);

    for (const selector of selectors) {
      const node = document.querySelector(selector);
      if (!node) continue;
      const card = node.closest("li, article, div[data-job-id], div[data-occludable-job-id]") || node;
      if (isVisible(card)) return card;
    }
    return null;
  }

  function findLinkedInDetailRoot(parsedTitle) {
    const candidates = [
      ".jobs-search__job-details--container",
      ".jobs-details__main-content",
      ".jobs-details",
      ".job-view-layout",
      ".jobs-search__job-details",
      ".two-pane-serp-page__detail-view",
      ".scaffold-layout__detail",
      "main"
    ]
      .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
      .filter(isVisible)
      .map((node) => {
        const text = visibleText(node);
        let score = text.length;
        if (/about the job|show more|apply|easy apply|seniority level|employment type/i.test(text)) score += 2000;
        if (parsedTitle?.title && text.includes(parsedTitle.title)) score += 1500;
        if (parsedTitle?.company && text.includes(parsedTitle.company)) score += 1000;
        if (/similar jobs|recommended jobs/i.test(text)) score -= 1000;
        return { node, score, textLength: text.length };
      })
      .filter((candidate) => candidate.textLength > 180)
      .sort((a, b) => b.score - a.score);

    return candidates[0]?.node || null;
  }

  function fallbackMainText() {
    const clone = document.body.cloneNode(true);
    clone.querySelectorAll("script, style, noscript, svg, nav, header, footer, aside, form, button, [class*='filter' i], [class*='search' i], [class*='newsletter' i], [class*='cookie' i]").forEach((node) => node.remove());
    const containers = [
      clone.querySelector("[data-testid*='job' i]"),
      clone.querySelector("[class*='job-detail' i]"),
      clone.querySelector("[class*='job-post' i]"),
      clone.querySelector("main"),
      clone.querySelector("article"),
      clone.querySelector("[role='main']"),
      clone
    ];
    for (const container of containers) {
      const text = normalizeText(container?.innerText || container?.textContent || "");
      if (text.length > 250) return text;
    }
    return "";
  }

  function extractLinkedIn() {
    const jsonLd = extractJsonLdJob();
    const metaTitle = getMetaContent(["og:title", "twitter:title"]) || document.title;
    const parsedTitle = parseLinkedInTitle(metaTitle);
    const detailRoot = findLinkedInDetailRoot(parsedTitle);
    const selectedCard = findLinkedInSelectedCard(currentLinkedInJobId());

    const titleSelectors = [
      "[data-test-job-title]",
      "[data-job-title]",
      ".jobs-details-top-card__job-title",
      ".job-details-jobs-unified-top-card__job-title",
      ".job-details-jobs-unified-top-card__job-title h1",
      ".jobs-unified-top-card__job-title h1",
      ".top-card-layout__title",
      ".jobs-unified-top-card__job-title",
      ".jobs-details__main-content h1",
      ".job-view-layout h1",
      "h1"
    ];
    const companySelectors = [
      "[data-test-job-company-name]",
      "[data-company-name]",
      ".jobs-details-top-card__company-url",
      ".job-details-jobs-unified-top-card__company-name a",
      ".job-details-jobs-unified-top-card__company-name",
      ".jobs-unified-top-card__company-name a",
      ".jobs-unified-top-card__company-name",
      ".topcard__org-name-link",
      ".top-card-layout__second-subline a"
    ];
    const locationSelectors = [
      "[data-test-job-location]",
      ".job-details-jobs-unified-top-card__bullet",
      ".job-details-jobs-unified-top-card__primary-description-container",
      ".jobs-unified-top-card__bullet",
      ".jobs-unified-top-card__primary-description",
      ".topcard__flavor--bullet",
      ".top-card-layout__second-subline"
    ];
    const descriptionSelectors = [
      ".jobs-description__content .jobs-box__html-content",
      ".jobs-description-content__text",
      ".jobs-description__container",
      ".jobs-box__html-content",
      ".jobs-search__job-details--container",
      ".job-view-layout"
    ];

    const cardTitle = firstTextWithin(selectedCard, [
      ".job-card-list__title",
      ".job-card-container__link",
      ".artdeco-entity-lockup__title",
      "a[href*='/jobs/view/']"
    ]);
    const cardCompany = firstTextWithin(selectedCard, [
      ".job-card-container__primary-description",
      ".artdeco-entity-lockup__subtitle",
      "[class*='company-name']"
    ]);
    const cardLocation = firstTextWithin(selectedCard, [
      ".job-card-container__metadata-item",
      ".artdeco-entity-lockup__caption",
      "[class*='location']"
    ]);

    const isViewPage = /\/jobs\/view\/\d+/i.test(location.pathname);
    const title =
      jsonLd.title ||
      (isViewPage ? parsedTitle.title : null) ||
      firstTextWithin(detailRoot, titleSelectors) ||
      cardTitle ||
      parsedTitle.title ||
      firstText(titleSelectors);
    const company =
      jsonLd.company ||
      (isViewPage ? parsedTitle.company : null) ||
      firstTextWithin(detailRoot, companySelectors) ||
      firstTopCardLinkTextWithin(detailRoot, "/company/") ||
      firstTopCardLinkTextWithin(detailRoot, "/school/") ||
      cardCompany ||
      parsedTitle.company ||
      firstTopCardLinkText("/company/") ||
      firstTopCardLinkText("/school/");
    const linkedInLocation =
      jsonLd.location ||
      (isViewPage ? parsedTitle.location : null) ||
      firstTextWithin(detailRoot, locationSelectors) ||
      cardLocation ||
      parsedTitle.location;
    let description =
      textWithin(detailRoot, descriptionSelectors) ||
      textFromSelectors(descriptionSelectors) ||
      jsonLd.description ||
      "";
    if (!description && (isViewPage || detailRoot)) {
      description = fallbackMainText();
    }
    description = cleanLinkedInText(description);

    return { source: "LinkedIn", title, company, location: linkedInLocation, description };
  }

  function extractIndeed() {
    const title = firstText([
      "[data-testid='jobsearch-JobInfoHeader-title']",
      ".jobsearch-JobInfoHeader-title",
      "h1"
    ]);
    const company = firstText([
      "[data-testid='inlineHeader-companyName']",
      "[data-testid='company-name']",
      ".jobsearch-CompanyInfoContainer a",
      ".jobsearch-InlineCompanyRating"
    ]);
    const location = firstText([
      "[data-testid='job-location']",
      ".jobsearch-JobInfoHeader-subtitle div",
      "[data-testid='inlineHeader-companyLocation']"
    ]);
    const description = textFromSelectors([
      "#jobDescriptionText",
      "[data-testid='jobDescriptionText']",
      ".jobsearch-jobDescriptionText",
      ".jobsearch-JobComponent-description"
    ]) || fallbackMainText();

    return { source: "Indeed", title, company, location, description };
  }

  function buildJobText(extracted) {
    const parts = [
      extracted.title ? `Job Title: ${extracted.title}` : null,
      extracted.company ? `Company: ${extracted.company}` : null,
      extracted.location ? `Location: ${extracted.location}` : null,
      `Source: ${extracted.source}`,
      document.title ? `Browser Title: ${document.title}` : null,
      "",
      extracted.description
    ];
    return normalizeText(parts.filter(Boolean).join("\n"));
  }

  function extractJobPage() {
    const source = sourceFromUrl(location.href);
    if (!source) {
      return {
        ok: false,
        error: "Open an individual posting on a supported job site before running RemoteTrust AI."
      };
    }
    if (isSearchOrListingPage(location.href)) {
      return {
        ok: false,
        error: "This looks like a search or listing page. Open one individual job posting, then run RemoteTrust AI again."
      };
    }

    const extracted =
      source === "LinkedIn" ? extractLinkedIn() :
      source === "Indeed" ? extractIndeed() :
      extractGenericJobPage(source);
    const jobText = buildJobText(extracted).slice(0, MAX_DESCRIPTION_LENGTH);
    if (!extracted.description || extracted.description.length < 120) {
      const hint = extracted.source === "LinkedIn"
        ? " On LinkedIn search/browse pages, click one job so the right-side job detail panel opens, then run the extension again."
        : extracted.source === "Indeed"
          ? ""
          : " Open the individual job posting rather than a search or listing page, then run the extension again.";
      return {
        ok: false,
        error: `Could not find enough readable job description text on this ${extracted.source} page.${hint}`
      };
    }

    return {
      ok: true,
      source: extracted.source,
      page_url: location.href,
      job_title: extracted.title,
      company: extracted.company,
      location: extracted.location,
      job_description: jobText
    };
  }

  window.__REMOTE_TRUST_AI_TEST_HOOKS__ = {
    sourceFromUrl,
    isSearchOrListingPage
  };

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "REMOTE_TRUST_EXTRACT_JOB") return false;
    sendResponse(extractJobPage());
    return true;
  });
})();
