import { useCallback, useEffect, useRef, useState } from "react";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { Play, Square, Container, Network, Code2, Loader2, ListChecks, ArrowUp, ArrowDown, Trash2 } from "lucide-react";
import { call } from "../lib/rpc";
import type {
  StepChangedEvent,
  ProgressEvent,
  LogEvent,
  CompatibilityReadyEvent,
  FinishedEvent,
  DepGraphData,
  SourceResult,
  BatchItem,
} from "../lib/types";
import { DropZone, filterAcceptedPaths } from "../components/DropZone";
import { StepIndicator, PIPELINE_STEPS, type StepStatus } from "../components/StepIndicator";
import { ProgressBar } from "../components/ui/ProgressBar";
import { LogViewer, type LogLine } from "../components/LogViewer";
import { QueueList, type QueueItem } from "../components/QueueList";
import { Button } from "../components/ui/Button";
import { Dialog } from "../components/ui/Dialog";
import { Badge } from "../components/ui/Badge";
import { Input } from "../components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { useToast } from "../components/ui/Toast";
import { DepGraph } from "../components/DepGraph";
import { cn } from "../lib/utils";
import type { CompatibilityReport } from "../lib/types";

/** Map a pipeline step index (0-5) to the StepIndicator step name. */
function stepName(index: number): string {
  return PIPELINE_STEPS[index] ?? "unknown";
}

type ConvertTab = "convert" | "fromsource" | "batch";

export function Convert() {
  const { toast } = useToast();
  const [tab, setTab] = useState<ConvertTab>("convert");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [statuses, setStatuses] = useState<Record<string, StepStatus>>({});
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [running, setRunning] = useState(false);
  const [report, setReport] = useState<CompatibilityReport | null>(null);
  const [dragging, setDragging] = useState(false);
  const [outputPkg, setOutputPkg] = useState("");

  // graph viewer
  const [graph, setGraph] = useState<DepGraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);

  // from-source wizard
  const [repoUrl, setRepoUrl] = useState("");
  const [sourceBusy, setSourceBusy] = useState(false);
  const [sourceStep, setSourceStep] = useState("");
  const [sourceResult, setSourceResult] = useState<SourceResult | null>(null);

  // batch queue (B6)
  const [batch, setBatch] = useState<BatchItem[]>([]);
  const [batchRunning, setBatchRunning] = useState(false);
  const [parallel, setParallel] = useState("1");
  // F4.3: batch defaults to CONVERSION-ONLY; installing is an explicit opt-in.
  const [batchInstall, setBatchInstall] = useState(false);
  const [batchFilter, setBatchFilter] = useState("");

  // Refs so event callbacks always see fresh state without re-subscribing.
  const queueRef = useRef(queue);
  queueRef.current = queue;
  const runningRef = useRef(running);
  runningRef.current = running;

  /** Start the next pending item in the queue, if idle. */
  const startNext = useCallback(async () => {
    if (runningRef.current) return;
    const next = queueRef.current.find((q) => q.status === "pending");
    if (!next) return;
    setRunning(true);
    setStatuses({});
    setProgress(0);
    setLogs([]);
    setOutputPkg("");
    setGraph(null);
    setQueue((prev) =>
      prev.map((q) => (q.id === next.id ? { ...q, status: "running" } : q)),
    );
    try {
      await call("pipeline.start", { path: next.id });
    } catch (e) {
      setRunning(false);
      setQueue((prev) =>
        prev.map((q) => (q.id === next.id ? { ...q, status: "failed" } : q)),
      );
      toast("error", `${next.id}: ${(e as Error).message}`);
    }
  }, [toast]);

  // Subscribe to sidecar events once.
  useEffect(() => {
    const unsubs: Promise<UnlistenFn>[] = [
      listen<StepChangedEvent>("event/step_changed", (e) => {
        const name = stepName(e.payload.step);
        setStatuses((prev) => ({ ...prev, [name]: e.payload.status as StepStatus }));
      }),
      listen<ProgressEvent>("event/progress", (e) => setProgress(e.payload.value)),
      listen<LogEvent>("event/log", (e) =>
        setLogs((prev) => [...prev, { message: e.payload.message, level: e.payload.level }]),
      ),
      listen<CompatibilityReadyEvent>("event/compatibility_ready", (e) =>
        setReport(e.payload.report),
      ),
      listen<FinishedEvent>("event/finished", (e) => {
        const { success, message, output_pkg } = e.payload;
        setRunning(false);
        setReport(null);
        if (success && output_pkg) setOutputPkg(output_pkg);
        // Mark the currently-running queue item with the outcome.
        setQueue((prev) => {
          const idx = prev.findIndex((q) => q.status === "running");
          if (idx === -1) return prev;
          const copy = [...prev];
          copy[idx] = { ...copy[idx], status: success ? "success" : "failed" };
          return copy;
        });
        toast(success ? "success" : "error", message || (success ? "Tamamlandı" : "Başarısız"));
        // Kick off the next queued item on the next tick.
        setTimeout(() => void startNext(), 0);
      }),
      listen<{ ok: boolean; result?: DepGraphData; error?: string }>("event/graph_done", (e) => {
        setGraphLoading(false);
        const p = e.payload;
        if (p.ok && p.result) setGraph(p.result);
        else toast("error", p.error ?? "Grafik oluşturulamadı");
      }),
      listen<{ step: string }>("event/source_progress", (e) => setSourceStep(e.payload.step)),
      listen<{ ok: boolean; result?: SourceResult; error?: string }>("event/source_done", (e) => {
        setSourceBusy(false);
        setSourceStep("");
        const p = e.payload;
        if (p.ok && p.result) setSourceResult(p.result);
        else toast("error", p.error ?? "PKGBUILD oluşturulamadı");
      }),
    ];
    return () => {
      void Promise.all(unsubs).then((fns) => fns.forEach((f) => f()));
    };
  }, [toast, startNext]);

  const addPaths = useCallback(
    (paths: string[]) => {
      const fresh = filterAcceptedPaths(paths).filter(
        (p) => !queueRef.current.some((q) => q.id === p),
      );
      if (!fresh.length) return;
      setQueue((prev) => [
        ...prev,
        ...fresh.map((p) => ({
          id: p,
          name: p.split("/").pop() ?? p,
          status: "pending" as const,
        })),
      ]);
      // If idle, begin processing immediately.
      setTimeout(() => void startNext(), 0);
    },
    [startNext],
  );

  // Native drag-drop (Tauri emits real filesystem paths).
  useEffect(() => {
    const unsubs = [
      listen<{ paths: string[] }>("tauri://drag-drop", (e) => {
        setDragging(false);
        addPaths(e.payload.paths);
      }),
      listen("tauri://drag-enter", () => setDragging(true)),
      listen("tauri://drag-leave", () => setDragging(false)),
    ];
    return () => {
      void Promise.all(unsubs).then((fns) => fns.forEach((f) => f()));
    };
  }, [addPaths]);

  const handleCancel = async () => {
    try {
      await call("pipeline.cancel");
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleApprove = async () => {
    setReport(null);
    try {
      await call("pipeline.approve");
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleDismiss = async () => {
    setReport(null);
    try {
      await call("pipeline.dismiss", { message: "" });
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const removeItem = (id: string) =>
    setQueue((prev) => prev.filter((q) => q.id !== id));

  // --- post-conversion actions ---
  const handleOciExport = async () => {
    if (!outputPkg) return;
    try {
      await call("export.oci", { pkg_path: outputPkg });
      toast("info", "OCI imajı oluşturuluyor — Dışa Aktar sekmesinden takip edin");
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleShowGraph = async () => {
    if (!outputPkg) return;
    setGraphLoading(true);
    setGraph(null);
    try {
      await call("graph.build", { pkg_path: outputPkg });
    } catch (e) {
      setGraphLoading(false);
      toast("error", (e as Error).message);
    }
  };

  // --- from-source wizard ---
  const handleGenerate = async () => {
    if (!repoUrl.trim()) {
      toast("error", "Bir depo URL'si girin");
      return;
    }
    setSourceBusy(true);
    setSourceResult(null);
    setSourceStep("başlatılıyor");
    try {
      await call("source.generate", { repo_url: repoUrl });
    } catch (e) {
      setSourceBusy(false);
      setSourceStep("");
      toast("error", (e as Error).message);
    }
  };

  // --- batch queue (B6) ---
  const loadBatch = useCallback(async () => {
    try {
      const res = await call<BatchItem[]>("queue.list");
      setBatch(res);
    } catch (e) {
      toast("error", (e as Error).message);
    }
  }, [toast]);

  useEffect(() => {
    if (tab === "batch") void loadBatch();
  }, [tab, loadBatch]);

  // batch finished event
  useEffect(() => {
    let un: (() => void) | undefined;
    void listen("event/queue_done", () => {
      setBatchRunning(false);
      void loadBatch();
    }).then((u) => { un = u; });
    return () => { if (un) un(); };
  }, [loadBatch]);

  const handleBatchAdd = async (paths: string[]) => {
    if (!paths.length) return;
    try {
      await call("queue.add", { paths });
      void loadBatch();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleBatchStart = async () => {
    const p = parseInt(parallel, 10) || 1;
    setBatchRunning(true);
    try {
      const res = await call<{ started: boolean; reason?: string }>(
        "queue.start",
        { parallel: batchInstall ? 1 : p, install: batchInstall },
      );
      if (!res.started) {
        setBatchRunning(false);
        toast("info", res.reason === "no pending items" ? "Bekleyen öğe yok" : "Zaten çalışıyor");
      }
    } catch (e) {
      setBatchRunning(false);
      toast("error", (e as Error).message);
    }
  };

  const handleBatchPriority = async (id: string, delta: number) => {
    const item = batch.find((b) => b.id === id);
    if (!item) return;
    try {
      await call("queue.priority", { id, priority: item.priority + delta });
      void loadBatch();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleBatchRemove = async (id: string) => {
    try {
      await call("queue.remove", { id });
      void loadBatch();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleBatchClear = async () => {
    try {
      await call("queue.clear", {});
      void loadBatch();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const filteredBatch = batchFilter
    ? batch.filter((b) => b.name.toLowerCase().includes(batchFilter.toLowerCase()))
    : batch;

  const overall = report?.overall ?? "pass";
  const needsDecision = report !== null;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-5">
      {/* tab switcher */}
      <div className="flex gap-1 border-b border-[var(--border-subtle)]">
        <button
          onClick={() => setTab("convert")}
          className={cn(
            "flex items-center gap-1.5 rounded-t-md px-3 py-2 text-sm font-medium transition-colors",
            tab === "convert"
              ? "border-b-2 border-[var(--brand-blue)] text-[var(--brand-blue)]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
          )}
        >
          <Play size={15} /> Dönüştür
        </button>
        <button
          onClick={() => setTab("fromsource")}
          className={cn(
            "flex items-center gap-1.5 rounded-t-md px-3 py-2 text-sm font-medium transition-colors",
            tab === "fromsource"
              ? "border-b-2 border-[var(--brand-blue)] text-[var(--brand-blue)]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
          )}
        >
          <Code2 size={15} /> Kaynaktan
        </button>
        <button
          onClick={() => setTab("batch")}
          className={cn(
            "flex items-center gap-1.5 rounded-t-md px-3 py-2 text-sm font-medium transition-colors",
            tab === "batch"
              ? "border-b-2 border-[var(--brand-blue)] text-[var(--brand-blue)]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
          )}
        >
          <ListChecks size={15} /> Toplu
        </button>
      </div>

      {tab === "convert" && (
        <>
          <DropZone onPaths={addPaths} dragging={dragging} disabled={running} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Dönüştürme</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <StepIndicator statuses={statuses} />
                <div className="flex items-center gap-3">
                  <ProgressBar value={progress} gradient className="flex-1" />
                  <span className="w-10 text-right text-xs text-[var(--text-secondary)]">
                    {progress}%
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => void startNext()}
                    disabled={running || !queue.some((q) => q.status === "pending")}
                  >
                    <Play size={14} /> Başlat
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => void handleCancel()} disabled={!running}>
                    <Square size={14} /> İptal
                  </Button>
                  {running && <Badge tone="info">çalışıyor…</Badge>}
                </div>

                {/* post-conversion actions */}
                {outputPkg && !running && (
                  <div className="flex flex-wrap items-center gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
                    <span className="max-w-[260px] truncate text-xs font-mono text-[var(--text-secondary)]">
                      {outputPkg.split("/").pop()}
                    </span>
                    <Button variant="secondary" size="sm" onClick={() => void handleOciExport()}>
                      <Container size={14} /> OCI olarak dışa aktar
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => void handleShowGraph()} disabled={graphLoading}>
                      {graphLoading ? <Loader2 size={14} className="animate-spin" /> : <Network size={14} />}
                      Bağımlılık grafiği
                    </Button>
                  </div>
                )}

                {graph && <DepGraph data={graph} />}

                <LogViewer lines={logs} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Kuyruk ({queue.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <QueueList items={queue} onRemove={removeItem} />
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {tab === "fromsource" && (
        <Card>
          <CardHeader>
            <CardTitle>Kaynaktan PKGBUILD Sihirbazı</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-[var(--text-muted)]">
              Bir Git deposu URL'si girin; PkgForge projeyi klonlar, build sistemini tespit eder
              ve bir PKGBUILD üretir.
            </p>
            <div className="flex items-center gap-2">
              <Input
                placeholder="https://github.com/user/repo.git"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="h-9 flex-1"
              />
              <Button onClick={() => void handleGenerate()} disabled={sourceBusy}>
                {sourceBusy ? <Loader2 size={15} className="animate-spin" /> : <Code2 size={15} />}
                Oluştur
              </Button>
            </div>
            {sourceBusy && (
              <Badge tone="info">
                {sourceStep === "clone" ? "Depo klonlanıyor…" : sourceStep === "detect" ? "Build sistemi tespit ediliyor…" : sourceStep === "generate" ? "PKGBUILD üretiliyor…" : "Çalışıyor…"}
              </Badge>
            )}
            {sourceResult && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge tone="success">Build sistemi: {sourceResult.build_system}</Badge>
                  <span className="text-xs text-[var(--text-muted)]">{sourceResult.proj_name}</span>
                </div>
                <p className="truncate text-xs font-mono text-[var(--text-secondary)]">{sourceResult.pkgbuild_path}</p>
                <pre
                  className="max-h-64 overflow-y-auto rounded-md border border-[var(--border-subtle)] bg-[var(--bg-base)] p-3 text-xs"
                  style={{ fontFamily: "var(--font-mono)" }}
                >
                  {sourceResult.pkgbuild_content}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "batch" && (
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Toplu Dönüştürme</CardTitle>
            <div className="flex items-center gap-2">
              <Input
                placeholder="Filtrele…"
                value={batchFilter}
                onChange={(e) => setBatchFilter(e.target.value)}
                className="h-8 w-40"
              />
              <Button variant="secondary" size="sm" onClick={() => void loadBatch()}>
                Yenile
              </Button>
              <Button variant="danger" size="sm" onClick={() => void handleBatchClear()} disabled={batchRunning}>
                <Trash2 size={13} /> Temizle
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <DropZone onPaths={(p) => void handleBatchAdd(p)} dragging={false} disabled={batchRunning} />

            <div className="flex items-center gap-2">
              <Button onClick={() => void handleBatchStart()} disabled={batchRunning || !batch.some((b) => b.status === "pending")}>
                {batchRunning ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                Toplu Başlat
              </Button>
              <span className="text-xs text-[var(--text-muted)]">Paralel:</span>
              <Input
                type="number"
                min={1}
                max={4}
                value={parallel}
                onChange={(e) => setParallel(e.target.value)}
                className="h-8 w-16"
              />
              <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
                <input
                  type="checkbox"
                  checked={batchInstall}
                  onChange={(e) => setBatchInstall(e.target.checked)}
                  className="h-3.5 w-3.5 accent-[var(--brand-blue)]"
                />
                Kur (seri)
              </label>
              {batchRunning && <Badge tone="info">çalışıyor…</Badge>}
            </div>

            {filteredBatch.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">Kuyruk boş. Paket dosyalarını yukarı sürükleyin.</p>
            ) : (
              <div className="space-y-1">
                {filteredBatch.map((b) => (
                  <div key={b.id} className="flex items-center justify-between rounded-md bg-[var(--bg-elevated)] px-3 py-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="truncate font-medium">{b.name}</span>
                        <Badge tone={b.status === "done" ? "success" : b.status === "error" ? "danger" : b.status === "running" ? "info" : "neutral"}>
                          {b.status}
                        </Badge>
                        <span className="text-xs text-[var(--text-muted)]">öncelik {b.priority}</span>
                      </div>
                      {b.message && <p className="truncate text-xs text-[var(--text-muted)]">{b.message}</p>}
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <button aria-label={`öncelik artır ${b.name}`} title="Önceliği artır" onClick={() => void handleBatchPriority(b.id, 1)} className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--brand-blue)]">
                        <ArrowUp size={14} />
                      </button>
                      <button aria-label={`öncelik azalt ${b.name}`} title="Önceliği azalt" onClick={() => void handleBatchPriority(b.id, -1)} className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--brand-blue)]">
                        <ArrowDown size={14} />
                      </button>
                      <button aria-label={`kaldır ${b.name}`} title="Kaldır" onClick={() => void handleBatchRemove(b.id)} disabled={b.status === "running"} className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--danger)]">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Compatibility decision dialog (WARNING / ERROR) */}
      <Dialog
        open={needsDecision}
        onClose={() => void handleDismiss()}
        title={`Uyumluluk Raporu — Sınıf ${report?.grade ?? "?"}`}
      >
        {report && (
          <div className="flex flex-col gap-3">
            <Badge tone={overall === "error" ? "danger" : overall === "warning" ? "warning" : "success"}>
              {overall === "error" ? "Engelleyici hatalar var" : overall === "warning" ? "Uyarılar var" : "Temiz"}
            </Badge>
            <ul className="max-h-56 space-y-2 overflow-y-auto text-sm">
              {report.checks.map((c, i) => (
                <li key={i} className="flex items-start gap-2">
                  <Badge
                    tone={c.severity === "error" ? "danger" : c.severity === "warning" ? "warning" : "success"}
                  >
                    {c.severity}
                  </Badge>
                  <span className="text-[var(--text-primary)]">
                    <strong>{c.name}:</strong> {c.message}
                  </span>
                </li>
              ))}
            </ul>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => void handleDismiss()}>
                Kapat
              </Button>
              <Button
                variant={overall === "error" ? "danger" : "primary"}
                onClick={() => void handleApprove()}
              >
                Yine de Kur
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
