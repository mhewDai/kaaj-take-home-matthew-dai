import type { CriterionResult } from "../types";
import { STATUS_META } from "../lib/format";

export default function CriterionRow({ c }: { c: CriterionResult }) {
  const meta = STATUS_META[c.status];
  return (
    <div className="flex items-start gap-3 py-2">
      <span
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${meta.dot}`}
        title={meta.label}
      >
        {meta.icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-800">{c.label}</span>
          {c.severity === "preference" && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-500">
              preference
            </span>
          )}
          {c.severity === "knockout" && (
            <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-rose-500">
              knockout
            </span>
          )}
        </div>
        <p className="text-sm text-slate-600">{c.message}</p>
        {(c.expected || c.actual) && (
          <div className="mt-0.5 flex gap-4 text-xs text-slate-400">
            {c.expected && <span>Required: {c.expected}</span>}
            {c.actual && <span>Application: {c.actual}</span>}
          </div>
        )}
      </div>
    </div>
  );
}
