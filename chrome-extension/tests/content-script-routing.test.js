const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const scriptPath = path.join(__dirname, "..", "content-script.js");
const script = fs.readFileSync(scriptPath, "utf8");

const sandbox = {
  URL,
  window: {},
  location: { href: "https://boards.greenhouse.io/envisio/jobs/123" },
  document: {},
  chrome: {
    runtime: {
      onMessage: {
        addListener() {}
      }
    }
  }
};

vm.createContext(sandbox);
vm.runInContext(script, sandbox, { filename: scriptPath });

const hooks = sandbox.window.__REMOTE_TRUST_AI_TEST_HOOKS__;
assert.ok(hooks, "content script should expose routing hooks for simulation tests");
const linkedInSearchResultsUrl = "https://www.linkedin.com/jobs/search-results/?currentJobId=4387144232&keywords=Artificial%20Intelligence%20Engineer%20or%20Intern%20or%20AI%20Intern%20or%20Machine%20Learning%20Intern%2C%20on-site%20or%20hybrid%20or%20remote&origin=PREFERENCES_LANDING&originToLandingJobPostings=4387144232%2C4402628957%2C4397660309&geoId=105149290";

assert.strictEqual(hooks.sourceFromUrl("https://boards.greenhouse.io/envisio/jobs/123"), "Greenhouse");
assert.strictEqual(hooks.sourceFromUrl("https://jobs.lever.co/envisio/123"), "Lever");
assert.strictEqual(hooks.sourceFromUrl("https://jobs.ashbyhq.com/envisio/123"), "Ashby");
assert.strictEqual(hooks.sourceFromUrl("https://apply.workable.com/envisio/j/123"), "Workable");
assert.strictEqual(hooks.sourceFromUrl("https://jobs.smartrecruiters.com/Envisio/123"), "SmartRecruiters");
assert.strictEqual(hooks.sourceFromUrl("https://www.flexjobs.com/remote-jobs/designcloud-product-designer"), "FlexJobs");
assert.strictEqual(hooks.sourceFromUrl("https://remoteok.com/remote-jobs/123456-product-designer"), "RemoteOK");
assert.strictEqual(hooks.sourceFromUrl("https://weworkremotely.com/remote-jobs/designcloud-product-designer"), "We Work Remotely");
assert.strictEqual(hooks.sourceFromUrl("https://remotive.com/remote-jobs/product/product-designer"), "Remotive");
assert.strictEqual(hooks.sourceFromUrl("https://wellfound.com/company/designcloud/jobs/123456-product-designer"), "Wellfound");
assert.strictEqual(hooks.sourceFromUrl("https://www.linkedin.com/jobs/view/1234567890/"), "LinkedIn");
assert.notStrictEqual(hooks.sourceFromUrl("https://boards.greenhouse.io/envisio/jobs/123"), "Indeed");
assert.strictEqual(hooks.isSearchOrListingPage("https://www.flexjobs.com/search?search=remote"), true);
assert.strictEqual(hooks.isSearchOrListingPage("https://remoteok.com/remote-python-jobs"), true);
assert.strictEqual(hooks.isSearchOrListingPage("https://www.flexjobs.com/remote-jobs/designcloud-product-designer"), false);
assert.strictEqual(hooks.isSearchOrListingPage("https://www.linkedin.com/jobs/search/?currentJobId=1234567890&keywords=engineer"), true);
assert.strictEqual(hooks.isSearchOrListingPage(linkedInSearchResultsUrl), true);
assert.strictEqual(hooks.isSearchOrListingPage("https://www.linkedin.com/jobs/view/1234567890/"), false);
assert.strictEqual(hooks.isLinkedInBrowseResultsPage(linkedInSearchResultsUrl), true);
assert.strictEqual(hooks.isLinkedInBrowseResultsPage("https://www.linkedin.com/jobs/search/?currentJobId=1234567890&keywords=engineer"), true);
assert.strictEqual(hooks.isLinkedInBrowseResultsPage("https://www.indeed.com/jobs?q=engineer"), false);
assert.strictEqual(hooks.shouldRejectSearchOrListingPage("https://www.linkedin.com/jobs/search/?currentJobId=1234567890&keywords=engineer"), false);
assert.strictEqual(hooks.shouldRejectSearchOrListingPage(linkedInSearchResultsUrl), false);
assert.strictEqual(hooks.shouldRejectSearchOrListingPage("https://www.linkedin.com/jobs/view/1234567890/"), false);
assert.strictEqual(hooks.shouldRejectSearchOrListingPage("https://www.indeed.com/jobs?q=engineer"), true);
assert.strictEqual(hooks.linkedInJobIdFromUrl("https://www.linkedin.com/jobs/search/?currentJobId=1234567890&keywords=engineer"), "1234567890");
assert.strictEqual(hooks.linkedInJobIdFromUrl(linkedInSearchResultsUrl), "4387144232");
assert.strictEqual(hooks.linkedInJobIdFromUrl("https://www.linkedin.com/jobs/view/1234567890/"), "1234567890");
assert.strictEqual(hooks.canonicalLinkedInJobUrl("https://www.linkedin.com/jobs/search/?currentJobId=1234567890&keywords=engineer"), "https://www.linkedin.com/jobs/view/1234567890/");
assert.strictEqual(hooks.canonicalLinkedInJobUrl(linkedInSearchResultsUrl), "https://www.linkedin.com/jobs/view/4387144232/");
assert.strictEqual(hooks.canonicalLinkedInJobUrl("https://www.linkedin.com/jobs/view/1234567890/"), "https://www.linkedin.com/jobs/view/1234567890/");
