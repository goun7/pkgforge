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
  output_pkg?: string;
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

/* --- Faz 1 / A2: security panel --- */

export interface SignatureInfo {
  signed: boolean;
  valid: boolean;
  key_id: string;
  key_fingerprint: string;
  signer: string;
  timestamp: string;
  detail: string;
}

export interface SbomEntry {
  path: string;
  file_type: string;
  size_bytes: number;
  sha256: string;
}

export interface SbomDocument {
  package_name: string;
  package_version: string;
  package_arch: string;
  package_description: string;
  files: SbomEntry[];
  dependencies: string[];
  total_files: number;
  total_size_bytes: number;
  elf_count: number;
  text_count: number;
  symlink_count: number;
  dir_count: number;
}

export interface QualityCheck {
  name: string;
  category: string;
  passed: boolean;
  score: number;
  max_score: number;
  detail: string;
}

export interface QualityReport {
  package_name: string;
  total_score: number;
  max_score: number;
  checks: QualityCheck[];
  grade: string;
  passed: boolean;
}

export interface Provenance {
  source_file: string;
  source_type: string;
  source_url: string;
  source_sha256: string;
  output_file: string;
  output_sha256: string;
  [key: string]: unknown;
}

export interface SigstoreStatus {
  cosign_available: boolean;
  cosign_path: string;
  cosign_version: string;
}

/* --- Faz 1 / A4: delta updater --- */

export interface DeltaStatus {
  installed: boolean;
  active: boolean;
  next_run: string;
}

/* --- Faz 1 / A6: system tools --- */

export interface HealthStats {
  total: number;
  installed: number;
  converted: number;
  failed: number;
  success_rate: number;
  by_type: Record<string, number>;
  by_arch: Record<string, number>;
  url_count: number;
  first_seen: string;
  last_seen: string;
}

export interface CrossCheckReport {
  package_name: string;
  local_version: string;
  aur_version: string;
  flatpak_version: string;
  recommended_source: string;
  recommendation_reason: string;
}

export interface SnapshotStatus {
  [key: string]: unknown;
}

export interface RollbackVerifyResult {
  verified: boolean;
  backend: string;
  snapshot_name: string;
  detail: string;
  files_checked: number;
  state_before: string;
  state_after: string;
}

export interface BenchmarkResult {
  name: string;
  duration_ms: number;
  memory_peak_kb: number;
  input_size_bytes: number;
  output_size_bytes: number;
  details: string;
  passed: boolean;
}

export interface BenchmarkReport {
  results: BenchmarkResult[];
  total_duration_ms: number;
  passed: boolean;
}

/* --- Faz 1 / A1: export centers --- */

export interface FlatpakApp {
  app_id: string;
  name: string;
  version: string;
  branch: string;
  description: string;
  origin: string;
}

export interface ExportResult {
  ok: boolean;
  message: string;
  output_path?: string;
  deb_path?: string;
}

/* --- Faz 1 / A3: dependency graph --- */

export interface DepNode {
  name: string;
  version: string;
  deps: string[];
  needed_by: string[];
  is_installed: boolean;
  is_foreign: boolean;
}

export interface DepGraphData {
  root: string;
  nodes: Record<string, DepNode>;
  stats: {
    total: number;
    installed: number;
    missing: number;
    foreign: number;
    max_depth: number;
  };
  mermaid: string;
  warnings: string[];
}

/* --- Faz 2 / B1: AUR browser --- */

export interface AurSearchResult {
  name: string;
  version: string;
  description: string;
  num_votes: number;
  out_of_date: boolean;
  url_path: string;
}

export interface AurInfo {
  status: string;
  aur_version: string;
  out_of_date: boolean;
  last_modified: string;
  detail: string;
}

/* --- Faz 2 / B8: plugin marketplace --- */

export interface InstalledPlugin {
  name: string;
  path: string;
  size: string;
}

export interface AvailablePlugin {
  name: string;
  version: string;
  description: string;
  download_url: string;
  sha256_url: string;
}

export interface PluginAudit {
  name: string;
  status: string;
  message: string;
}

/* --- Faz 2 / B5: package comparison --- */

export interface SbomDiff {
  old_name: string;
  new_name: string;
  old_version: string;
  new_version: string;
  added_files: string[];
  removed_files: string[];
  changed_files: { path: string; old_sha256: string; new_sha256: string }[];
  changed_deps: string[];
  added_deps: string[];
  removed_deps: string[];
  version_changes: { dep: string; old: string; new: string }[];
  old_total_files: number;
  new_total_files: number;
  old_total_size: number;
  new_total_size: number;
}

/* --- Faz 1 / A5: from-source --- */

export interface SourceResult {
  ok: boolean;
  proj_name: string;
  build_system: string;
  pkgbuild_path: string;
  pkgbuild_content: string;
}
