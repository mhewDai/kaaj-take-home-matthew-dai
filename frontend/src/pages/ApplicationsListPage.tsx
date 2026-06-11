import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { deleteApplication, listApplications } from "../api/client";
import type { ApplicationSummary } from "../types";
import { currency } from "../lib/format";

export default function ApplicationsListPage() {
  const [apps, setApps] = useState<ApplicationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    listApplications()
      .then(setApps)
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const remove = async (id: number) => {
    if (!confirm("Delete this application?")) return;
    await deleteApplication(id);
    load();
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Applications</h1>
          <p className="text-sm text-slate-500">
            Submit a loan application and underwrite it against all active lenders.
          </p>
        </div>
        <Link to="/applications/new" className="btn-primary">
          + New application
        </Link>
      </div>

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : apps.length === 0 ? (
        <div className="card p-10 text-center text-slate-500">
          No applications yet.{" "}
          <Link to="/applications/new" className="text-brand-600 underline">
            Create one
          </Link>
          .
        </div>
      ) : (
        <div className="card divide-y divide-slate-100">
          {apps.map((a) => (
            <div key={a.id} className="flex items-center justify-between px-4 py-3">
              <Link to={`/applications/${a.id}`} className="min-w-0 flex-1">
                <div className="font-medium text-slate-800">
                  {a.business_name || "Untitled business"}
                </div>
                <div className="text-xs text-slate-500">
                  #{a.id}
                  {a.reference ? ` · ${a.reference}` : ""} · {currency(a.amount)} ·{" "}
                  {a.status}
                </div>
              </Link>
              <div className="flex items-center gap-2">
                <Link to={`/applications/${a.id}`} className="btn-secondary">
                  View
                </Link>
                <button
                  onClick={() => remove(a.id)}
                  className="text-sm text-slate-400 hover:text-rose-600"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
