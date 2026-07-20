# Security Rules

## Secrets Handling
*   **Environment Variables**: All secrets must be loaded via `.env` (using `os.getenv`).
*   **Never Hardcode**: Passwords, API keys, DSNs, and tokens must NEVER be committed to the repository.

## Important Credentials
*   `CAPITAL_API_KEY`, `CAPITAL_PASSWORD`, `CAPITAL_IDENTIFIER`: Capital.com auth credentials.
*   `POSTGRES_DSN`: Database connection string containing password.

## Authentication / Authorization
*   Currently, the API appears to be an internal-facing tool.
*   If exposed publicly, standard authentication must be added (currently missing/unknown in API layer).

## Sensitive Data Logging
*   **Never log passwords, API keys, or raw PostgreSQL connection strings.**
*   Obfuscate or mask `CAPITAL_PASSWORD` in any debug prints or exception stack traces.

## Dependency Risks
*   Run pip audits occasionally. Stick to pinned versions in `requirements.txt`.

## Execution Risks (Demo vs Real)
*   Ensure `CAPITAL_EXECUTION_DEMO_ONLY=1` remains intact in the `.env` default flow.
*   Any code modifying `capital_execution.py` must be carefully audited to prevent accidental real money trading.
