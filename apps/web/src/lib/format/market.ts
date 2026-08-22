import type { Numberish } from "@/lib/api/types";

const priceFormatter = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 });
const compactFormatter = new Intl.NumberFormat("id-ID", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function toNumber(value: Numberish | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatPrice(value: Numberish | null | undefined): string {
  const parsed = toNumber(value);
  return parsed === null ? "—" : priceFormatter.format(parsed);
}

export function formatSigned(value: Numberish | null | undefined, digits = 2): string {
  const parsed = toNumber(value);
  if (parsed === null) return "—";
  return `${parsed > 0 ? "+" : ""}${parsed.toFixed(digits)}`;
}

export function formatCompact(value: Numberish | null | undefined): string {
  const parsed = toNumber(value);
  return parsed === null ? "—" : compactFormatter.format(parsed);
}

export function marketDirection(value: Numberish | null | undefined): "up" | "down" | "flat" {
  const parsed = toNumber(value);
  if (parsed === null || parsed === 0) return "flat";
  return parsed > 0 ? "up" : "down";
}
