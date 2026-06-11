import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addLenderRule,
  addProgramRule,
  createProgram,
  deleteRule,
  getEnums,
  getLender,
  getRuleTypes,
  updateRule,
} from "../api/client";
import type { Enums, Lender, PolicyRule, RuleParam, RuleType } from "../types";
import { humanize } from "../lib/format";

function enumOptions(enums: Enums | null, name: string | null): string[] {
  if (!enums || !name) return [];
  if (name === "Industry") return enums.industries;
  if (name === "EquipmentType") return enums.equipment_types;
  return [];
}

/** A single editable parameter input, rendered from the rule-type descriptor. */
function ParamInput({
  param, value, onChange, enums,
}: {
  param: RuleParam;
  value: unknown;
  onChange: (v: unknown) => void;
  enums: Enums | null;
}) {
  if (param.type === "int" || param.type === "float") {
    return (
      <input className="input" type="number" value={(value as number) ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} />
    );
  }
  if (param.type === "bool") {
    return (
      <input type="checkbox" className="h-4 w-4" checked={Boolean(value)}
        onChange={(e) => onChange(e.target.checked)} />
    );
  }
  if (param.type === "enum[]") {
    const opts = enumOptions(enums, param.options_enum);
    const selected = new Set((value as string[]) ?? []);
    return (
      <select className="input h-28" multiple value={[...selected]}
        onChange={(e) => onChange([...e.target.selectedOptions].map((o) => o.value))}>
        {opts.map((o) => (
          <option key={o} value={o}>{humanize(o)}</option>
        ))}
      </select>
    );
  }
  if (param.type === "string[]") {
    const arr = (value as string[]) ?? [];
    return (
      <input className="input" value={arr.join(", ")} placeholder="comma,separated"
        onChange={(e) => onChange(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))} />
    );
  }
  // string (incl. JSON tiers)
  return (
    <input className="input" value={(value as string) ?? ""}
      onChange={(e) => onChange(e.target.value)} />
  );
}

function RuleEditor({
  rule, ruleType, enums, onSaved,
}: {
  rule: PolicyRule;
  ruleType?: RuleType;
  enums: Enums | null;
  onSaved: () => void;
}) {
  const [config, setConfig] = useState<Record<string, unknown>>(rule.config);
  const [severity, setSeverity] = useState(rule.severity);
  const [active, setActive] = useState(rule.is_active);
  const [dirty, setDirty] = useState(false);

  const setParam = (name: string, v: unknown) => {
    setConfig((c) => ({ ...c, [name]: v }));
    setDirty(true);
  };

  const save = async () => {
    await updateRule(rule.id, { config, severity, is_active: active });
    setDirty(false);
    onSaved();
  };
  const remove = async () => {
    if (!confirm("Delete this rule?")) return;
    await deleteRule(rule.id);
    onSaved();
  };

  return (
    <div className={`rounded-md border p-3 ${active ? "border-slate-200" : "border-slate-100 bg-slate-50 opacity-60"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-800">
            {ruleType?.label ?? rule.rule_type}
          </span>
          <code className="rounded bg-slate-100 px-1 text-[11px] text-slate-500">
            {rule.rule_type}
          </code>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <select className="rounded border border-slate-200 px-1 py-0.5"
            value={severity} onChange={(e) => { setSeverity(e.target.value as PolicyRule["severity"]); setDirty(true); }}>
            {["knockout", "qualification", "prerequisite", "preference"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <label className="flex items-center gap-1 text-slate-500">
            <input type="checkbox" checked={active}
              onChange={(e) => { setActive(e.target.checked); setDirty(true); }} />
            active
          </label>
          <button onClick={remove} className="text-slate-400 hover:text-rose-600">Delete</button>
        </div>
      </div>

      {ruleType && ruleType.params.length > 0 && (
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {ruleType.params.map((p) => (
            <label key={p.name} className="text-xs text-slate-500">
              <span className="mb-0.5 block">{p.label}</span>
              <ParamInput param={p} value={config[p.name]} enums={enums}
                onChange={(v) => setParam(p.name, v)} />
            </label>
          ))}
        </div>
      )}

      {dirty && (
        <div className="mt-2 flex justify-end">
          <button onClick={save} className="btn-primary px-3 py-1 text-xs">Save changes</button>
        </div>
      )}
    </div>
  );
}

function AddRule({
  ruleTypes, enums, onAdd,
}: {
  ruleTypes: RuleType[];
  enums: Enums | null;
  onAdd: (payload: Partial<PolicyRule>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState(ruleTypes[0]?.key ?? "");
  const rt = ruleTypes.find((r) => r.key === key);
  const [config, setConfig] = useState<Record<string, unknown>>({});

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="btn-secondary mt-2 w-full text-sm">
        + Add rule
      </button>
    );
  }
  return (
    <div className="mt-2 rounded-md border border-dashed border-brand-300 bg-brand-50/40 p-3">
      <select className="input mb-2"
        value={key}
        onChange={(e) => { setKey(e.target.value); setConfig({}); }}>
        {ruleTypes.map((r) => (
          <option key={r.key} value={r.key}>{r.label} — {r.category}</option>
        ))}
      </select>
      {rt && rt.params.length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {rt.params.map((p) => (
            <label key={p.name} className="text-xs text-slate-500">
              <span className="mb-0.5 block">{p.label}</span>
              <ParamInput param={p} value={config[p.name]} enums={enums}
                onChange={(v) => setConfig((c) => ({ ...c, [p.name]: v }))} />
            </label>
          ))}
        </div>
      )}
      <div className="mt-2 flex justify-end gap-2">
        <button onClick={() => setOpen(false)} className="btn-secondary px-3 py-1 text-xs">Cancel</button>
        <button
          onClick={() => {
            onAdd({ rule_type: key, config, severity: rt?.default_severity });
            setOpen(false);
            setConfig({});
          }}
          className="btn-primary px-3 py-1 text-xs"
        >
          Add
        </button>
      </div>
    </div>
  );
}

export default function LenderDetailPage() {
  const { id } = useParams();
  const lenderId = Number(id);
  const [lender, setLender] = useState<Lender | null>(null);
  const [ruleTypes, setRuleTypes] = useState<RuleType[]>([]);
  const [enums, setEnums] = useState<Enums | null>(null);

  const reload = () => getLender(lenderId).then(setLender);

  useEffect(() => {
    reload();
    getRuleTypes().then(setRuleTypes);
    getEnums().then(setEnums);
  }, [lenderId]);

  const rtFor = (key: string) => ruleTypes.find((r) => r.key === key);

  const addProgram = async () => {
    const name = prompt("New program name?");
    if (!name) return;
    await createProgram(lenderId, { name, rank: (lender?.programs.length ?? 0) + 1 });
    reload();
  };

  if (!lender) return <p className="text-slate-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/lenders" className="text-sm text-brand-600 hover:underline">← Lenders</Link>
        <h1 className="text-2xl font-semibold text-slate-800">{lender.name}</h1>
        <p className="text-sm text-slate-500">{lender.description}</p>
      </div>

      {/* lender-wide knockouts */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Lender-wide rules
        </h2>
        <p className="mb-3 text-xs text-slate-400">
          Apply to every program (industry/state/citizenship/bankruptcy knockouts, …).
        </p>
        <div className="space-y-2">
          {lender.rules.map((r) => (
            <RuleEditor key={r.id} rule={r} ruleType={rtFor(r.rule_type)} enums={enums} onSaved={reload} />
          ))}
        </div>
        <AddRule
          ruleTypes={ruleTypes}
          enums={enums}
          onAdd={async (payload) => {
            await addLenderRule(lenderId, payload);
            reload();
          }}
        />
      </div>

      {/* programs */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">
          Programs ({lender.programs.length})
        </h2>
        <button onClick={addProgram} className="btn-secondary text-sm">+ Add program</button>
      </div>

      <div className="space-y-4">
        {lender.programs.map((p) => (
          <div key={p.id} className="card p-5">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-800">{p.name}</h3>
                <div className="text-xs text-slate-400">
                  rank {p.rank}
                  {p.rate != null ? ` · ${p.rate}%` : ""}
                  {p.credit_grade ? ` · grade ${p.credit_grade}` : ""}
                </div>
              </div>
            </div>
            <div className="space-y-2">
              {p.rules.map((r) => (
                <RuleEditor key={r.id} rule={r} ruleType={rtFor(r.rule_type)} enums={enums} onSaved={reload} />
              ))}
            </div>
            <AddRule
              ruleTypes={ruleTypes}
              enums={enums}
              onAdd={async (payload) => {
                await addProgramRule(p.id, payload);
                reload();
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
