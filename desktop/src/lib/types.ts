/** JSON-RPC 2.0 wire types shared with the Python sidecar. */

export interface RpcResponse<T = unknown> {
  jsonrpc: "2.0";
  id?: number | null;
  result?: T;
  error?: { code: number; message: string };
  method?: string;
  params?: unknown;
}

/* --- Sidecar event payloads --- */

export interface StepChangedEvent {
  step: number;
  status: string; // pending | running | done | error | warning
}

export interface ProgressEvent {
  value: number; // 0-100
}

export interface LogEvent {
  message: string;
  level: string; // info | warning | error | success
}

export interface CompatibilityCheck {
  name: string;
  severity: string; // pass | warning | error
  message: string;
  details: string[];
}

export interface CompatibilityReport {
  overall: string; // pass | warning | error
  grade: string; // A-F
  checks: CompatibilityCheck[];
}

export interface CompatibilityReadyEvent {
  report: CompatibilityReport;
}

export interface FinishedEvent {
  success: boolean;
  message: string;
}

/* --- Method result types --- */

export interface AppVersion {
  name: string;
  version: string;
}

export interface ToolsStatus {
  has_pacman: boolean;
  has_makepkg: boolean;
  has_distrobox: boolean;
  missing_required: string[];
  missing_optional: string[];
}

export interface HistoryRecord {
  id: number;
  timestamp: string;
  package_name: string;
  package_type: string;
  status: string;
  original_file: string;
  source_url: string;
}
