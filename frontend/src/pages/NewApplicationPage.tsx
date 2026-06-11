import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApplication, getEnums, startUnderwriting } from "../api/client";
import type { ApplicationCreate, Enums } from "../types";
import { Check, Num, Section, Select, Text } from "../components/fields";

type N = number | "";
const num = (v: N): number | null => (v === "" ? null : v);

export default function NewApplicationPage() {
  const navigate = useNavigate();
  const [enums, setEnums] = useState<Enums | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- form state (seeded with a realistic default scenario) ---
  const [reference] = useState("APP-001");
  const [legalName, setLegalName] = useState("Green Acres Landscaping LLC");
  const [industry, setIndustry] = useState("arbor_landscaping");
  const [state, setState] = useState("TX");
  const [yib, setYib] = useState<N>(6);
  const [revenue, setRevenue] = useState<N>(900000);
  const [trucks, setTrucks] = useState<N>("");

  const [hasGuarantor, setHasGuarantor] = useState(true);
  const [fico, setFico] = useState<N>(735);
  const [homeowner, setHomeowner] = useState(true);
  const [citizen, setCitizen] = useState(true);
  const [exp, setExp] = useState<N>(8);
  const [hasCdl, setHasCdl] = useState(false);
  const [secondaryIncome, setSecondaryIncome] = useState(true);
  const [bankruptcy, setBankruptcy] = useState(false);
  const [bkYears, setBkYears] = useState<N>("");
  const [judgments, setJudgments] = useState(false);
  const [foreclosures, setForeclosures] = useState(false);
  const [repos, setRepos] = useState(false);
  const [taxLiens, setTaxLiens] = useState(false);
  const [recentCollections, setRecentCollections] = useState(false);
  const [revolving, setRevolving] = useState<N>(12000);
  const [unsecured, setUnsecured] = useState<N>(8000);

  const [paynet, setPaynet] = useState<N>(690);
  const [tradeLines, setTradeLines] = useState<N>(5);
  const [comparablePct, setComparablePct] = useState<N>(80);

  const [amount, setAmount] = useState<N>(120000);
  const [term, setTerm] = useState<N>(60);
  const [downPct, setDownPct] = useState<N>(15);
  const [softPct, setSoftPct] = useState<N>(10);
  const [privateParty, setPrivateParty] = useState(false);

  const [equipType, setEquipType] = useState("construction_equipment");
  const [equipYear, setEquipYear] = useState<N>(2022);
  const [condition, setCondition] = useState("used");
  const [mileage, setMileage] = useState<N>("");

  useEffect(() => {
    getEnums().then((e) => {
      setEnums(e);
      setIndustry(e.industries[0] ?? "other");
      setEquipType(e.equipment_types[0] ?? "other");
      // keep the friendly defaults if present
      if (e.industries.includes("arbor_landscaping")) setIndustry("arbor_landscaping");
      if (e.equipment_types.includes("construction_equipment"))
        setEquipType("construction_equipment");
    });
  }, []);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    const payload: ApplicationCreate = {
      reference,
      business: {
        legal_name: legalName,
        industry,
        state: state.toUpperCase(),
        years_in_business: num(yib) ?? 0,
        annual_revenue: num(revenue),
        number_of_trucks: num(trucks),
      },
      guarantor: hasGuarantor
        ? {
            fico: num(fico),
            is_homeowner: homeowner,
            is_us_citizen: citizen,
            industry_experience_years: num(exp),
            has_cdl: hasCdl,
            has_secondary_income: secondaryIncome,
            bankruptcy,
            bankruptcy_years_since_discharge: bankruptcy ? num(bkYears) : null,
            has_open_judgments: judgments,
            has_foreclosures: foreclosures,
            has_repossessions: repos,
            has_tax_liens: taxLiens,
            has_recent_collections: recentCollections,
            personal_revolving_balance: num(revolving),
            unsecured_debt: num(unsecured),
          }
        : null,
      business_credit: {
        paynet_score: num(paynet),
        trade_lines: num(tradeLines),
        comparable_credit_pct: num(comparablePct),
      },
      loan_request: {
        amount: num(amount) ?? 0,
        term_months: num(term) ?? 60,
        down_payment_pct: num(downPct),
        soft_costs_pct: num(softPct),
        is_private_party_sale: privateParty,
      },
      equipment: {
        equipment_type: equipType,
        year: num(equipYear),
        condition,
        mileage: num(mileage),
      },
    };
    try {
      const app = await createApplication(payload);
      await startUnderwriting(app.id);
      navigate(`/applications/${app.id}`);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.toString() || e.message || "Submission failed");
      setSubmitting(false);
    }
  };

  if (!enums) return <p className="text-slate-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">New loan application</h1>
        <p className="text-sm text-slate-500">
          Fill in the borrower profile, then we underwrite it against every active lender.
        </p>
      </div>

      <Section title="Business" hint="Borrower / business profile.">
        <Text label="Legal name" value={legalName} onChange={setLegalName} />
        <Select label="Industry" value={industry} onChange={setIndustry} options={enums.industries} />
        <Text label="State" value={state} onChange={setState} placeholder="TX" />
        <Num label="Years in business" value={yib} onChange={setYib} step="0.5" />
        <Num label="Annual revenue" value={revenue} onChange={setRevenue} suffix="$" />
        <Num label="Fleet size (trucks)" value={trucks} onChange={setTrucks} />
      </Section>

      <Section title="Personal Guarantor" hint="Uncheck for a corp-only (no PG) application.">
        <div className="sm:col-span-2 lg:col-span-3">
          <Check label="Application has a personal guarantor" checked={hasGuarantor} onChange={setHasGuarantor} />
        </div>
        {hasGuarantor && (
          <>
            <Num label="FICO score" value={fico} onChange={setFico} />
            <Num label="Industry experience" value={exp} onChange={setExp} suffix="yrs" />
            <Num label="Personal revolving balance" value={revolving} onChange={setRevolving} suffix="$" />
            <Num label="Unsecured debt" value={unsecured} onChange={setUnsecured} suffix="$" />
            <div className="sm:col-span-2 lg:col-span-3 grid grid-cols-2 gap-x-6 sm:grid-cols-3 lg:grid-cols-4">
              <Check label="Homeowner" checked={homeowner} onChange={setHomeowner} />
              <Check label="US citizen" checked={citizen} onChange={setCitizen} />
              <Check label="Holds CDL" checked={hasCdl} onChange={setHasCdl} />
              <Check label="Secondary income" checked={secondaryIncome} onChange={setSecondaryIncome} />
              <Check label="Bankruptcy" checked={bankruptcy} onChange={setBankruptcy} />
              <Check label="Open judgments" checked={judgments} onChange={setJudgments} />
              <Check label="Foreclosures" checked={foreclosures} onChange={setForeclosures} />
              <Check label="Repossessions" checked={repos} onChange={setRepos} />
              <Check label="Tax liens" checked={taxLiens} onChange={setTaxLiens} />
              <Check label="Recent collections" checked={recentCollections} onChange={setRecentCollections} />
            </div>
            {bankruptcy && (
              <Num label="Years since BK discharge" value={bkYears} onChange={setBkYears} />
            )}
          </>
        )}
      </Section>

      <Section title="Business Credit">
        <Num label="PayNet MasterScore" value={paynet} onChange={setPaynet} />
        <Num label="Trade lines" value={tradeLines} onChange={setTradeLines} />
        <Num label="Comparable credit" value={comparablePct} onChange={setComparablePct} suffix="% of request" />
      </Section>

      <Section title="Loan Request">
        <Num label="Amount" value={amount} onChange={setAmount} suffix="$" />
        <Num label="Term" value={term} onChange={setTerm} suffix="months" />
        <Num label="Down payment" value={downPct} onChange={setDownPct} suffix="%" />
        <Num label="Soft costs" value={softPct} onChange={setSoftPct} suffix="%" />
        <div className="self-end">
          <Check label="Private-party sale" checked={privateParty} onChange={setPrivateParty} />
        </div>
      </Section>

      <Section title="Equipment">
        <Select label="Equipment type" value={equipType} onChange={setEquipType} options={enums.equipment_types} />
        <Num label="Year" value={equipYear} onChange={setEquipYear} />
        <Select label="Condition" value={condition} onChange={setCondition} options={["new", "used"]} />
        <Num label="Mileage / hours" value={mileage} onChange={setMileage} />
      </Section>

      {error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button onClick={submit} disabled={submitting} className="btn-primary">
          {submitting ? "Underwriting…" : "Submit & underwrite"}
        </button>
        <button onClick={() => navigate("/applications")} className="btn-secondary">
          Cancel
        </button>
      </div>
    </div>
  );
}
