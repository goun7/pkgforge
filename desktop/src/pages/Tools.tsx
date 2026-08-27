import { useEffect, useState } from "react";
import { Loader2, ShieldCheck, ScrollText, PackageSearch } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { RpmToDebResult, AbiReport, AuditReport } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Input } from "../components/ui/Input";
import { useToast } from "../components/ui/Toast";

export function Tools() {
  const { toast } = useToast();

  const [rpmPath, setRpmPath] = useState("");
  const [rpmBusy, setRpmBusy] = useState(false);
  const [rpmResult, setRpmResult] = useState<RpmToDebResult | null>(null);

  const [abiPath, setAbiPath] = useState("");
  const [abiBusy, setAbiBusy] = useState(false);
  const [abiReport, setAbiReport] = useState<AbiReport | null>(null);

  const [auditBusy, setAuditBusy] = useState(false);
  const [audit, setAudit] = useState<AuditReport | null>(null);

  useEffect(() => {
    let unRpm: (() => void) | undefined;
    let unAbi: (() => void) | undefined;
    void onEvent<{ ok: boolean; result?: RpmToDebResult; error?: string }>(
      "event/rpm_to_deb_done",
      (p) => {
        setRpmBusy(false);
        if (p.ok && p.result) setRpmResult(p.result);
        else toast("error", p.error ?? "RPM donusumu basarisiz");
      },
    ).then((u) => { unRpm = u; });
    void onEvent<{ ok: boolean; result?: AbiReport; error?: string }>(
      "event/abi_check_done",
      (p) => {
        setAbiBusy(false);
        if (p.ok && p.result) setAbiReport(p.result);
        else toast("error", p.error ?? "ABI taramasi basarisiz");
      },
    ).then((u) => { unAbi = u; });
    return () => {
      if (unRpm) unRpm();
      if (unAbi) unAbi();
    };
  }, [toast]);

  const handleRpm = async () => {
    if (!rpmPath.trim()) {
      toast("error", "RPM dosya yolu gerekli");
      return;
    }
    setRpmBusy(true);
    setRpmResult(null);
    try {
      await call("tools.rpm_to_deb", { rpm: rpmPath });
    } catch (e) {
      setRpmBusy(false);
      toast("error", (e as Error).message);
    }
  };

  const handleAbi = async () => {
    if (!abiPath.trim()) {
      toast("error", "Paket yolu gerekli");
      return;
    }
    setAbiBusy(true);
    setAbiReport(null);
    try {
      await call("tools.abi_check", { package: abiPath });
    } catch (e) {
      setAbiBusy(false);
      toast("error", (e as Error).message);
    }
  };

  const handleAudit = async () => {
    setAuditBusy(true);
    setAudit(null);
    try {
      const res = await call<AuditReport>("tools.audit");
      setAudit(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setAuditBusy(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="grid gap-4">
        <Card>
          <CardHeader>
            <CardTitle>RPM → DEB</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input
                value={rpmPath}
                onChange={(e) => setRpmPath(e.target.value)}
                placeholder="/yol/paket.rpm"
                aria-label="RPM dosya yolu"
              />
              <Button onClick={handleRpm} disabled={rpmBusy}>
                {rpmBusy ? <Loader2 className="animate-spin" size={16} /> : <PackageSearch size={16} />}
                Donustur
              </Button>
            </div>
            {rpmResult && (
              <p className="mt-3 text-sm">
                <Badge>{rpmResult.ok ? "BASARILI" : "HATA"}</Badge>{" "}
                {rpmResult.message}
                {rpmResult.deb_path ? " -> " + rpmResult.deb_path : ""}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>ABI Uyumluluk Denetimi</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input
                value={abiPath}
                onChange={(e) => setAbiPath(e.target.value)}
                placeholder="/yol/paket.pkg.tar.zst"
                aria-label="Paket yolu"
              />
              <Button onClick={handleAbi} disabled={abiBusy}>
                {abiBusy ? <Loader2 className="animate-spin" size={16} /> : <ShieldCheck size={16} />}
                Tara
              </Button>
            </div>
            {abiReport && (
              <div className="mt-3 text-sm">
                <Badge>{abiReport.passed ? "UYUMLU" : abiReport.error_count + " SORUN"}</Badge>
                <pre className="mt-2 whitespace-pre-wrap text-xs text-[var(--text-secondary)]">
                  {abiReport.summary}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Denetim İzi (Audit)</CardTitle>
          </CardHeader>
          <CardContent>
            <Button onClick={handleAudit} disabled={auditBusy}>
              {auditBusy ? <Loader2 className="animate-spin" size={16} /> : <ScrollText size={16} />}
              Denetim İzini Yukle
            </Button>
            {audit && (
              <div className="mt-3 text-sm">
                <p>
                  Toplam {audit.total} kayıt — {audit.integrity_issues} butunluk sorunu,{" "}
                  {audit.anomalies} anomali
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
      </div>
    </div>
  );
}
