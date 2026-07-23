# Security Rules

## Secrets Handling
*   **Environment Variables**: All secrets must be loaded via `.env` (using `os.getenv`).
*   **Never Hardcode**: Passwords, API keys, DSNs, and tokens must NEVER be committed to the repository.

## Important Credentials
*   `CAPITAL_API_KEY`, `CAPITAL_PASSWORD`, `CAPITAL_IDENTIFIER`: Capital.com auth credentials.
*   `POSTGRES_DSN`: Database connection string containing password.

## Authentication / Authorization
* The legacy development API remains internal-facing when
  `NEWXAU_DESKTOP_TOKEN` is unset.
* Desktop mode generates a random per-launch token in Electron main. All
  `/api/*` requests require its bearer token and `/ws/events` requires the token
  query parameter.
* The backend binds to loopback only. Configured desktop CORS uses one exact
  origin rather than a wildcard.
* Electron uses context isolation, disables renderer Node integration, validates
  IPC senders, blocks unexpected navigation/windows, and exposes one method per
  allowed IPC action.
* The generic REST bridge permits GET requests plus an explicit mutation
  allowlist. Direct order-submission endpoints are not exposed to the renderer.
* Electron-vite emits an ESM preload, which Electron requires to run
  unsandboxed. The risk is bounded by the isolated narrow bridge, sender guards,
  CSP, and navigation lockdown.

## Desktop Secrets

* Capital.com, PostgreSQL, and Telegram secret values are encrypted through
  Electron `safeStorage` in `%LOCALAPPDATA%\NEWXAU`.
* The renderer can only query whether a secret is configured; decrypted values
  are injected into the owned Python child environment and never returned to
  renderer JavaScript.
* The Electron-owned backend accepts encrypted desktop secrets or explicitly
  inherited environment values. Missing Capital.com, PostgreSQL, and Telegram
  keys are passed as empty values so development startup cannot silently import
  credentials from the repository `.env`.
* Desktop settings and secret writes are serialized and use temporary-file
  replacement.

## Sensitive Data Logging
*   **Never log passwords, API keys, or raw PostgreSQL connection strings.**
*   Obfuscate or mask `CAPITAL_PASSWORD` in any debug prints or exception stack traces.
* Desktop diagnostics use the shared `app/shared/redaction.ts` boundary before
  log persistence, backend state/error display, failed-response diagnostics,
  or future support export. It redacts Authorization/CST/security headers,
  Capital.com credentials, PostgreSQL DSNs, Telegram and desktop tokens,
  cookies/sessions, and broker account fields.
* Successful business API payloads are not treated as support bundles. Full
  execution-order exports remain operational data and must be handled as
  sensitive.

## Dependency Risks
*   Run pip audits occasionally. Stick to pinned versions in `requirements.txt`.
* `npm audit` reports zero vulnerabilities for the checked-in desktop lockfile.
  Packaging requires Node 22.12 or newer.
* Packaged mode never falls back to PATH Python. The private runtime and model
  bundle are verified against SHA-256 manifests before test packaging.
* The private runtime is warmed before hashing, and the owned backend disables
  runtime bytecode writes so launch cannot mutate the verified inventory.

## Execution Risks (Demo vs Real)
*   Ensure `CAPITAL_EXECUTION_DEMO_ONLY=1` remains intact in the `.env` default flow.
*   Any code modifying `capital_execution.py` must be carefully audited to prevent accidental real money trading.
