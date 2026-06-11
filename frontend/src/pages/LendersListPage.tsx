import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listLenders } from "../api/client";
import type { LenderSummary } from "../types";

export default function LendersListPage() {
  const [lenders, setLenders] = useState<LenderSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listLenders()
      .then(setLenders)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-800">Lender policies</h1>
        <p className="text-sm text-slate-500">
          View and edit each lender's normalized credit policy. Editing a rule is a
          data change — no code or redeploy required.
        </p>
      </div>

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {lenders.map((l) => (
            <Link key={l.id} to={`/lenders/${l.id}`} className="card p-5 transition hover:shadow-md">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-slate-800">{l.name}</h2>
                <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                  {l.program_count} programs
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-500">{l.description}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
