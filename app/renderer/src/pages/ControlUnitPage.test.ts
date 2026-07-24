import { describe, expect, it } from "vitest";
import { shouldAdoptControlResponse } from "./ControlUnitPage";

describe("Control Unit response ordering", () => {
  it("does not adopt a stale response while a checkbox edit is dirty", () => {
    const staleResponse = { config: { enabled: false } };
    const previousResponse = { config: { enabled: true } };

    expect(shouldAdoptControlResponse(staleResponse, previousResponse, true, false)).toBe(false);
    expect(shouldAdoptControlResponse(staleResponse, previousResponse, false, true)).toBe(false);
  });

  it("adopts a new confirmed response after edits are clean", () => {
    const confirmedResponse = { config: { enabled: true } };
    const previousResponse = { config: { enabled: false } };

    expect(shouldAdoptControlResponse(confirmedResponse, previousResponse, false, false)).toBe(true);
    expect(shouldAdoptControlResponse(previousResponse, previousResponse, false, false)).toBe(false);
  });
});
