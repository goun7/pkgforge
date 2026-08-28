import { useState } from "react";
import { ShieldCheck, FileSearch, Award, ScrollText, KeyRound, Loader2, Bug } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { SignatureInfo, SbomDocument, QualityReport, Provenance, SigstoreStatus, CveScanResult } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { PathPicker, PKG_DIALOG_FILTERS } from "../components/PathPicker";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";
import { InfoTip } from "../components/ui/InfoTip";
import { cn } from "../lib/utils";
import { useLang } from "../lib/lang";
import { tFor, type I18nKey } from "../lib/i18n";

type Tab = "sign" | "sbom" | "quality" | "provenance" | "sigstore" | "cve";

const TABS: { id: Tab; labelKey: I18nKey; icon: typeof ShieldCheck }[] = [
  { id: "sign", labelKey: "secTabSign", icon: KeyRound },
  { id: "sbom", labelKey: "secTabSbom", icon: FileSearch },
  { id: "quality", labelKey: "secTabQuality", icon: Award },
  { id: "provenance", labelKey: "secTabProvenance", icon: ScrollText },
  { id: "sigstore", labelKey: "secTabSigstore", icon: ShieldCheck },
  { id: "cve", labelKey: "secTabCve", icon: Bug },
];

export function Security() {
  const { toast } = useToast();
  const lang = useLang();
  const t = tFor(lang);
  const [tab, setTab] = useState<Tab>("sign");
  const [pkgPath, setPkgPath] = useState("");
  const [loading, setLoading] = useState(false);

  // results
  const [sig, setSig] = useState<SignatureInfo | null>(null);
  const [sbom, setSbom] = useState<SbomDocument | null>(null);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [prov, setProv] = useState<Provenance | null>(null);
  const [sigstore, setSigstore] = useState<SigstoreStatus | null>(null);
  const [cve, setCve] = useState<CveScanResult | null>(null);
  const [keys, setKeys] = useState<{ key_id: string; uid?: string; algo?: string; created?: string }[] | null>(null);

  const requirePath = (): boolean => {
    if (!pkgPath.trim()) {
      toast("error", t("secNeedPath"));
      return false;
    }
    return true;
  };

  const handleVerify = async () => {
    if (!requirePath()) return;
    setLoading(true);
    try {
      const res = await call<SignatureInfo>("security.verify", { pkg_path: pkgPath });
      setSig(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadKeys = async () => {
    setLoading(true);
    try {
      const res = await call<{ key_id: string; uid?: string; algo?: string; created?: string }[]>("security.keys");
      setKeys(res ?? []);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleSbom = async () => {
    if (!requirePath()) return;
    setLoading(true);
    const un = await onEvent<{ ok: boolean; result?: SbomDocument; error?: string }>(
      "event/security_done",
      (p) => {
        setLoading(false);
        if (p.ok && p.result) setSbom(p.result);
        else toast("error", p.error ?? t("secSbomFail"));
        void un();
      },
    );
    try {
      await call("security.sbom", { pkg_path: pkgPath });
    } catch (e) {
      setLoading(false);
      toast("error", (e as Error).message);
    }
  };

  const handleQuality = async () => {
    if (!requirePath()) return;
    setLoading(true);
    const un = await onEvent<{ ok: boolean; result?: QualityReport; error?: string }>(
      "event/security_done",
      (p) => {
        setLoading(false);
        if (p.ok && p.result) setQuality(p.result);
        else toast("error", p.error ?? t("secQualityFail"));
        void un();
      },
    );
    try {
      await call("security.quality", { pkg_path: pkgPath });
    } catch (e) {
      setLoading(false);
      toast("error", (e as Error).message);
    }
  };

  const handleProvenance = async () => {
    if (!requirePath()) return;
    setLoading(true);
    try {
      const res = await call<Provenance | null>("security.provenance", { pkg_path: pkgPath });
      setProv(res);
      if (!res) toast("info", t("secNoProvenance"));
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleSigstore = async () => {
    setLoading(true);
    try {
      const res = await call<SigstoreStatus>("security.sigstore_status");
      setSigstore(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleCve = async () => {
    if (!requirePath()) return;
    setLoading(true);
    const un = await onEvent<{ ok: boolean; result?: CveScanResult; error?: string }>(
      "event/security_done",
      (p) => {
        setLoading(false);
        if (p.ok && p.result) setCve(p.result);
        else toast("error", p.error ?? t("secCveFail"));
        void un();
      },
    );
    try {
      await call("security.cve_scan", { pkg_path: pkgPath });
    } catch (e) {
      setLoading(false);
      toast("error", (e as Error).message);
    }
  };

  /** Event tabanli tek guvenlik kontrolunu calistirir, sonucla resolve olur.
   *  Hepsi ayni event/security_done kanalini kullandigind paralel degil
   *  sirali cagrilirlar (handleRunAll). */
  const runEventCheck = <T,>(method: string): Promise<T | null> =>
    new Promise((resolve) => {
      let un: (() => void) | undefined;
      const timer = setTimeout(() => {
        if (un) un();
        resolve(null);
      }, 180000);
      void onEvent<{ ok: boolean; result?: T; error?: string }>(
        "event/security_done",
        (p) => {
          clearTimeout(timer);
          if (un) un();
          resolve(p.ok && p.result ? p.result : null);
        },
      ).then((u) => { un = u; });
      call(method, { pkg_path: pkgPath }).catch(() => {
        clearTimeout(timer);
        if (un) un();
        resolve(null);
      });
    });

  /** Paket uzerindeki tum guvenlik kontrollerini sirayla calistirir. */
  const handleRunAll = async () => {
    if (!requirePath()) return;
    setLoading(true);
    try {
      try { setSig(await call<SignatureInfo>("security.verify", { pkg_path: pkgPath })); } catch { /* atla */ }
      try { setSigstore(await call<SigstoreStatus>("security.sigstore_status")); } catch { /* atla */ }
      try { setProv(await call<Provenance | null>("security.provenance", { pkg_path: pkgPath })); } catch { /* atla */ }
      setSbom(await runEventCheck<SbomDocument>("security.sbom"));
      setQuality(await runEventCheck<QualityReport>("security.quality"));
      setCve(await runEventCheck<CveScanResult>("security.cve_scan"));
      toast("success", t("secAllDone"));
    } finally {
      setLoading(false);
    }
  };

  // Ozet kart: 6 kontrolun anlik durumu (bir bakista sonuc).
  type SumTone = "neutral" | "success" | "warning" | "danger";
  const summary: { id: Tab; label: string; tone: SumTone; text: string }[] = [
    {
      id: "sign",
      label: t("secTabSign"),
      tone: sig ? (sig.valid ? "success" : sig.signed ? "danger" : "warning") : "neutral",
      text: sig ? (sig.valid ? t("secSumValid") : sig.signed ? t("secSumInvalid") : t("secSumUnsigned")) : "—",
    },
    {
      id: "sbom",
      label: t("secTabSbom"),
      tone: sbom ? "success" : "neutral",
      text: sbom ? `${sbom.total_files} ${t("secFiles")}` : "—",
    },
    {
      id: "quality",
      label: t("secTabQuality"),
      tone: quality ? (quality.passed ? "success" : "warning") : "neutral",
      text: quality ? `${quality.grade} (${quality.total_score}/${quality.max_score})` : "—",
    },
    {
      id: "provenance",
      label: t("secTabProvenance"),
      tone: prov ? "success" : "neutral",
      text: prov ? t("secSumFound") : "—",
    },
    {
      id: "sigstore",
      label: t("secTabSigstore"),
      tone: sigstore ? (sigstore.cosign_available ? "success" : "warning") : "neutral",
      text: sigstore ? (sigstore.cosign_available ? t("secCosignReady") : t("secCosignNone")) : "—",
    },
    {
      id: "cve",
      label: "CVE",
      tone: cve ? (cve.count === 0 ? "success" : "danger") : "neutral",
      text: cve ? (cve.count === 0 ? t("secClean") : `${cve.count} ${t("secOpen")}`) : "—",
    },
  ];

  return (
    <div className="h-full overflow-y-auto p-5">
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-1.5">
              {t("secTitle")}
              <InfoTip text={t("helpSecurity")} />
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* package path input + tum kontroller */}
          <div className="mb-4 flex flex-col gap-2">
            <PathPicker
              placeholder={t("secPkgPh")}
              value={pkgPath}
              onChange={setPkgPath}
              filters={PKG_DIALOG_FILTERS}
              title={t("secSelectPkg")}
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void handleRunAll()}
              disabled={loading || !pkgPath.trim()}
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
              {t("secRunAll")}
            </Button>
          </div>

          {/* ozet kart: tum kontroller bir bakista, tiklayinca ilgili sekmeye gider */}
          <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {summary.map((s) => (
              <button
                key={s.id}
                onClick={() => setTab(s.id)}
                aria-label={`${s.label} durumu: ${s.text}`}
                className={cn(
                  "flex cursor-pointer flex-col items-start gap-1 rounded-lg border p-2.5 text-left transition-all",
                  "hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand-blue)]",
                  s.tone === "success" && "border-[var(--success)]/40 bg-[var(--success)]/10",
                  s.tone === "warning" && "border-[var(--warning)]/40 bg-[var(--warning)]/10",
                  s.tone === "danger" && "border-[var(--danger)]/40 bg-[var(--danger)]/10",
                  s.tone === "neutral" && "border-[var(--border-subtle)] bg-[var(--bg-elevated)]",
                )}
              >
                <span className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">{s.label}</span>
                <span className={cn(
                  "text-sm font-semibold",
                  s.tone === "success" && "text-[var(--success)]",
                  s.tone === "warning" && "text-[var(--warning)]",
                  s.tone === "danger" && "text-[var(--danger)]",
                  s.tone === "neutral" && "text-[var(--text-secondary)]",
                )}>{s.text}</span>
              </button>
            ))}
          </div>

          {/* tabs */}
          <div className="mb-4 flex gap-1 border-b border-[var(--border-subtle)]">
            {TABS.map(({ id, labelKey, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-t-md px-3 py-2 text-sm font-medium transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand-blue)]",
                  tab === id
                    ? "border-b-2 border-[var(--brand-blue)] text-[var(--brand-blue)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                )}
              >
                <Icon size={15} />
                {t(labelKey)}
              </button>
            ))}
          </div>

          {/* tab content */}
          {tab === "sign" && (
            <div className="space-y-3">
              <Button variant="secondary" onClick={() => void handleVerify()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />}
                {t("secVerify")}
              </Button>
              {sig && (
                <div className="rounded-md border border-[var(--border-subtle)] p-3 text-sm">
                  <div className="mb-2 flex items-center gap-2">
                    <Badge tone={sig.valid ? "success" : sig.signed ? "warning" : "neutral"}>
                      {sig.valid ? t("secValidSig") : sig.signed ? t("secInvalidSig") : t("secUnsigned")}
                    </Badge>
                  </div>
                  {sig.signed && (
                    <dl className="grid grid-cols-[120px_1fr] gap-y-1 text-xs">
                      <dt className="text-[var(--text-muted)]">Key ID</dt>
                      <dd className="font-mono">{sig.key_id}</dd>
                      <dt className="text-[var(--text-muted)]">{t("secSigner")}</dt>
                      <dd>{sig.signer}</dd>
                      <dt className="text-[var(--text-muted)]">{t("secTime")}</dt>
                      <dd>{sig.timestamp}</dd>
                    </dl>
                  )}
                  {sig.detail && <p className="mt-2 text-xs text-[var(--text-muted)]">{sig.detail}</p>}
                </div>
              )}
              {/* Faz 9 (2.6): imza anahtarlari */}
              <div className="rounded-md border border-[var(--border-subtle)] p-3">
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-sm font-medium">{t("secKeysTitle")}</h4>
                  <Button variant="secondary" size="sm" onClick={() => void handleLoadKeys()} disabled={loading}>
                    {t("secKeysLoad")}
                  </Button>
                </div>
                {keys && keys.length === 0 && (
                  <p className="text-xs text-[var(--text-muted)]">{t("secKeysNone")}</p>
                )}
                {keys && keys.length > 0 && (
                  <ul className="space-y-1">
                    {keys.map((k) => (
                      <li key={k.key_id} className="flex items-center gap-2 text-xs">
                        <KeyRound size={13} className="shrink-0 text-[var(--text-muted)]" />
                        <span className="font-mono">{k.key_id}</span>
                        {k.uid && <span className="truncate text-[var(--text-secondary)]">{k.uid}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          {tab === "sbom" && (
            <div className="space-y-3">
              <Button variant="secondary" onClick={() => void handleSbom()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <FileSearch size={15} />}
                {t("secSbomCreate")}
              </Button>
              {loading && <Skeleton className="h-24 w-full" />}
              {sbom && (
                <div className="space-y-3">
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div className="rounded-md bg-[var(--bg-elevated)] p-2">
                      <div className="text-lg font-bold">{sbom.total_files}</div>
                      <div className="text-xs text-[var(--text-muted)]">{t("secFiles")}</div>
                    </div>
                    <div className="rounded-md bg-[var(--bg-elevated)] p-2">
                      <div className="text-lg font-bold">{sbom.elf_count}</div>
                      <div className="text-xs text-[var(--text-muted)]">ELF</div>
                    </div>
                    <div className="rounded-md bg-[var(--bg-elevated)] p-2">
                      <div className="text-lg font-bold">{(sbom.total_size_bytes / 1024).toFixed(0)}</div>
                      <div className="text-xs text-[var(--text-muted)]">KB</div>
                    </div>
                    <div className="rounded-md bg-[var(--bg-elevated)] p-2">
                      <div className="text-lg font-bold">{sbom.dependencies.length}</div>
                      <div className="text-xs text-[var(--text-muted)]">{t("secDeps")}</div>
                    </div>
                  </div>
                  <div className="max-h-64 overflow-y-auto rounded-md border border-[var(--border-subtle)]">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-[var(--bg-surface)]">
                        <tr className="text-left text-[var(--text-muted)]">
                          <th scope="col" className="p-2">{t("secPath")}</th>
                          <th scope="col" className="p-2">{t("secType")}</th>
                          <th scope="col" className="p-2">{t("secSize")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sbom.files.slice(0, 200).map((f) => (
                          <tr key={f.path} className="border-t border-[var(--border-subtle)]/50">
                            <td className="max-w-[280px] truncate p-2 font-mono">{f.path}</td>
                            <td className="p-2">{f.file_type}</td>
                            <td className="p-2">{f.size_bytes}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === "quality" && (
            <div className="space-y-3">
              <Button variant="secondary" onClick={() => void handleQuality()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Award size={15} />}
                {t("secQuality")}
              </Button>
              {loading && <Skeleton className="h-24 w-full" />}
              {quality && (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="text-3xl font-bold text-[var(--brand-blue)]">
                      {quality.total_score}/{quality.max_score}
                    </div>
                    <Badge tone={quality.passed ? "success" : "danger"}>{quality.grade}</Badge>
                  </div>
                  <div className="space-y-1">
                    {quality.checks.map((c) => (
                      <div key={c.name} className="flex items-center justify-between rounded-md bg-[var(--bg-elevated)] px-3 py-2 text-xs">
                        <span className={c.passed ? "text-[var(--text-primary)]" : "text-[var(--danger)]"}>
                          {c.passed ? "✓" : "✗"} {c.name}
                        </span>
                        <span className="text-[var(--text-muted)]">{c.score}/{c.max_score}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === "provenance" && (
            <div className="space-y-3">
              <Button variant="secondary" onClick={() => void handleProvenance()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <ScrollText size={15} />}
                {t("secProvQuery")}
              </Button>
              {prov && (
                <div className="rounded-md border border-[var(--border-subtle)] p-3 text-xs">
                  <dl className="grid grid-cols-[140px_1fr] gap-y-1">
                    <dt className="text-[var(--text-muted)]">{t("secSourceFile")}</dt>
                    <dd className="font-mono">{prov.source_file}</dd>
                    <dt className="text-[var(--text-muted)]">{t("secSourceType")}</dt>
                    <dd>{prov.source_type}</dd>
                    <dt className="text-[var(--text-muted)]">{t("secOutputFile")}</dt>
                    <dd className="font-mono">{prov.output_file}</dd>
                  </dl>
                </div>
              )}
            </div>
          )}

          {tab === "cve" && (
            <div className="space-y-3">
              <Button variant="secondary" onClick={() => void handleCve()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Bug size={15} />}
                {t("secCveStart")}
              </Button>
              {loading && <Skeleton className="h-24 w-full" />}
              {cve && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge tone={cve.count === 0 ? "success" : "danger"}>
                      {cve.count === 0 ? t("secCveNone") : `${cve.count} ${t("secCveFound")}`}
                    </Badge>
                    <span className="text-xs text-[var(--text-muted)]">
                      {cve.deps_scanned} {t("secDepsScanned")}
                    </span>
                    {cve.offline && <Badge tone="warning">{t("secOffline")}</Badge>}
                  </div>
                  {cve.vulns.length > 0 && (
                    <div className="max-h-64 space-y-1 overflow-y-auto">
                      {cve.vulns.map((v) => (
                        <div key={v.id} className="rounded-md bg-[var(--bg-elevated)] px-3 py-2 text-xs">
                          <div className="flex items-center gap-2">
                            <Badge tone={v.severity === "CRITICAL" || v.severity === "HIGH" ? "danger" : v.severity === "MEDIUM" ? "warning" : "neutral"}>
                              {v.severity}
                            </Badge>
                            <span className="font-mono font-medium">{v.id}</span>
                            <span className="text-[var(--text-muted)]">({v.affected_dep})</span>
                          </div>
                          {v.summary && <p className="mt-1 text-[var(--text-muted)]">{v.summary}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {tab === "sigstore" && (
            <div className="space-y-3">
              <Button variant="secondary" onClick={() => void handleSigstore()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
                {t("secSigstoreStatus")}
              </Button>
              {sigstore && (
                <div className="rounded-md border border-[var(--border-subtle)] p-3 text-sm">
                  <div className="flex items-center gap-2">
                    <Badge tone={sigstore.cosign_available ? "success" : "warning"}>
                      {sigstore.cosign_available ? t("secCosignIn") : t("secCosignOut")}
                    </Badge>
                  </div>
                  {sigstore.cosign_version && (
                    <p className="mt-2 text-xs text-[var(--text-muted)]">{sigstore.cosign_version}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
