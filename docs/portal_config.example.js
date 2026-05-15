// ── Meridian Lending Portal — Configuration Template ──────────────────────────
// Copy this file to portal_config.js and fill in your values.
// portal_config.js is gitignored — never commit it.
//
// TRIGGER_URL    : Orchestrator → Automations → Triggers → your trigger → copy URL
// ACCESS_TOKEN   : cloud.uipath.com → My Profile → Personal Access Tokens
//                  Required scopes: OR.Assets, OR.Buckets, OR.Jobs.Write, OR.Folders.Read
// ORCHESTRATOR_BASE_URL : https://cloud.uipath.com/{org}/{tenant}/orchestrator_
// BUCKET_ID      : Orchestrator → Storage Buckets → click bucket → URL shows /Buckets(XXXXX)
// FOLDER_PATH    : Name of the Orchestrator folder containing the bucket (e.g. "Shared")
// BUCKET_NAME    : Name of the storage bucket (e.g. "Loan_Applications")

const CONFIG = {
  TRIGGER_URL:          "https://cloud.uipath.com/YOUR_ORG/YOUR_TENANT/orchestrator_/t/YOUR_FOLDER_KEY/YOUR_TRIGGER_SLUG",
  ACCESS_TOKEN:         "YOUR_PERSONAL_ACCESS_TOKEN",
  CALL_MODE:            "FireAndForget",
  ORCHESTRATOR_BASE_URL: "https://cloud.uipath.com/YOUR_ORG/YOUR_TENANT/orchestrator_",
  BUCKET_ID:            "YOUR_BUCKET_ID",
  FOLDER_PATH:          "Shared",
  BUCKET_NAME:          "Loan_Applications",
};
