import { describe, expect, it } from "vitest";
import {
  BackendProcessManager,
  assertBackendRequestAllowed,
  resolveDesktopSecretEnvironment
} from "./backendProcessManager";
import type { AppPaths } from "./appPaths";
import type { SecretStore } from "./secretStore";

describe("backend request bridge policy", () => {
  it("allows read-only API requests and explicitly required mutations", () => {
    expect(() => assertBackendRequestAllowed("/api/dashboard/summary", "GET")).not.toThrow();
    expect(() => assertBackendRequestAllowed("/api/execution/control", "PUT")).not.toThrow();
    expect(() => assertBackendRequestAllowed("/api/backtests/run", "POST")).not.toThrow();
  });

  it("blocks order submission and unlisted mutations", () => {
    expect(() => assertBackendRequestAllowed("/api/execution/execute-latest", "POST")).toThrow(/does not permit/);
    expect(() => assertBackendRequestAllowed("/api/execution/execute/42", "POST")).toThrow(/does not permit/);
    expect(() => assertBackendRequestAllowed("/api/desktop/shutdown", "POST")).toThrow(/does not permit/);
    expect(() => assertBackendRequestAllowed("//attacker.invalid/api", "GET")).toThrow(/Invalid/);
  });

  it("prevents implicit repository env secrets while preserving explicit desktop values", () => {
    const environment = resolveDesktopSecretEnvironment(
      { POSTGRES_DSN: "stored-postgres" },
      { CAPITAL_API_KEY: "explicit-capital" }
    );

    expect(environment.POSTGRES_DSN).toBe("stored-postgres");
    expect(environment.CAPITAL_API_KEY).toBe("explicit-capital");
    expect(environment.CAPITALCOM_PASSWORD).toBe("");
    expect(environment.TELEGRAM_BOT_TOKEN).toBe("");
  });

  it("reports a blocking failure without spawning when no verified runtime is available", async () => {
    const paths: AppPaths = {
      appDataRoot: "C:/NEWXAU-test",
      logsRoot: "C:/NEWXAU-test/logs",
      runtimeRoot: "C:/NEWXAU-test/runtime",
      resourceRoot: "C:/NEWXAU-test/backend",
      backendRoot: "C:/NEWXAU-test/backend",
      pythonExecutable: null,
      pythonRuntimeSource: "missing",
      pythonResolutionError:
        "Packaged runtime missing. Authorization: Bearer should-not-reach-renderer"
    };
    const secrets = { environment: async () => ({}) } as SecretStore;
    const manager = new BackendProcessManager(paths, secrets);

    const state = await manager.start();

    expect(state).toMatchObject({
      phase: "failed",
      pid: null,
      baseUrl: null
    });
    expect(state.message).toContain("Authorization: [REDACTED]");
    expect(state.message).not.toContain("should-not-reach-renderer");
  });
});
