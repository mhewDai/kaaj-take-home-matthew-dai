// Types mirroring the backend Pydantic schemas.

export type EvalStatus =
  | "pass"
  | "fail"
  | "warning"
  | "not_applicable"
  | "insufficient_data";

export type RuleSeverity =
  | "knockout"
  | "qualification"
  | "prerequisite"
  | "preference";

export interface RuleParam {
  name: string;
  type: string;
  label: string;
  required: boolean;
  options_enum: string | null;
  help: string | null;
}

export interface RuleType {
  key: string;
  label: string;
  category: string;
  description: string;
  default_severity: RuleSeverity;
  params: RuleParam[];
}

export interface PolicyRule {
  id: number;
  lender_id: number;
  program_id: number | null;
  rule_type: string;
  config: Record<string, unknown>;
  severity: RuleSeverity;
  description: string | null;
  is_active: boolean;
  scope: string;
}

export interface Program {
  id: number;
  lender_id: number;
  name: string;
  rank: number;
  rate: number | null;
  credit_grade: string | null;
  notes: string | null;
  is_active: boolean;
  metadata_json: Record<string, unknown>;
  rules: PolicyRule[];
}

export interface LenderSummary {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  program_count: number;
}

export interface Lender {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  metadata_json: Record<string, unknown>;
  programs: Program[];
  rules: PolicyRule[];
}

export interface Business {
  legal_name: string;
  industry: string;
  state: string;
  years_in_business: number;
  annual_revenue?: number | null;
  entity_type?: string | null;
  number_of_trucks?: number | null;
}

export interface Guarantor {
  full_name?: string | null;
  fico?: number | null;
  is_homeowner?: boolean | null;
  is_us_citizen?: boolean | null;
  industry_experience_years?: number | null;
  has_cdl?: boolean | null;
  cdl_years?: number | null;
  has_secondary_income?: boolean | null;
  bankruptcy: boolean;
  bankruptcy_years_since_discharge?: number | null;
  has_open_judgments: boolean;
  has_foreclosures: boolean;
  has_repossessions: boolean;
  has_tax_liens: boolean;
  has_recent_collections: boolean;
  collections_years_ago?: number | null;
  personal_revolving_balance?: number | null;
  unsecured_debt?: number | null;
}

export interface BusinessCredit {
  paynet_score?: number | null;
  trade_lines?: number | null;
  comparable_credit_pct?: number | null;
}

export interface LoanRequest {
  amount: number;
  term_months: number;
  down_payment_pct?: number | null;
  soft_costs_pct?: number | null;
  is_private_party_sale: boolean;
}

export interface Equipment {
  equipment_type: string;
  year?: number | null;
  condition?: string | null;
  mileage?: number | null;
  description?: string | null;
}

export interface ApplicationCreate {
  reference?: string | null;
  business: Business;
  guarantor?: Guarantor | null;
  business_credit?: BusinessCredit | null;
  loan_request: LoanRequest;
  equipment: Equipment;
}

export interface Application extends ApplicationCreate {
  id: number;
  status: string;
}

export interface ApplicationSummary {
  id: number;
  reference: string | null;
  status: string;
  business_name: string | null;
  amount: number | null;
}

export interface CriterionResult {
  id: number;
  program_id: number | null;
  program_name: string | null;
  rule_type: string;
  label: string;
  status: EvalStatus;
  severity: RuleSeverity;
  message: string;
  expected: string | null;
  actual: string | null;
}

export interface MatchResult {
  id: number;
  lender_id: number;
  lender_name: string;
  eligible: boolean;
  fit_score: number;
  rank: number;
  matched_program_id: number | null;
  matched_program_name: string | null;
  matched_program_rate: number | null;
  reasons: string[];
  criteria: CriterionResult[];
}

export interface UnderwritingRun {
  id: number;
  application_id: number;
  status: string;
  error: string | null;
  eligible_count: number;
  lender_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  derived_features: Record<string, unknown>;
  results: MatchResult[];
}

export interface RunSummary {
  id: number;
  application_id: number;
  status: string;
  error: string | null;
  eligible_count: number;
  lender_count: number;
  created_at: string;
}

export interface Enums {
  industries: string[];
  equipment_types: string[];
  severities: string[];
}
