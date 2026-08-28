import { useEffect, useState } from "react";
import {
  Loader2, ShieldCheck, ScrollText, PackageSearch, Radar, FileCheck2,
  UploadCloud, Trash2, RefreshCw,
} from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type {
  RpmToDebResult, AbiReport, AuditReport, ScanImageResult, AttestResult,
  PublishResult, SnapshotStatus,
} from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Input } from "../components/ui/Input";
import { useToast } from "../components/ui/Toast";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

export function Tools() {
  const { toast } = useToast();
  const lang = useLang();
  const t = tFor(lang);

  const [rpmPath, setRpmPath] = useState("");
  const [rpmBusy, setRpmBusy] = useState(false);
  const [rpmResult, setRpmResult] = useState<RpmToDebResult | null>(null);

  const [abiPath, setAbiPath] = useState("");
  const [abiBusy, setAbiBusy] = useState(false);
  const [abiReport, setAbiReport] = useState<AbiReport | null>(null);

  const [auditBusy, setAuditBusy] = useState(false);
  const [audit, setAudit] = useState<AuditReport | null>(null);

  const [scanPath, setScanPath] = useState("");
  const [scanBusy, setScanBusy] = useState(false);
  const [scanResult, setScanResult] = useState<ScanImageResult | null>(null);

  const [attestPath, setAttestPath] = useState("");
  const [attestBusy, setAttestBusy] = useState(false);
  const [attestResult, setAttestResult] = useState<AttestResult | null>(null);

  const [publishPath, setPublishPath] = useState("");
  const [publishBusy, setPublishBusy] = useState(false);
  const [publishResult, setPublishResult] = useState<PublishResult | null>(null);

  const [snapshot, setSnapshot] = useState<SnapshotStatus | null>(null);
  const [snapBusy, setSnapBusy] = useState(false);

  useEffect(() => {
    const unsubs: (() => void)[] = [];
    void onEvent<{ ok: boolean; result?: RpmToDebResult; error?: string }>(
      "event/rpm_to_deb_done",
      (p) => {
        setRpmBusy(false);
        if (p.ok && p.result) setRpmResult(p.result);
        else toast("error", p.error ?? "RPM dönüşümü başarısız");
      },
    ).then((u) => { unsubs.push(u); });
    void onEvent<{ ok: boolean; result?: AbiReport; error?: string }>(
      "event/abi_check_done",
      (p) => {
        setAbiBusy(false);
        if (p.ok && p.result) setAbiReport(p.result);
        else toast("error", p.error ?? "ABI taraması başarısız");
      },
    ).then((u) => { unsubs.push(u); });
    void onEvent<{ ok: boolean; result?: ScanImageResult; error?: string }>(
      "event/scan_image_done",
      (p) => {
        setScanBusy(false);
        if (p.ok && p.result) setScanResult(p.result);
        else toast("error", p.error ?? "İmaj taraması başarısız");
      },
    ).then((u) => { unsubs.push(u); });
    void onEvent<{ ok: boolean; result?: AttestResult; error?: string }>(
      "event/attest_done",
      (p) => {
        setAttestBusy(false);
        if (p.ok && p.result) setAttestResult(p.result);
        else toast("error", p.error ?? "Attestasyon başarısız");
      },
    ).then((u) => { unsubs.push(u); });
    void onEvent<{ ok: boolean; result?: PublishResult; error?: string }>(
      "event/publish_done",
      (p) => {
        setPublishBusy(false);
        if (p.ok && p.result) setPublishResult(p.result);
        else toast("error", p.error ?? "Yayınlama başarısız");
      },
    ).then((u) => { unsubs.push(u); });
    void onEvent<{ ok: boolean; result?: { ok: boolean; message: string }; error?: string }>(
      "event/snapshot_done",
      (p) => {
        setSnapBusy(false);
        if (p.ok && p.result) {
          if (p.result.ok) toast("success", p.result.message);
          else toast("error", p.result.message);
        } else {
          toast("error", p.error ?? "Snapshot işlemi başarısız");
        }
        void loadSnapshot();
      },
    ).then((u) => { unsubs.push(u); });
    return () => { unsubs.forEach((u) => u()); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toast]);

  const loadSnapshot = async () => {
    try {
      const res = await call<SnapshotStatus>("tools.snapshot_status");
      setSnapshot(res);
    } catch {
      /* durum yuklenemedi; sessiz gec */
    }
  };

  useEffect(() => {
    void loadSnapshot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRpm = async () => {
    if (!rpmPath.trim()) { toast("error", "RPM dosya yolu gerekli"); return; }
    setRpmBusy(true); setRpmResult(null);
    try { await call("tools.rpm_to_deb", { rpm: rpmPath }); }
    catch (e) { setRpmBusy(false); toast("error", (e as Error).message); }
  };

  const handleAbi = async () => {
    if (!abiPath.trim()) { toast("error", "Paket yolu gerekli"); return; }
    setAbiBusy(true); setAbiReport(null);
    try { await call("tools.abi_check", { package: abiPath }); }
    catch (e) { setAbiBusy(false); toast("error", (e as Error).message); }
  };

  const handleAudit = async () => {
    setAuditBusy(true); setAudit(null);
    try { const res = await call<AuditReport>("tools.audit"); setAudit(res); }
    catch (e) { toast("error", (e as Error).message); }
    finally { setAuditBusy(false); }
  };

  const handleScan = async () => {
    if (!scanPath.trim()) { toast("error", "İmaj yolu gerekli"); return; }
    setScanBusy(true); setScanResult(null);
    try { await call("tools.scan_image", { image: scanPath }); }
    catch (e) { setScanBusy(false); toast("error", (e as Error).message); }
  };

  const handleAttest = async () => {
    if (!attestPath.trim()) { toast("error", "Paket yolu gerekli"); return; }
    setAttestBusy(true); setAttestResult(null);
    try { await call("tools.attest", { package: attestPath }); }
    catch (e) { setAttestBusy(false); toast("error", (e as Error).message); }
  };

  const handlePublish = async () => {
    if (!publishPath.trim()) { toast("error", "Paket yolu gerekli"); return; }
    setPublishBusy(true); setPublishResult(null);
    try { await call("tools.publish", { package: publishPath }); }
    catch (e) { setPublishBusy(false); toast("error", (e as Error).message); }
  };

  const handleSnapInstall = async () => {
    setSnapBusy(true);
    try { await call("tools.snapshot_install", { max_age_days: 7 }); }
    catch (e) { setSnapBusy(false); toast("error", (e as Error).message); }
  };

  const handleSnapRemove = async () => {
    setSnapBusy(true);
    try { await call("tools.snapshot_remove"); }
    catch (e) { setSnapBusy(false); toast("error", (e as Error).message); }
  };

  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="grid gap-4">
        <Card>
          <CardHeader><CardTitle>RPM → DEB</CardTitle></CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input value={rpmPath} onChange={(e) => setRpmPath(e.target.value)}
                placeholder={t("toolsRpmPh")} aria-label={t("toolsRpmAria")} />
              <Button onClick={handleRpm} disabled={rpmBusy}>
                {rpmBusy ? <Loader2 className="animate-spin" size={16} /> : <PackageSearch size={16} />}
                {t("toolsConvert")}
              </Button>
            </div>
            {rpmResult && (
              <p className="mt-3 text-sm">
                <Badge>{rpmResult.ok ? t("toolsOk") : t("toolsErr")}</Badge>{" "}
                {rpmResult.message}
                {rpmResult.deb_path ? " -> " + rpmResult.deb_path : ""}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("toolsAbiTitle")}</CardTitle></CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input value={abiPath} onChange={(e) => setAbiPath(e.target.value)}
                placeholder="/yol/paket.pkg.tar.zst" aria-label={t("toolsPkgPath")} />
              <Button onClick={handleAbi} disabled={abiBusy}>
                {abiBusy ? <Loader2 className="animate-spin" size={16} /> : <ShieldCheck size={16} />}
                {t("toolsScan")}
              </Button>
            </div>
            {abiReport && (
              <div className="mt-3 text-sm">
                <Badge>{abiReport.passed ? t("toolsCompatible") : abiReport.error_count + " " + t("toolsIssues")}</Badge>
                <pre className="mt-2 whitespace-pre-wrap text-xs text-[var(--text-secondary)]">
                  {abiReport.summary}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("toolsAuditTitle")}</CardTitle></CardHeader>
          <CardContent>
            <Button onClick={handleAudit} disabled={auditBusy}>
              {auditBusy ? <Loader2 className="animate-spin" size={16} /> : <ScrollText size={16} />}
              {t("toolsLoadAudit")}
            </Button>
            {audit && (
              <div className="mt-3 text-sm">
                <p>
                  {t("toolsTotal")} {audit.total} — {audit.integrity_issues} {t("toolsIntegrity")},{" "}
                  {audit.anomalies} {t("toolsAnomaly")}
                </p>
                <ul className="mt-2 space-y-1">
                  {Object.entries(audit.status_counts).map(([status, count]) => (
                    <li key={status} className="text-xs text-[var(--text-secondary)]">
                      {status}: {count}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("toolsImgTitle")}</CardTitle></CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input value={scanPath} onChange={(e) => setScanPath(e.target.value)}
                placeholder="/yol/imaj.tar" aria-label={t("toolsImgPath")} />
              <Button onClick={handleScan} disabled={scanBusy}>
                {scanBusy ? <Loader2 className="animate-spin" size={16} /> : <Radar size={16} />}
                {t("toolsScanImg")}
              </Button>
            </div>
            {scanResult && (
              <div className="mt-3 text-sm">
                <Badge>{scanResult.clean ? t("toolsClean") : scanResult.findings.length + " " + t("toolsFinding")}</Badge>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{scanResult.detail}</p>
                <ul className="mt-2 space-y-1">
                  {scanResult.findings.slice(0, 10).map((f, i) => (
                    <li key={i} className="text-xs text-[var(--text-secondary)]">
                      [{f.tool}/{f.severity}] {f.line}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Attestation (SLSA)</CardTitle></CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input value={attestPath} onChange={(e) => setAttestPath(e.target.value)}
                placeholder="/yol/paket.pkg.tar.zst" aria-label={t("toolsAttestPath")} />
              <Button onClick={handleAttest} disabled={attestBusy}>
                {attestBusy ? <Loader2 className="animate-spin" size={16} /> : <FileCheck2 size={16} />}
                {t("toolsAttestGen")}
              </Button>
            </div>
            {attestResult && (
              <div className="mt-3 text-sm">
                <Badge>{attestResult.ok ? t("toolsCreated") : t("toolsErr")}</Badge>
                {attestResult.ok ? (
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    {attestResult.subject + " → " + attestResult.attestation_path}
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">{attestResult.error}</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("toolsPubTitle")}</CardTitle></CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input value={publishPath} onChange={(e) => setPublishPath(e.target.value)}
                placeholder="/yol/paket.pkg.tar.zst" aria-label={t("toolsPubPkg")} />
              <Button onClick={handlePublish} disabled={publishBusy}>
                {publishBusy ? <Loader2 className="animate-spin" size={16} /> : <UploadCloud size={16} />}
                {t("toolsPubPrep")}
              </Button>
            </div>
            {publishResult && (
              <div className="mt-3 text-sm">
                <Badge>{publishResult.ok ? t("toolsReady") : t("toolsErr")}</Badge>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{publishResult.message}</p>
                {publishResult.pkgbuild ? (
                  <p className="text-xs text-[var(--text-secondary)]">PKGBUILD: {publishResult.pkgbuild}</p>
                ) : null}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("toolsSnapTitle")}</CardTitle></CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => void loadSnapshot()}>
                <RefreshCw size={16} /> {t("toolsRefresh")}
              </Button>
              <Button onClick={handleSnapInstall} disabled={snapBusy}>
                {snapBusy ? <Loader2 className="animate-spin" size={16} /> : <Trash2 size={16} />}
                {t("toolsInstallSvc")}
              </Button>
              <Button variant="danger" onClick={handleSnapRemove} disabled={snapBusy}>
                {t("toolsRemoveSvc")}
              </Button>
            </div>
            {snapshot && (
              <p className="mt-3 text-sm">
                {snapshot.installed
                  ? t("toolsSvcInstalled") + " — " + (snapshot.active ? t("toolsSvcActive") : t("toolsSvcStopped")) +
                    (snapshot.next_run ? " | " + t("toolsSvcNext") + " " + snapshot.next_run : "")
                  : t("toolsSvcNotInstalled")}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
