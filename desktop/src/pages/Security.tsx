import { useState } from "react";
import { ShieldCheck, FileSearch, Award, ScrollText, KeyRound, Loader2, Bug } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { SignatureInfo, SbomDocument, QualityReport, Provenance, SigstoreStatus, CveScanResult } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";
import { cn } from "../lib/utils";

type Tab = "sign" | "sbom" | "quality" | "provenance" | "sigstore" | "cve";

const TABS: { id: Tab; label: string; icon: typeof ShieldCheck }[] = [
  { id: "sign", label: "İmza", icon: KeyRound },
  { id: "sbom", label: "SBOM", icon: FileSearch },
  { id: "quality", label: "Kalite", icon: Award },
  { id: "provenance", label: "Provenance", icon: ScrollText },
  { id: "sigstore", label: "Sigstore", icon: ShieldCheck },
  { id: "cve", label: "CVE Tara", icon: Bug },
];

export function Security() {
  const { toast } = useToast();
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

  const requirePath = (): boolean => {
    if (!pkgPath.trim()) {
      toast("error", "Önce bir paket yolu girin");
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

  const handleSbom = async () => {
    if (!requirePath()) return;
    setLoading(true);
    const un = await onEvent<{ ok: boolean; result?: SbomDocument; error?: string }>(
      "event.security_done",
      (p) => {
        setLoading(false);
        if (p.ok && p.result) setSbom(p.result);
        else toast("error", p.error ?? "SBOM oluşturulamadı");
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
      "event.security_done",
      (p) => {
        setLoading(false);
        if (p.ok && p.result) setQuality(p.result);
        else toast("error", p.error ?? "Kalite analizi başarısız");
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
      if (!res) toast("info", "Bu paket için provenance kaydı bulunamadı");
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
      "event.security_done",
      (p) => {
        setLoading(false);
        if (p.ok && p.result) setCve(p.result);
        else toast("error", p.error ?? "CVE taraması başarısız");
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

  return (
    <div className="h-full overflow-y-auto p-5">
      <Card>
        <CardHeader>
          <CardTitle>Güvenlik Paneli</CardTitle>
        </CardHeader>
        <CardContent>
          {/* package path input */}
          <div className="mb-4 flex items-center gap-2">
            <Input
              placeholder="Paket yolu (.pkg.tar.zst)…"
              value={pkgPath}
              onChange={(e) => setPkgPath(e.target.value)}
              className="h-9 flex-1"
            />
          </div>

          {/* tabs */}
          <div className="mb-4 flex gap-1 border-b border-[var(--border-subtle)]">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-t-md px-3 py-2 text-sm font-medium transition-colors",
                  tab === id
                    ? "border-b-2 border-[var(--brand-blue)] text-[var(--brand-blue)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                )}
              >
                <Icon size={15} />
                {label}
              </button>
            ))}
          </div>

          {/* tab content */}
          {tab === "sign" && (
            <div className="space-y-3">
              <Button onClick={() => void handleVerify()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />}
                Doğrula
              </Button>
              {sig && (
                <div className="rounded-md border border-[var(--border-subtle)] p-3 text-sm">
                  <div className="mb-2 flex items-center gap-2">
                    <Badge tone={sig.valid ? "success" : sig.signed ? "warning" : "neutral"}>
                      {sig.valid ? "Geçerli imza" : sig.signed ? "Geçersiz imza" : "İmzasız"}
                    </Badge>
                  </div>
                  {sig.signed && (
                    <dl className="grid grid-cols-[120px_1fr] gap-y-1 text-xs">
                      <dt className="text-[var(--text-muted)]">Key ID</dt>
                      <dd className="font-mono">{sig.key_id}</dd>
                      <dt className="text-[var(--text-muted)]">İmzalayan</dt>
                      <dd>{sig.signer}</dd>
                      <dt className="text-[var(--text-muted)]">Zaman</dt>
                      <dd>{sig.timestamp}</dd>
                    </dl>
                  )}
                  {sig.detail && <p className="mt-2 text-xs text-[var(--text-muted)]">{sig.detail}</p>}
                </div>
              )}
            </div>
          )}

          {tab === "sbom" && (
            <div className="space-y-3">
              <Button onClick={() => void handleSbom()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <FileSearch size={15} />}
                SBOM Oluştur
              </Button>
              {loading && <Skeleton className="h-24 w-full" />}
              {sbom && (
                <div className="space-y-3">
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div className="rounded-md bg-[var(--bg-elevated)] p-2">
                      <div className="text-lg font-bold">{sbom.total_files}</div>
                      <div className="text-xs text-[var(--text-muted)]">Dosya</div>
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
                      <div className="text-xs text-[var(--text-muted)]">Bağımlılık</div>
                    </div>
                  </div>
                  <div className="max-h-64 overflow-y-auto rounded-md border border-[var(--border-subtle)]">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-[var(--bg-surface)]">
                        <tr className="text-left text-[var(--text-muted)]">
                          <th className="p-2">Yol</th>
                          <th className="p-2">Tür</th>
                          <th className="p-2">Boyut</th>
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
              <Button onClick={() => void handleQuality()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Award size={15} />}
                Kalite Analizi
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
              <Button onClick={() => void handleProvenance()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <ScrollText size={15} />}
                Provenance Sorgula
              </Button>
              {prov && (
                <div className="rounded-md border border-[var(--border-subtle)] p-3 text-xs">
                  <dl className="grid grid-cols-[140px_1fr] gap-y-1">
                    <dt className="text-[var(--text-muted)]">Kaynak dosya</dt>
                    <dd className="font-mono">{prov.source_file}</dd>
                    <dt className="text-[var(--text-muted)]">Kaynak türü</dt>
                    <dd>{prov.source_type}</dd>
                    <dt className="text-[var(--text-muted)]">Çıktı dosyası</dt>
                    <dd className="font-mono">{prov.output_file}</dd>
                  </dl>
                </div>
              )}
            </div>
          )}

          {tab === "cve" && (
            <div className="space-y-3">
              <Button onClick={() => void handleCve()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Bug size={15} />}
                Taramayı Başlat
              </Button>
              {loading && <Skeleton className="h-24 w-full" />}
              {cve && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge tone={cve.count === 0 ? "success" : "danger"}>
                      {cve.count === 0 ? "Açık bulunamadı" : `${cve.count} açık bulundu`}
                    </Badge>
                    <span className="text-xs text-[var(--text-muted)]">
                      {cve.deps_scanned} bağımlılık tarandı
                    </span>
                    {cve.offline && <Badge tone="warning">çevrimdışı</Badge>}
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
              <Button onClick={() => void handleSigstore()} disabled={loading}>
                {loading ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
                Sigstore Durumu
              </Button>
              {sigstore && (
                <div className="rounded-md border border-[var(--border-subtle)] p-3 text-sm">
                  <div className="flex items-center gap-2">
                    <Badge tone={sigstore.cosign_available ? "success" : "warning"}>
                      {sigstore.cosign_available ? "cosign kurulu" : "cosign yok"}
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
