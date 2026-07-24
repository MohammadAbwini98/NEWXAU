import type { PriceSnapshot } from "./apiClient";

interface SignalPriceReference {
  current_price?: unknown;
  entry_price?: unknown;
}

export interface DisplayPrice {
  value: number | undefined;
  detail: string;
  referenceOnly: boolean;
}

function finiteNumber(value: unknown): number | undefined {
  const number = typeof value === "number" ? value : Number.NaN;
  return Number.isFinite(number) ? number : undefined;
}

export function resolveDisplayPrice(
  price: PriceSnapshot | null | undefined,
  signal: SignalPriceReference | null | undefined
): DisplayPrice {
  const directPrice = finiteNumber(price?.price);
  const bid = finiteNumber(price?.bid);
  const ask = finiteNumber(price?.ask);
  const livePrice = directPrice ?? (
    bid !== undefined && ask !== undefined ? (bid + ask) / 2 : undefined
  );

  if (livePrice !== undefined) {
    return {
      value: livePrice,
      detail: price?.source ?? "Latest market price",
      referenceOnly: false
    };
  }

  const referencePrice = finiteNumber(signal?.current_price)
    ?? finiteNumber(signal?.entry_price);
  if (referencePrice !== undefined) {
    return {
      value: referencePrice,
      detail: price?.status === "REFERENCE_ONLY"
        ? "Synthetic signal reference · not a live quote"
        : "Signal reference · live quote unavailable",
      referenceOnly: true
    };
  }

  return {
    value: undefined,
    detail: price?.message ?? price?.source ?? "Waiting for a market price",
    referenceOnly: true
  };
}
