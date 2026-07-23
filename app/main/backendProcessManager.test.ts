import { describe, expect, it } from "vitest";
import { assertBackendRequestAllowed } from "./backendProcessManager";

describe("backend request bridge policy", () => {
  it("allows read-only API requests and explicitly required mutations", () => {
    expect(() => assertBackendRequestAllowed("/api/dashboard/summary", "GET")).not.toThrow();
    expect(() => assertBackendRequestAllowed("/api/execution/control", "PUT")).not.toThrow();
    expect(() => assertBackendRequestAllowed("/api/backtests/run", "POST")).not.toThrow();
  });

  it("blocks order submission and unlisted mutations", () => {
    expect(() => assertBackendRequestAllowed("/api/execution/execute-latest", "POST")).toThrow(/does not permit/);
    expect(() => assertBackendRequestAllowed("/api/execution/execute/42", "POST")).toThrow(/does not permit/);
    expect(() => assertBackendRequestAllowed("//attacker.invalid/api", "GET")).toThrow(/Invalid/);
  });
});
