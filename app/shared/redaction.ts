const REDACTED = "[REDACTED]";

const SENSITIVE_KEYS = new Set([
  "authorization",
  "cst",
  "xsecuritytoken",
  "capitalapikey",
  "capitalcomapikey",
  "capitalidentifier",
  "capitalcomidentifier",
  "capitalpassword",
  "capitalcompassword",
  "postgresdsn",
  "databaseurl",
  "telegramtoken",
  "telegrambottoken",
  "newxaudesktoptoken",
  "desktopbearertoken",
  "cookie",
  "setcookie",
  "session",
  "sessionid",
  "account",
  "accountid",
  "accountname",
  "accountnumber",
  "accountbalance"
]);

function normalizedKey(key: string): string {
  return key.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function isSensitiveKey(key: string): boolean {
  const normalized = normalizedKey(key);
  return (
    SENSITIVE_KEYS.has(normalized) ||
    normalized.endsWith("password") ||
    normalized.endsWith("apikey") ||
    normalized.endsWith("securitytoken") ||
    normalized.endsWith("bearertoken") ||
    normalized.endsWith("sessiontoken") ||
    normalized.startsWith("account")
  );
}

export function redactSensitiveText(value: string): string {
  return value
    .replace(
      /^(\s*(?:authorization|cst|x-security-token|set-cookie|cookie)\s*:\s*).*$/gim,
      `$1${REDACTED}`
    )
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, `Bearer ${REDACTED}`)
    .replace(/\bpostgres(?:ql)?:\/\/[^\s"'<>]+/gi, REDACTED)
    .replace(
      /((?:"|')?(?:authorization|cst|x-security-token|capital(?:com)?[_-]?(?:api[_-]?key|identifier|password)|postgres[_-]?dsn|database[_-]?url|telegram(?:[_-]?bot)?[_-]?token|newxau[_-]?desktop[_-]?token|desktop[_-]?bearer[_-]?token|set-cookie|cookie|session(?:[_-]?id|[_-]?token)?|account(?:[_-]?(?:id|name|number|balance))?)(?:"|')?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;\r\n}]+)/gi,
      `$1${REDACTED}`
    )
    .replace(/\[REDACTED\](?:\s+\[REDACTED\])+/g, REDACTED);
}

export function redactSensitiveValue(value: unknown): unknown {
  const seen = new WeakSet<object>();

  const visit = (candidate: unknown): unknown => {
    if (typeof candidate === "string") return redactSensitiveText(candidate);
    if (
      candidate === null ||
      typeof candidate === "number" ||
      typeof candidate === "boolean" ||
      typeof candidate === "undefined"
    ) {
      return candidate;
    }
    if (candidate instanceof Error) {
      return {
        name: candidate.name,
        message: redactSensitiveText(candidate.message),
        stack: candidate.stack ? redactSensitiveText(candidate.stack) : undefined
      };
    }
    if (Array.isArray(candidate)) return candidate.map(visit);
    if (typeof candidate !== "object") return redactSensitiveText(String(candidate));
    if (seen.has(candidate)) return "[Circular]";
    seen.add(candidate);
    return Object.fromEntries(
      Object.entries(candidate as Record<string, unknown>).map(([key, item]) => [
        key,
        isSensitiveKey(key) ? REDACTED : visit(item)
      ])
    );
  };

  return visit(value);
}

export function redactErrorMessage(reason: unknown): string {
  if (reason instanceof Error) return redactSensitiveText(reason.message);
  return redactSensitiveText(String(reason));
}

export function redactDiagnosticPayload(value: unknown): unknown {
  return redactSensitiveValue(value);
}
