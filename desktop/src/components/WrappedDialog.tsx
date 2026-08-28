import { useEffect, useState } from "react";
import { PartyPopper, Loader2 } from "lucide-react";
import { call } from "../lib/rpc";
import { Dialog } from "./ui/Dialog";
import { Skeleton } from "./ui/Skeleton";
import { fmtNumber } from "../lib/format";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

interface WrappedReport {
  year: number;
  total: number;
  success: number;
  failed: number;
  success_rate: number;
  by_type: Record<string, number>;
  by_month: Record<string, number>;
  top_packages: { name: string; count: number }[];
  distinct_packages: number;
  busiest_month: string;
  url_count: number;
}

interface WrappedDialogProps {
  open: boolean;
  onClose: () => void;
  year?: number;
}

/** Faz 9 (2.2): Spotify-Wrapped tarzi yillik donusum ozeti dialog'u. */
export function WrappedDialog({ open, onClose, year }: WrappedDialogProps) {
  const lang = useLang();
  const t = tFor(lang);
  const [report, setReport] = useState<WrappedReport | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setLoading(true);
    setReport(null);
    call<WrappedReport>("stats.wrapped", year ? { year } : {})
      .then((res) => {
        if (alive) setReport(res);
      })
      .catch(() => {
        if (alive) setReport(null);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [open, year]);

  return (
    <Dialog open={open} onClose={onClose} title={t("wrappedTitle")} className="max-w-lg">
      {loading && <Skeleton className="h-48 w-full" />}
      {!loading && report && report.total === 0 && (
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <PartyPopper size={32} className="text-[var(--text-muted)]" />
          <p className="text-sm text-[var(--text-muted)]">{t("wrappedEmpty")}</p>
        </div>
      )}
      {!loading && report && report.total > 0 && (
        <div className="space-y-5">
          <div className="text-center">
            <div className="bg-[var(--brand-gradient)] bg-clip-text text-5xl font-extrabold text-transparent">
              {report.year}
            </div>
            <p className="mt-1 text-xs uppercase tracking-widest text-[var(--text-muted)]">
              PkgForge Wrapped
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-center">
              <div className="text-2xl font-bold">{fmtNumber(report.total, lang)}</div>
              <div className="text-[11px] text-[var(--text-muted)]">{t("wrappedConversions")}</div>
            </div>
            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-center">
              <div className="text-2xl font-bold text-[var(--success)]">{report.success_rate}%</div>
              <div className="text-[11px] text-[var(--text-muted)]">{t("wrappedSuccessRate")}</div>
            </div>
            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-center">
              <div className="text-2xl font-bold">{fmtNumber(report.distinct_packages, lang)}</div>
              <div className="text-[11px] text-[var(--text-muted)]">{t("wrappedDistinct")}</div>
            </div>
            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-center">
              <div className="truncate text-lg font-bold">{report.busiest_month || "—"}</div>
              <div className="text-[11px] text-[var(--text-muted)]">{t("wrappedBusiestMonth")}</div>
            </div>
          </div>
          {/* Faz 10 (5.2): ay-bazli mini bar grafik. */}
          {Object.keys(report.by_month).length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
                {t("wrappedByMonth")}
              </h4>
              <div className="flex items-end gap-1">
                {Object.entries(report.by_month)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([month, count]) => {
                    const max = Math.max(...Object.values(report.by_month), 1);
                    const h = Math.max(6, Math.round((count / max) * 64));
                    return (
                      <div
                        key={month}
                        className="flex flex-1 flex-col items-center gap-1"
                        title={month + ": " + count}
                      >
                        <div className="w-full rounded-t bg-[var(--brand-gradient)]" style={{ height: h + "px" }} />
                        <span className="text-[9px] text-[var(--text-muted)]">
                          {month.length > 5 ? month.slice(5) : month}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
          {report.top_packages.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
                {t("wrappedTopPackages")}
              </h4>
              <ol className="space-y-1">
                {report.top_packages.map((p, i) => (
                  <li key={p.name} className="flex items-center gap-2 text-sm">
                    <span className="w-5 text-right font-mono text-[var(--text-muted)]">{i + 1}.</span>
                    <span className="flex-1 truncate">{p.name}</span>
                    <span className="font-mono text-[var(--text-secondary)]">{p.count}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {report.url_count > 0 && (
            <p className="text-center text-xs text-[var(--text-muted)]">
              {t("wrappedFromUrl")}: {fmtNumber(report.url_count, lang)}
            </p>
          )}
        </div>
      )}
      {!loading && !report && (
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-[var(--text-muted)]">
          <Loader2 size={16} className="animate-spin" />
        </div>
      )}
    </Dialog>
  );
}
