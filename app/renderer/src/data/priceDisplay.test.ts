import { describe, expect, it } from "vitest";
import { resolveDisplayPrice } from "./priceDisplay";

describe("display price resolution", () => {
  it("prefers a real live price over signal references", () => {
    expect(resolveDisplayPrice(
      { bid: 2399, ask: 2401, source: "capital.com.websocket" },
      { current_price: 2300, entry_price: 2290 }
    )).toEqual({
      value: 2400,
      detail: "capital.com.websocket",
      referenceOnly: false
    });
  });

  it("uses the synthetic signal price only as an explicit reference", () => {
    expect(resolveDisplayPrice(
      { status: "REFERENCE_ONLY", source: "synthetic.candles" },
      { current_price: 2388.25, entry_price: 2380 }
    )).toEqual({
      value: 2388.25,
      detail: "Synthetic signal reference · not a live quote",
      referenceOnly: true
    });
  });

  it("keeps an honest empty state when no quote or signal price exists", () => {
    expect(resolveDisplayPrice(
      { status: "REFERENCE_ONLY", message: "Reference unavailable." },
      null
    )).toEqual({
      value: undefined,
      detail: "Reference unavailable.",
      referenceOnly: true
    });
  });
});
