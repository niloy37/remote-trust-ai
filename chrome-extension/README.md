# RemoteTrust AI Chrome Extension

This is a standalone Chrome extension UI for reading LinkedIn and Indeed job pages with explicit user consent, then sending the extracted job text to the local RemoteTrust AI backend.

## What It Reads

The extension is intentionally scoped to:

- `linkedin.com`
- `indeed.com`

It only reads the active page after the user opens the popup, checks the consent box, and clicks **Read page & analyze**.

## What It Sends

After consent, the content script extracts job-related visible text:

- job title
- company
- location
- job description
- active page URL

It sends that text to:

```text
http://127.0.0.1:8000/analyze
```

The extension does not require the Next.js frontend, but the FastAPI backend must be running.

## Install Locally

1. Start the backend:

   ```powershell
   cd C:\Users\niloy\OneDrive\Documents\scala-jobreview\remote-trust-ai
   docker compose up -d backend
   ```

2. Open Chrome and go to:

   ```text
   chrome://extensions
   ```

3. Enable **Developer mode**.
4. Click **Load unpacked**.
5. Select:

   ```text
   C:\Users\niloy\OneDrive\Documents\scala-jobreview\remote-trust-ai\chrome-extension
   ```

6. Open a LinkedIn or Indeed job page.
7. Click the RemoteTrust AI extension icon.
8. Confirm consent and analyze.

## Privacy Notes

- The extension does not auto-read pages.
- The extension only runs on LinkedIn and Indeed URL patterns.
- The user must explicitly consent in the popup for each analysis.
- Data is sent only to the local backend URL.

