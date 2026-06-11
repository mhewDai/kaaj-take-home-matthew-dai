import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getApplication, getRun, listRuns, startUnderwriting } from "../api/client";
import type { Application, UnderwritingRun } from "../types";
import { currency, humanize } from "../lib/format";
import MatchResultCard from "../components/MatchResultCard";

export default function ApplicationDetailPage() {
  const { id } = useParams();
  const appId = Number(id);
  const [app, setApp] = useState<Application | null>(null);
  const [run, setRun] = useState<UnderwritingRun | null>(null);
  const [running, setRunning] = useState(false);
  const [filter, setFilter] = useState<"all" | "eligible" | "ineligible">("all");

  const loadLatestRun = useCallback(async () => {
    const runs = await listRuns(appId);
    if (runs.length > 0) setRun(await getRun(runs[0].id));
    else setRun(null);
  }, [appId]);

  useEffect(() => {
    getApplication(appId).then(setApp);
    loadLatestRun();
  }, [appId, loadLatestRun]);

  const rerun = async () => {
    setRunning(true);
    try {
      const r = await startUnderwriting(appId);
      setRun(r);
    } finally {
      setRunning(false);
    }
  };

  if (!app) return <p className="text-slate-500">Loading…</p>;

  const results = run?.results ?? [];
  const shown = results.filter((r) =>
    filter === "all" ? true : filter === "eligible" ? r.eligible : !r.eligible
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/applications" className="text-sm text-brand-600 hover:underline">
            ← Applications
          </Link>
          <h1 className="text-2xl font-semibold text-slate-800">
            {app.business?.legal_name}
          </h1>
          <p className="text-sm text-slate-500">
            #{app.id}
            {app.reference ? ` · ${app.reference}` : ""} ·{" "}
            {currency(app.loan_request?.amount)} · {app.loan_request?.term_months} mo
          </p>
        </div>
        <button onClick={rerun} disabled={running} className="btn-primary">
          {running ? "Underwriting…" : run ? "Re-run underwriting" : "Run underwriting"}
        </button>
      </div>

      {/* application summary */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Fact label="Industry" value={humanize(app.business?.industry ?? "")} />
        <Fact label="State" value={app.business?.state ?? "—"} />
        <Fact label="Years in business" value={String(app.business?.years_in_business ?? "—")} />
        <Fact label="Guarantor FICO" value={app.guarantor?.fico?.toString() ?? "Corp-only"} />
        <Fact label="PayNet" value={app.business_credit?.paynet_score?.toString() ?? "—"} />
        <Fact label="Equipment" value={humanize(app.equipment?.equipment_type ?? "")} />
        <Fact label="Equipment year" value={app.equipment?.year?.toString() ?? "—"} />
        <Fact label="Comparable credit" value={app.business_credit?.comparable_credit_pct != null ? `${app.business_credit.comparable_credit_pct}%` : "—"} />
      </div>

      {/* run status */}
      {run && (
        <div className="flex flex-wrap items-center gap-3">
          {run.status === "failed" ? (
            <div className="w-full rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              Underwriting failed: {run.error}
            </div>
          ) : (
            <>
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-700">
                {run.eligible_count} eligible
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-600">
                {run.lender_count} lenders evaluated
              </span>
              <div className="ml-auto flex gap-1 rounded-md border border-slate-200 bg-white p-0.5 text-sm">
                {(["all", "eligible", "ineligible"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`rounded px-3 py-1 ${
                      filter === f ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {humanize(f)}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* results */}
      {!run ? (
        <div className="card p-10 text-center text-slate-500">
          No underwriting run yet. Click “Run underwriting”.
        </div>
      ) : (
        <div className="space-y-3">
          {shown.map((mr) => (
            <MatchResultCard key={mr.id} mr={mr} />
          ))}
        </div>
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="card px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="truncate text-sm font-medium text-slate-700">{value || "—"}</div>
    </div>
  );
}
