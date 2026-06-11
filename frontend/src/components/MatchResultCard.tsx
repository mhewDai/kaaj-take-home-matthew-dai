import { useMemo, useState } from "react";
import type { CriterionResult, MatchResult } from "../types";
import { scoreColor } from "../lib/format";
import CriterionRow from "./CriterionRow";

interface Group {
  key: string;
  name: string;
  criteria: CriterionResult[];
  isMatched: boolean;
}

function groupCriteria(mr: MatchResult): Group[] {
  const byProgram = new Map<string, Group>();
  for (const c of mr.criteria) {
    const key = c.program_id == null ? "__lender__" : String(c.program_id);
    const name = c.program_id == null ? "Lender-wide requirements" : c.program_name || "Program";
    if (!byProgram.has(key)) {
      byProgram.set(key, {
        key,
        name,
        criteria: [],
        isMatched: c.program_id != null && c.program_id === mr.matched_program_id,
      });
    }
    byProgram.get(key)!.criteria.push(c);
  }
  // Lender-wide first, then the matched program, then the rest.
  return [...byProgram.values()].sort((a, b) => {
    if (a.key === "__lender__") return -1;
    if (b.key === "__lender__") return 1;
    if (a.isMatched) return -1;
    if (b.isMatched) return 1;
    return 0;
  });
}

export default function MatchResultCard({ mr }: { mr: MatchResult }) {
  const [open, setOpen] = useState(false);
  const groups = useMemo(() => groupCriteria(mr), [mr]);

  return (
    <div className={`card overflow-hidden ${mr.eligible ? "" : "opacity-95"}`}>
      <div className="flex items-start gap-4 p-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-500">
          #{mr.rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-slate-800">{mr.lender_name}</h3>
            {mr.eligible ? (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                Eligible
              </span>
            ) : (
              <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700">
                Not eligible
              </span>
            )}
            {mr.matched_program_name && (
              <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                {mr.matched_program_name}
                {mr.matched_program_rate != null && ` · ${mr.matched_program_rate}%`}
              </span>
            )}
          </div>

          {/* reasons */}
          <ul className="mt-1.5 space-y-0.5">
            {mr.reasons.map((r, i) => (
              <li key={i} className="text-sm text-slate-600">
                {mr.eligible ? "• " : "✕ "}
                {r}
              </li>
            ))}
          </ul>
        </div>

        {/* fit score */}
        <div className="w-28 shrink-0 text-right">
          <div className="text-2xl font-bold text-slate-800">{mr.fit_score}</div>
          <div className="text-[11px] uppercase tracking-wide text-slate-400">fit score</div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full ${scoreColor(mr.fit_score)}`}
              style={{ width: `${mr.fit_score}%` }}
            />
          </div>
        </div>
      </div>

      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between border-t border-slate-100 bg-slate-50 px-4 py-2 text-xs font-medium text-slate-500 hover:bg-slate-100"
      >
        <span>{open ? "Hide" : "Show"} criteria breakdown ({mr.criteria.length})</span>
        <span>{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="divide-y divide-slate-100 px-4 pb-3">
          {groups.map((g) => (
            <div key={g.key} className="py-2">
              <div className="mb-1 flex items-center gap-2">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {g.name}
                </h4>
                {g.isMatched && (
                  <span className="rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">
                    matched tier
                  </span>
                )}
              </div>
              <div className="divide-y divide-slate-50">
                {g.criteria.map((c) => (
                  <CriterionRow key={c.id} c={c} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
