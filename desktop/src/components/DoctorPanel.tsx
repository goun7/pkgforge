import { useState } from "react";
import { Stethoscope, Loader2, CheckCircle2, AlertTriangle, XCircle, Copy } from "lucide-react";
import { call } from "../lib/rpc";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/Card";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { Skeleton } from "./ui/Skeleton";
import { useToast } from "./ui/Toast";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

interface DoctorTools {
  ok: boolean;
  missing_required: string[];
  missing_optional: string[];
  debtap: boolean;
  pkexec: boolean;
  distrobox: boolean;
}
interface DoctorProbe {
  ok: boolean;
  detail?: unknown;
}
interface DoctorStorage extends DoctorProbe {
  config_dir?: string;
  config_dir_exists?: boolean;
  profile?: string;
  history_db_exists?: boolean;
  queue_db_exists?: boolean;
}
interface DoctorScheduler extends DoctorProbe {
  tasks?: number;
}
interface DoctorReport {
  version: string;
  ok: boolean;
  tools: DoctorTools;
  polkit?: DoctorProbe; // Faz 15: sudo/pkexec deneyimi teşhisi (eski yanıtlerde yok)
  keyring: DoctorProbe;
  storage: DoctorStorage;
  dbus: DoctorProbe;
  scheduler: DoctorScheduler;
}

function StatusIcon({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle2 size={16} className="shrink-0 text-[var(--success)]" />
  ) : (
    <XCircle size={16} className="shrink-0 text-[var(--danger)]" />
  );
}

/** Faz 9 (2.1): app.doctor sonuclarini gorsellestiren sistem sagligi karti. */
export function DoctorPanel() {
  const t = tFor(useLang());
  const { toast } = useToast();
  const [report, setReport] = useState<DoctorReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Faz 10 (5.10): hata raporu icin tanilari Markdown olarak panoya kopyala.
  const copyReport = async () => {
    if (!report) return;
    const lines: string[] = [
      "# PkgForge Diagnostics",
      "- version: " + report.version,
      "- ok: " + String(report.ok),
      "- tools.ok: " + String(report.tools.ok),
    ];
    if (report.tools.missing_required.length) lines.push("- missing_required: " + report.tools.missing_required.join(", "));
    if (report.tools.missing_optional.length) lines.push("- missing_optional: " + report.tools.missing_optional.join(", "));
    if (report.polkit) {
      lines.push("- polkit.ok: " + String(report.polkit.ok));
      if (!report.polkit.ok && report.polkit.detail) {
        lines.push("  - " + String(report.polkit.detail));
      }
    }
    lines.push("- keyring.ok: " + String(report.keyring.ok));
    lines.push("- storage.ok: " + String(report.storage.ok) + (report.storage.profile ? " (profile: " + report.storage.profile + ")" : ""));
    lines.push("- dbus.ok: " + String(report.dbus.ok));
    lines.push("- scheduler.ok: " + String(report.scheduler.ok) + (typeof report.scheduler.tasks === "number" ? " (tasks: " + report.scheduler.tasks + ")" : ""));
    lines.push("- platform: " + navigator.platform);
    lines.push("- lang: " + navigator.language);
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      toast("success", t("doctorCopied"));
    } catch {
      toast("error", t("doctorCopyFail"));
    }
  };

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await call<DoctorReport>("app.doctor");
      setReport(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const detailStr = (d: unknown): string => {
    if (d == null) return "";
    if (typeof d === "string") return d;
    try {
      return JSON.stringify(d);
    } catch {
      return String(d);
    }
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Stethoscope size={16} /> {t("doctorTitle")}
        </CardTitle>
        <div className="flex items-center gap-2">
          {report && (
            <Button size="sm" variant="secondary" onClick={() => void copyReport()}>
              <Copy size={14} /> {t("doctorCopy")}
            </Button>
          )}
          <Button size="sm" onClick={() => void run()} disabled={busy}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Stethoscope size={14} />}
            {t("doctorRun")}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {busy && <Skeleton className="h-24 w-full" />}
        {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
        {!busy && report && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              {report.ok ? (
                <Badge tone="success">{t("doctorOk")}</Badge>
              ) : (
                <Badge tone="danger">{t("doctorIssues")}</Badge>
              )}
              <span className="text-xs text-[var(--text-muted)]">
                {t("doctorVersion")}: {report.version}
              </span>
            </div>
            <ul className="space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <StatusIcon ok={report.tools.ok} />
                <div>
                  <span className="font-medium">{t("doctorTools")}</span>
                  {report.tools.missing_required.length > 0 && (
                    <p className="text-xs text-[var(--danger)]">
                      {t("doctorMissingReq")}: {report.tools.missing_required.join(", ")}
                    </p>
                  )}
                  {report.tools.missing_optional.length > 0 && (
                    <p className="text-xs text-[var(--text-muted)]">
                      {t("doctorMissingOpt")}: {report.tools.missing_optional.join(", ")}
                    </p>
                  )}
                </div>
              </li>
              {report.polkit && (
                <li className="flex items-start gap-2">
                  <StatusIcon ok={report.polkit.ok} />
                  <div>
                    <span className="font-medium">{t("doctorPolkit")}</span>
                    {!report.polkit.ok && report.polkit.detail != null && (
                      <p className="text-xs text-[var(--warning)]">{detailStr(report.polkit.detail)}</p>
                    )}
                  </div>
                </li>
              )}
              <li className="flex items-start gap-2">
                <StatusIcon ok={report.keyring.ok} />
                <div>
                  <span className="font-medium">{t("doctorKeyring")}</span>
                  {report.keyring.detail != null && (
                    <p className="text-xs text-[var(--text-muted)]">{detailStr(report.keyring.detail)}</p>
                  )}
                </div>
              </li>
              <li className="flex items-start gap-2">
                <StatusIcon ok={report.storage.ok} />
                <div>
                  <span className="font-medium">{t("doctorStorage")}</span>
                  {report.storage.profile && (
                    <p className="text-xs text-[var(--text-muted)]">
                      {t("doctorProfile")}: {report.storage.profile}
                    </p>
                  )}
                </div>
              </li>
              <li className="flex items-start gap-2">
                <StatusIcon ok={report.dbus.ok} />
                <div>
                  <span className="font-medium">{t("doctorDbus")}</span>
                  {report.dbus.detail != null && (
                    <p className="text-xs text-[var(--text-muted)]">{detailStr(report.dbus.detail)}</p>
                  )}
                </div>
              </li>
              <li className="flex items-start gap-2">
                <StatusIcon ok={report.scheduler.ok} />
                <div>
                  <span className="font-medium">{t("doctorScheduler")}</span>
                  {typeof report.scheduler.tasks === "number" && (
                    <p className="text-xs text-[var(--text-muted)]">{report.scheduler.tasks} task</p>
                  )}
                </div>
              </li>
            </ul>
            {!report.tools.ok && (
              <div className="flex items-start gap-2 rounded-md border border-[var(--warning)]/40 bg-[var(--warning)]/10 p-2 text-xs text-[var(--text-secondary)]">
                <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[var(--warning)]" />
                <span>sudo pacman -S --needed {report.tools.missing_required.join(" ")}</span>
              </div>
            )}
            {report.polkit && !report.polkit.ok && (
              <div className="flex items-start gap-2 rounded-md border border-[var(--warning)]/40 bg-[var(--warning)]/10 p-2 text-xs text-[var(--text-secondary)]">
                <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[var(--warning)]" />
                <span>{t("doctorPolkitFix")}</span>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
