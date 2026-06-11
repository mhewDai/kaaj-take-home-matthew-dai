import axios from "axios";
import type {
  Application,
  ApplicationCreate,
  ApplicationSummary,
  Enums,
  Lender,
  LenderSummary,
  PolicyRule,
  Program,
  RuleType,
  RunSummary,
  UnderwritingRun,
} from "../types";

const api = axios.create({ baseURL: "/api" });

// ---- reference data ----
export const getRuleTypes = () => api.get<RuleType[]>("/rule-types").then((r) => r.data);
export const getEnums = () => api.get<Enums>("/enums").then((r) => r.data);

// ---- lenders / policies ----
export const listLenders = () => api.get<LenderSummary[]>("/lenders").then((r) => r.data);
export const getLender = (id: number) => api.get<Lender>(`/lenders/${id}`).then((r) => r.data);
export const createLender = (payload: Partial<Lender>) =>
  api.post<Lender>("/lenders", payload).then((r) => r.data);
export const updateLender = (id: number, payload: Record<string, unknown>) =>
  api.patch<Lender>(`/lenders/${id}`, payload).then((r) => r.data);
export const deleteLender = (id: number) => api.delete(`/lenders/${id}`);

export const createProgram = (lenderId: number, payload: Partial<Program>) =>
  api.post<Program>(`/lenders/${lenderId}/programs`, payload).then((r) => r.data);
export const updateProgram = (id: number, payload: Record<string, unknown>) =>
  api.patch<Program>(`/programs/${id}`, payload).then((r) => r.data);
export const deleteProgram = (id: number) => api.delete(`/programs/${id}`);

export const addProgramRule = (programId: number, payload: Partial<PolicyRule>) =>
  api.post<PolicyRule>(`/programs/${programId}/rules`, payload).then((r) => r.data);
export const addLenderRule = (lenderId: number, payload: Partial<PolicyRule>) =>
  api.post<PolicyRule>(`/lenders/${lenderId}/rules`, payload).then((r) => r.data);
export const updateRule = (id: number, payload: Record<string, unknown>) =>
  api.patch<PolicyRule>(`/rules/${id}`, payload).then((r) => r.data);
export const deleteRule = (id: number) => api.delete(`/rules/${id}`);

// ---- applications ----
export const listApplications = () =>
  api.get<ApplicationSummary[]>("/applications").then((r) => r.data);
export const getApplication = (id: number) =>
  api.get<Application>(`/applications/${id}`).then((r) => r.data);
export const createApplication = (payload: ApplicationCreate) =>
  api.post<Application>("/applications", payload).then((r) => r.data);
export const deleteApplication = (id: number) => api.delete(`/applications/${id}`);

// ---- underwriting ----
export const startUnderwriting = (appId: number) =>
  api.post<UnderwritingRun>(`/applications/${appId}/underwrite`).then((r) => r.data);
export const listRuns = (appId: number) =>
  api.get<RunSummary[]>(`/applications/${appId}/runs`).then((r) => r.data);
export const getRun = (runId: number) =>
  api.get<UnderwritingRun>(`/runs/${runId}`).then((r) => r.data);

export default api;
