export type Business = {
  id: string;
  name: string;
  description: string;
  profile_revision: number;
  onboarding_status?: "context_saved" | "analysis_started";
  analysis_count?: number;
  created_at?: string;
};
export type Memory = {
  pending?: number;
  failed?: number;
  uncertain?: number;
  needs_review?: number;
};
export type Dataset = {
  id: string;
  title: string;
  version: number;
  status: string;
  corrected?: boolean;
  superseded_by?: string;
  period_from?: string;
  period_until?: string;
  files?: { id: string; name: string; rows?: number; status?: string }[];
  original_files?: { path: string; size: number }[];
};
export type Analysis = {
  context_reference?: ContextAttachment;
  id: string;
  title: string;
  filename: string;
  created_at: string;
  status: string;
  presentation_status?: string;
  conversation_id?: string;
  data_version?: Dataset;
};
export type Workspace = {
  business: Business | null;
  businesses: Business[];
  analyses: Analysis[];
  configured: boolean;
  memory: Memory;
};
export type Chat = {
  id: string;
  business_id: string;
  title: string;
  created_at: string;
  last_message_at?: string;
};
export type ChatListing = {
  business_id: string | null;
  conversations: Chat[];
  datasets: { items: DatasetChoice[]; more: boolean };
};
export type Claim = {
  key: string;
  title: string;
  statement: string;
  interpretation?: string;
  method?: string;
  recommendation?: string;
  next_step?: string;
  evidence_details?: {
    files: string[];
    metrics: { label: string; value: string }[];
    operations: string[];
  };
};
export type ChartData = {
  key: string;
  kind: "line" | "bar" | "table";
  title: string;
  unit: string;
  caption: string;
  claim_key: string;
  points: { label: string; value: string; formatted: string }[];
};
export type Report = {
  report_id?: string;
  report_version?: string;
  title: string;
  summary?: string;
  no_chart_reason?: string;
  scope: {
    period: string;
    coverage: string;
    business?: string;
    question?: string;
  };
  claims: Claim[];
  highlights: {
    key?: string;
    label: string;
    value: string;
    unit: string;
    claim_key: string;
  }[];
  charts: ChartData[];
  limitations: string[];
};
export type Dashboard = {
  selected_id: string | null;
  report: Report | null;
  reports: { id: string; title: string; created_at: string }[];
  activity: { href: string; title: string; status: string }[];
  report_id?: string;
  report_version?: string;
  analysis_id?: string;
  created_at?: string;
  data_version?: Dataset;
};
export type ReportReference = {
  report_id: string;
  report_version: string;
  kind: "chart" | "metric" | "insight" | "section";
  element_key: string;
};
export type ContextReference =
  | ReportReference
  | {
      source_id: string;
      source_version: string;
      kind: "business" | "memory";
      element_key: string;
    };
export type ContextAttachment = ContextReference & {
  title?: string;
  period?: string;
  report_title?: string;
  href?: string;
  status?: "available" | "withdrawn";
  content?: ChartData | Claim | Report["highlights"][number];
};
export type FindingReference = {
  report_id: string;
  report_version: string;
  claim_key: string;
  title?: string;
  period?: string;
};
export type QuestionContext = {
  context_references?: ContextAttachment[];
  analysis_id?: string;
  finding_reference?: FindingReference;
  label?: string;
};
export type Question = {
  references?: { kind: string; id: string; column: string }[];
  previous_text?: string;
  id: string;
  text: string;
  reason: string;
  options?: string[];
  phase?: string;
};
export type FactContent = {
  kind: string;
  statement: string;
  topic?: string;
  scope: string;
  scope_id: string | null;
  valid_from: string | null;
  valid_until: string | null;
  temporal_scope: string;
  result_id?: string | null;
};
export type Fact = {
  id?: string;
  fact_id: string;
  revision: number;
  status: string;
  content: FactContent;
  alternatives?: {
    content?: FactContent;
    statement?: string;
    quote?: string;
  }[];
  created_at: string;
  origin_kind?: string;
  origin_key?: string;
  original_text?: string;
  quote?: string;
  question?: string;
  conversation_id?: string;
  change_kind?: string;
};
export type Dossier = {
  business_id: string;
  business: Business;
  memory: Memory;
  facts: Fact[];
  history: Fact[];
  datasets: Dataset[];
};
export type Response = Partial<Report> & {
  kind: string;
  text?: string;
  paragraphs?: string[];
  sources?: { label: string; reference: string }[];
  evidence?: Response;
  report_id?: string;
  report_version?: string;
  questions?: Question[];
  items?: ResponseItem[];
};
export type ResponseItem = {
  description?: string;
  names?: string[];
  columns?: string[];
  preceding_question?: string;
  text?: string;
  conversation_id?: string;
  status?: string;
  content?: FactContent;
};
export type Turn = {
  id: string;
  status: string;
  payload: {
    text: string;
    finding_reference?: FindingReference;
    context_references?: ContextReference[];
  };
  attachments?: ContextAttachment[];
  response?: Response;
  issue?: string;
  historical?: boolean;
  report_outdated?: boolean;
  report_requested?: boolean;
  job_id?: string;
  questions?: Question[];
  context_changed_before?: boolean;
};
export type ChatDetail = {
  conversation: Chat;
  turns: Turn[];
  dataset?: Dataset;
  memory: Memory;
  memory_items: Fact[];
  context_changed_after?: boolean;
};
export type Job = Analysis & {
  analysis_id?: string;
  unresolved_questions?: Question[];
  business_id: string;
  business: string;
  context: string;
  goal: string;
  phase: string;
  issue?: string;
  activity?: string;
  publishable: boolean;
  origin: string;
  byte_count: number;
  context_stale?: boolean;
  memory: Memory;
  questions: Question[];
  answers: { text: string; disposition: string; question?: string }[];
  interpretations: { text: string; status: string }[];
  files: { row_count?: number; column_count?: number; status: string }[];
};

export type DatasetChoice = {
  id: string;
  analysis_id: string;
  description: string;
  dataset_version: number;
  names: string[];
  columns: string[];
};

export type HomeSource = {
  job_id: string;
  report_id: string;
  version: string;
  title: string;
  period: string;
  coverage: string;
  filename: string;
  created_at: string;
  data_version?: Dataset;
  analysis_id: string;
  limitations: string[];
  href: string;
};
export type HomeItem = { id: string; title: string; source: HomeSource } & (
  | { kind: "metric"; content: Report["highlights"][number] }
  | { kind: "chart"; content: ChartData }
  | { kind: "insight"; content: Claim }
);
export type HomeDashboard = {
  business_id: string;
  revision: number;
  fingerprint: string;
  items: HomeItem[];
  sources: HomeSource[];
  selected: string[];
  pinned: string[];
  hidden: string[];
  unavailable: number;
  reasons: Record<string, string>;
  selection_origin: "initial" | "owner" | "agent";
  proposal: {
    picks: { id: string; reason: string }[];
    fingerprint: string;
  } | null;
  can_suggest: boolean;
  activity: Dashboard["activity"];
  limited: boolean;
};
