import { useEffect, useState } from "react";
import {
  Loader2, Server, UploadCloud, Download, PackageOpen, RefreshCw,
} from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { FleetStatus } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";

export function Fleet() {
  const { toast } = useToast();
  const [status, setStatus] = useState<FleetStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [syncBusy, setSyncBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    try {
      const res = await call<FleetStatus>("fleet.status");
      setStatus(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let unsub: (() => void) | undefined;
    void onEvent<{ ok: boolean; error?: string }>(
      "event/sync_done",
      (p) => {
        setSyncBusy(false);
        if (p.ok) toast("success", "Senkron tamamlandi");
        else toast("error", p.error ?? "Senkron basarisiz");
      },
    ).then((u) => { unsub = u; });
    return () => { if (unsub) unsub(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toast]);

  const syncPush = async () => {
    setSyncBusy(true);
    try { await call("sync.push"); }
    catch (e) { setSyncBusy(false); toast("error", (e as Error).message); }
  };

  const syncPull = async () => {
    setSyncBusy(true);
    try { await call("sync.pull"); }
    catch (e) { setSyncBusy(false); toast("error", (e as Error).message); }
  };

  const syncExport = async () => {
    setSyncBusy(true);
    try {
      await call("sync.export");
      setSyncBusy(false);
      toast("success", "Yedek export tamamlandi");
    } catch (e) { setSyncBusy(false); toast("error", (e as Error).message); }
  };

  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="grid gap-4">
        <Card>
          <CardHeader><CardTitle>Fleet Konsolu</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Button onClick={() => void load()} disabled={busy}>
                {busy ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                Yenile
              </Button>
              {status ? <Badge>{status.policy_level}</Badge> : null}
              {status ? (
                <span className="text-xs text-[var(--text-secondary)]">
                  <Server size={14} className="mr-1 inline" />
                  {status.history_count} gecmis kayit
                </span>
              ) : null}
            </div>
          </CardContent>
        </Card>

        {status ? (
          <Card>
            <CardHeader><CardTitle>Senkron Backend'leri</CardTitle></CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {status.backend_names.map((name) => {
                  const b = status.backends[name] ?? { configured: false, available: false };
                  return (
                    <li key={name} className="flex items-center gap-2 text-sm">
                      <Badge>{b.available ? "HAZIR" : "YOK"}</Badge>
                      <span>{name}</span>
                      {b.configured ? <Badge>yapilandirildi</Badge> : null}
                    </li>
                  );
                })}
              </ul>
              <p className="mt-3 text-xs text-[var(--text-secondary)]">
                age sifreleme: {status.age_available ? "var" : "yok"}
              </p>
            </CardContent>
          </Card>
        ) : null}

        {status ? (
          <Card>
            <CardHeader><CardTitle>Durum Ozeti</CardTitle></CardHeader>
            <CardContent>
              <ul className="space-y-1 text-sm">
                <li>Profiller: {status.profiles.join(", ") || "-"}</li>
                <li>Senkron: {status.sync_configured ? "yapilandirildi" : "yok"}</li>
                <li>Politika: {status.policy_level}</li>
              </ul>
            </CardContent>
          </Card>
        ) : null}

        <Card>
          <CardHeader><CardTitle>Senkron Eylemleri</CardTitle></CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Button onClick={syncPush} disabled={syncBusy}>
                <UploadCloud size={16} /> Push
              </Button>
              <Button onClick={syncPull} disabled={syncBusy}>
                <Download size={16} /> Pull
              </Button>
              <Button variant="outline" onClick={syncExport} disabled={syncBusy}>
                <PackageOpen size={16} /> Yedek Export
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
