import type { EvalStatus } from "../types";

/** "arbor_landscaping" -> "Arbor Landscaping" */
export function humanize(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function currency(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function percent(n: number | null | undefined): string {
  return n == null ? "—" : `${n}%`;
}

export const STATUS_META: Record<
  EvalStatus,
  { label: string; icon: string; chip: string; dot: string }
> = {
  pass: {
    label: "Met",
    icon: "✓",
    chip: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  fail: {
    label: "Not met",
    icon: "✕",
    chip: "bg-rose-50 text-rose-700 border-rose-200",
    dot: "bg-rose-500",
  },
  warning: {
    label: "Warning",
    icon: "!",
    chip: "bg-amber-50 text-amber-700 border-amber-200",
    dot: "bg-amber-500",
  },
  insufficient_data: {
    label: "Missing info",
    icon: "?",
    chip: "bg-slate-100 text-slate-600 border-slate-200",
    dot: "bg-slate-400",
  },
  not_applicable: {
    label: "N/A",
    icon: "–",
    chip: "bg-slate-50 text-slate-400 border-slate-200",
    dot: "bg-slate-300",
  },
};

export function scoreColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-brand-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-rose-400";
}
