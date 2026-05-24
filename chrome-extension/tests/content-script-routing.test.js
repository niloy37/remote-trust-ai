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
assert.notStrictEqual(hooks.sourceFromUrl("https://boards.greenhouse.io/envisio/jobs/123"), "Indeed");
assert.strictEqual(hooks.isSearchOrListingPage("https://www.flexjobs.com/search?search=remote"), true);
assert.strictEqual(hooks.isSearchOrListingPage("https://remoteok.com/remote-python-jobs"), true);
assert.strictEqual(hooks.isSearchOrListingPage("https://www.flexjobs.com/remote-jobs/designcloud-product-designer"), false);
