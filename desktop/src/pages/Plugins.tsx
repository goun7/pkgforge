import { useCallback, useEffect, useState } from "react";
import { Puzzle, Download, Trash2, RefreshCw, ShieldCheck, Loader2 } from "lucide-react";
import { call, eventBinder, onEvent } from "../lib/rpc";
import type { InstalledPlugin, AvailablePlugin, PluginAudit } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";
import { cn } from "../lib/utils";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

type Tab = "installed" | "available";

export function Plugins() {
  const { toast } = useToast();
  const lang = useLang();
  const t = tFor(lang);
  const [tab, setTab] = useState<Tab>("installed");
  const [installed, setInstalled] = useState<InstalledPlugin[]>([]);
  const [available, setAvailable] = useState<AvailablePlugin[]>([]);
  const [audits, setAudits] = useState<PluginAudit[]>([]);
  const [loading, setLoading] = useState(true);
  const [availLoading, setAvailLoading] = useState(false);
  const [busy, setBusy] = useState("");

  const loadInstalled = useCallback(async () => {
    setLoading(true);
    try {
      const res = await call<InstalledPlugin[]>("plugin.list");
      setInstalled(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const loadAvailable = useCallback(async () => {
    setAvailLoading(true);
    try {
      const res = await call<AvailablePlugin[]>("plugin.available");
      setAvailable(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setAvailLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadInstalled();
  }, [loadInstalled]);

  // plugin install/update finish events
  useEffect(() => {
    const binder = eventBinder();
    binder.bind(() => onEvent<{ ok: boolean; result?: { ok?: boolean; message?: string }; error?: string }>(
      "event/plugin_done",
      (p) => {
        setBusy("");
        if (p.ok) {
          toast("success", p.result?.message ?? t("plugDone"));
          void loadInstalled();
        } else {
          toast("error", p.error ?? t("plugFail"));
        }
      },
    ));
    return () => binder.dispose();
  }, [toast, loadInstalled]);

  const handleInstall = async (name: string) => {
    setBusy(name);
    try {
      await call("plugin.install", { name });
    } catch (e) {
      setBusy("");
      toast("error", (e as Error).message);
    }
  };

  const handleUninstall = async (name: string) => {
    setBusy(name);
    try {
      await call("plugin.uninstall", { name });
      toast("success", `${name} ${t("plugRemoved")}`);
      void loadInstalled();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const handleUpdate = async (name: string) => {
    setBusy(name);
    try {
      await call("plugin.update", { name });
    } catch (e) {
      setBusy("");
      toast("error", (e as Error).message);
    }
  };

  const handleAudit = async () => {
    setBusy("__audit__");
    try {
      const res = await call<PluginAudit[]>("plugin.audit");
      setAudits(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="h-full overflow-y-auto p-5">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2"><Puzzle size={16} /> {t("plugTitle")}</CardTitle>
          <Button variant="secondary" size="sm" onClick={() => void handleAudit()} disabled={busy === "__audit__"}>
            {busy === "__audit__" ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
            {t("plugAudit")}
          </Button>
        </CardHeader>
        <CardContent>
          {/* tabs */}
          <div className="mb-4 flex gap-1 border-b border-[var(--border-subtle)]">
            <button
              onClick={() => setTab("installed")}
              className={cn(
                "rounded-t-md px-3 py-2 text-sm font-medium transition-colors",
                tab === "installed"
                  ? "border-b-2 border-[var(--brand-blue)] text-[var(--brand-blue)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
              )}
            >
              {t("plugInstalled")} ({installed.length})
            </button>
            <button
              onClick={() => { setTab("available"); if (!available.length && !availLoading) void loadAvailable(); }}
              className={cn(
                "rounded-t-md px-3 py-2 text-sm font-medium transition-colors",
                tab === "available"
                  ? "border-b-2 border-[var(--brand-blue)] text-[var(--brand-blue)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
              )}
            >
              {t("plugAvailable")}
            </button>
          </div>

          {tab === "installed" && (
            loading ? (
              <div className="space-y-2"><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></div>
            ) : installed.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">{t("plugNoLocal")}</p>
            ) : (
              <div className="space-y-2">
                {installed.map((p) => (
                  <div key={p.name} className="flex items-center justify-between rounded-md bg-[var(--bg-elevated)] px-3 py-2">
                    <div className="flex items-center gap-2 text-sm">
                      <Puzzle size={15} className="text-[var(--brand-blue)]" />
                      <span className="font-medium">{p.name}</span>
                      <span className="text-xs text-[var(--text-muted)]">{p.size} B</span>
                    </div>
                    <div className="flex gap-1">
                      <button
                        aria-label={`${t("plugUpdate")} ${p.name}`}
                        title={t("plugUpdate")}
                        onClick={() => void handleUpdate(p.name)}
                        disabled={busy === p.name}
                        className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--brand-blue)]"
                      >
                        {busy === p.name ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                      </button>
                      <button
                        aria-label={`${t("commonRemove")} ${p.name}`}
                        title={t("commonRemove")}
                        onClick={() => void handleUninstall(p.name)}
                        disabled={busy === p.name}
                        className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--danger)]"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )
          )}

          {tab === "available" && (
            availLoading ? (
              <div className="space-y-2"><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></div>
            ) : available.length === 0 ? (
              <div className="space-y-2">
                <p className="text-sm text-[var(--text-muted)]">{t("plugNotFound")}</p>
                <Button variant="secondary" size="sm" onClick={() => void loadAvailable()}>
                  <RefreshCw size={14} /> {t("toolsRefresh")}
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                {available.map((p) => (
                  <div key={p.name} className="flex items-center justify-between rounded-md bg-[var(--bg-elevated)] px-3 py-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-medium">{p.name}</span>
                        <Badge tone="neutral">v{p.version}</Badge>
                      </div>
                      <p className="truncate text-xs text-[var(--text-muted)]">{p.description}</p>
                    </div>
                    <Button size="sm" variant="secondary" onClick={() => void handleInstall(p.name)} disabled={busy === p.name}>
                      {busy === p.name ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                      {t("commonInstall")}
                    </Button>
                  </div>
                ))}
              </div>
            )
          )}

          {/* audit results */}
          {audits.length > 0 && (
            <div className="mt-4 space-y-1">
              <h4 className="text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t("plugAuditResults")}</h4>
              {audits.map((a) => (
                <div key={a.name} className="flex items-center gap-2 rounded-md bg-[var(--bg-elevated)] px-3 py-2 text-xs">
                  <Badge tone={a.status === "ok" ? "success" : "danger"}>{a.status}</Badge>
                  <span>{a.name}</span>
                  <span className="text-[var(--text-muted)]">{a.message}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
