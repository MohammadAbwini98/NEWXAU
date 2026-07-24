import { describe, expect, it } from "vitest";
import {
  redactDiagnosticPayload,
  redactErrorMessage,
  redactSensitiveText
} from "./redaction";

describe("desktop diagnostic redaction", () => {
  it("redacts authentication headers, DSNs, tokens, cookies, and key-value secrets", () => {
    const value = [
      "Authorization: Bearer desktop-secret",
      "CST=session-secret",
      "X-SECURITY-TOKEN: security-secret",
      "CAPITAL_API_KEY=capital-secret",
      "CAPITAL_IDENTIFIER=user@example.invalid",
      "CAPITAL_PASSWORD=password-secret",
      "POSTGRES_DSN=postgresql://user:password@localhost/newxau",
      "TELEGRAM_BOT_TOKEN=telegram-secret",
      "Cookie: session=session-cookie; preference=private-value"
    ].join("\n");

    const redacted = redactSensitiveText(value);

    for (const secret of [
      "desktop-secret",
      "session-secret",
      "security-secret",
      "capital-secret",
      "user@example.invalid",
      "password-secret",
      "postgresql://",
      "telegram-secret",
      "session-cookie",
      "private-value"
    ]) {
      expect(redacted).not.toContain(secret);
    }
  });

  it("redacts nested broker account and session fields for diagnostics and support data", () => {
    const redacted = redactDiagnosticPayload({
      request: {
        headers: { Authorization: "Bearer token", CST: "session" },
        accountId: "account-123"
      },
      response: {
        accountName: "Demo Account",
        balance: 1200,
        nested: [{ password: "secret", market: "XAUUSD" }]
      }
    });

    expect(redacted).toEqual({
      request: {
        headers: { Authorization: "[REDACTED]", CST: "[REDACTED]" },
        accountId: "[REDACTED]"
      },
      response: {
        accountName: "[REDACTED]",
        balance: 1200,
        nested: [{ password: "[REDACTED]", market: "XAUUSD" }]
      }
    });
  });

  it("sanitizes error messages before they are shown in the renderer", () => {
    expect(redactErrorMessage(new Error("Authorization: Bearer top-secret"))).toBe(
      "Authorization: [REDACTED]"
    );
  });
});
