import { useCallback, useEffect, useRef, useState } from "react";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { Play, Square, Container, Network, Code2, Loader2, ListChecks, ArrowUp, ArrowDown, Trash2, FolderOpen, Copy, Download, CheckCircle2, PackageOpen, X } from "lucide-react";
import { call } from "../lib/rpc";
import { tFor, type I18nKey } from "../lib/i18n";
import { useLang } from "../lib/lang";
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
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
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

/** Adim anahtarlarindan i18n etiket anahtarlari. */
const STEP_LABEL_KEYS: Record<string, I18nKey> = {
  security: "stepSecurity",
  malware: "stepMalware",
  analysis: "stepAnalysis",
  conversion: "stepConversion",
  compatibility: "stepCompatibility",
  install: "stepInstall",
};

/** Gecen sureyi (saniye) "Xdk Ysn" biciminde gosterir. */
function fmtElapsed(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m} dk ${sec} sn` : `${sec} sn`;
}

type ConvertTab = "convert" | "fromsource" | "batch";

export function Convert() {
  const { toast } = useToast();
  const [tab, setTab] = useState<ConvertTab>("convert");
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [statuses, setStatuses] = useState<Record<string, StepStatus>>({});
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [running, setRunning] = useState(false);
  const [report, setReport] = useState<CompatibilityReport | null>(null);
  const [dragging, setDragging] = useState(false);
  const [outputPkg, setOutputPkg] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [installing, setInstalling] = useState(false);
  const startRef = useRef<number>(0);

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
  // F5.20: live language — follows the shared store set in Settings.
  const lang = useLang();
  const tBatch = tFor(lang);
  const t = tFor(lang);
  const [batchFilter, setBatchFilter] = useState("");

  // Refs so event callbacks always see fresh state without re-subscribing.
  const queueRef = useRef(queue);
  queueRef.current = queue;
  const runningRef = useRef(running);
  runningRef.current = running;

  // Donusum surerken gecen sureyi sayar; bitince sifirlanir.
  useEffect(() => {
    if (!running) {
      setElapsed(0);
      return;
    }
    startRef.current = Date.now();
    const iv = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(iv);
  }, [running]);

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
        toast(success ? "success" : "error", message || (success ? t("convDone") : t("convFailed")));
        // Kick off the next queued item on the next tick.
        setTimeout(() => void startNext(), 0);
      }),
      listen<{ ok: boolean; result?: DepGraphData; error?: string }>("event/graph_done", (e) => {
        setGraphLoading(false);
        const p = e.payload;
        if (p.ok && p.result) setGraph(p.result);
        else toast("error", p.error ?? t("convGraphFail"));
      }),
      listen<{ ok: boolean; result?: { ok: boolean; message: string }; error?: string }>("event/install_done", (e) => {
        setInstalling(false);
        const p = e.payload;
        if (p.ok && p.result) {
          if (p.result.ok) toast("success", p.result.message);
          else toast("error", p.result.message);
        } else {
          toast("error", p.error ?? t("convInstallFail"));
        }
      }),
      listen<{ step: string }>("event/source_progress", (e) => setSourceStep(e.payload.step)),
      listen<{ ok: boolean; result?: SourceResult; error?: string }>("event/source_done", (e) => {
        setSourceBusy(false);
        setSourceStep("");
        const p = e.payload;
        if (p.ok && p.result) setSourceResult(p.result);
        else toast("error", p.error ?? t("convPkgbuildFail"));
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
      toast("info", t("convOciStarted"));
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

  const handleOpenFolder = async () => {
    if (!outputPkg) return;
    try {
      await call("system.open_path", { path: outputPkg });
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleCopyPath = async () => {
    if (!outputPkg) return;
    try {
      await navigator.clipboard.writeText(outputPkg);
      toast("success", t("copiedPath"));
    } catch {
      toast("error", t("copyFailed"));
    }
  };

  const handleInstall = async () => {
    if (!outputPkg) return;
    setInstalling(true);
    try {
      await call("system.install_pkg", { pkg_path: outputPkg });
    } catch (e) {
      setInstalling(false);
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
    setSourceStep("starting");
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
        toast("info", res.reason === "no pending items" ? t("queueNoPending") : t("queueAlreadyRunning"));
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

  // Faz 10 (2.1): calisan bir batch ogisini iptal et (queue.cancel).
  const handleBatchCancel = async (id: string) => {
    try {
      await call("queue.cancel", { item_id: id });
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
  // Ilerleme hissi: uzun suren donusum adimi indeterminate + gecen sure ile akar
  const isConverting = statuses["conversion"] === "running";
  // Faz 8 (2.1): ilerleme yüzdesinden kalan sure tahmini (ETA).
  const eta =
    isConverting && progress > 0 && progress < 100 && elapsed > 0
      ? Math.round((elapsed * (100 - progress)) / progress)
      : null;
  const activeStepKey = PIPELINE_STEPS.find((s) => statuses[s] === "running");
  // Adim gostergesine yerellestirilmis etiketler (ham anahtar yerine).
  const stepLabels: Record<string, string> = {};
  for (const [key, labelKey] of Object.entries(STEP_LABEL_KEYS)) stepLabels[key] = t(labelKey);

  return (
    <div className="relative flex h-full flex-col gap-4 overflow-y-auto p-5">
      {/* Faz 9 (5.6): sayfanin tamami drop hedefi — surukleme sirasinda tam ekran geri bildirim. */}
      {dragging && (
        <div className="pointer-events-none absolute inset-2 z-40 flex items-center justify-center rounded-2xl border-2 border-dashed border-[var(--brand-blue)] bg-[var(--brand-blue)]/10 backdrop-blur-[1px]">
          <div className="flex flex-col items-center gap-2 rounded-xl bg-[var(--bg-surface)] px-6 py-4 shadow-[var(--shadow-lg)]">
            <PackageOpen size={28} className="text-[var(--brand-blue)]" />
            <span className="text-sm font-medium text-[var(--text-primary)]">{t("dropOverlayHint")}</span>
          </div>
        </div>
      )}
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
          <Play size={15} /> {t("tabConvert")}
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
          <Code2 size={15} /> {t("tabSource")}
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
          <ListChecks size={15} /> {t("tabBatch")}
        </button>
      </div>

      {tab === "convert" && (
        <>
          <DropZone onPaths={addPaths} dragging={dragging} disabled={running} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>{t("convertTitle")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <StepIndicator statuses={statuses} labels={stepLabels} />
                <div className="flex items-center gap-3">
                  <ProgressBar value={progress} gradient indeterminate={isConverting && progress === 0} className="flex-1" />
                  <span className="w-12 text-right text-xs text-[var(--text-secondary)]">
                    {isConverting && progress === 0 ? "…" : `${progress}%`}
                  </span>
                </div>
                {running && (
                  <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                    <span>{activeStepKey && STEP_LABEL_KEYS[activeStepKey] ? t(STEP_LABEL_KEYS[activeStepKey]) : t("convertPreparing")}</span>
                    <span>
                      {t("convertElapsed")}: {fmtElapsed(elapsed)}
                      {eta !== null && ` · ${t("convEta")} ~${fmtElapsed(eta)}`}
                    </span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => void startNext()}
                    disabled={running || !queue.some((q) => q.status === "pending")}
                  >
                    <Play size={14} /> {t("commonStart")}
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => setConfirmCancel(true)} disabled={!running}>
                    <Square size={14} /> {t("commonCancel")}
                  </Button>
                  {running && <Badge tone="info">{t("commonRunning")}</Badge>}
                </div>

                {/* Kalici sonuc bandi: yol + ac/kopyala/kur + ileri islemler */}
                {outputPkg && !running && (
                  <div className="rounded-lg border border-[var(--success)]/40 bg-[var(--success)]/10 p-3">
                    <div className="mb-2 flex items-center gap-2">
                      <CheckCircle2 size={17} className="shrink-0 text-[var(--success)]" />
                      <span className="text-sm font-semibold text-[var(--text-primary)]">{t("convertDone")}</span>
                    </div>
                    <p className="mb-3 break-all font-mono text-xs text-[var(--text-secondary)]">{outputPkg}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button variant="primary" size="sm" onClick={() => void handleInstall()} disabled={installing}>
                        {installing ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                        {t("commonInstall")}
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => void handleOpenFolder()}>
                        <FolderOpen size={14} /> {t("commonOpenFolder")}
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => void handleCopyPath()}>
                        <Copy size={14} /> {t("commonCopyPath")}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => void handleOciExport()}>
                        <Container size={14} /> {t("convertOci")}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => void handleShowGraph()} disabled={graphLoading}>
                        {graphLoading ? <Loader2 size={14} className="animate-spin" /> : <Network size={14} />}
                        {t("convertGraph")}
                      </Button>
                    </div>
                  </div>
                )}

                {graph && <DepGraph data={graph} />}

                <LogViewer lines={logs} onClear={() => setLogs([])} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("convertQueue")} ({queue.length})</CardTitle>
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
            <CardTitle>{t("convSourceWizard")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-[var(--text-muted)]">
              {t("convSourceDesc")}
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
                {t("convGenerate")}
              </Button>
            </div>
            {sourceBusy && (
              <Badge tone="info">
                {sourceStep === "clone" ? t("convCloning") : sourceStep === "detect" ? t("convDetecting") : sourceStep === "generate" ? t("convGenerating") : t("convWorking")}
              </Badge>
            )}
            {sourceResult && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge tone="success">{t("convBuildSystem")} {sourceResult.build_system}</Badge>
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
            <CardTitle>{tBatch("batchTitle")}</CardTitle>
            <div className="flex items-center gap-2">
              <Input
                placeholder={tBatch("batchFilter")}
                value={batchFilter}
                onChange={(e) => setBatchFilter(e.target.value)}
                className="h-8 w-40"
              />
              <Button variant="secondary" size="sm" onClick={() => void loadBatch()}>
                {tBatch("batchRefresh")}
              </Button>
              <Button variant="danger" size="sm" onClick={() => void handleBatchClear()} disabled={batchRunning}>
                <Trash2 size={13} /> {tBatch("batchClear")}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <DropZone onPaths={(p) => void handleBatchAdd(p)} dragging={false} disabled={batchRunning} />

            <div className="flex items-center gap-2">
              <Button onClick={() => void handleBatchStart()} disabled={batchRunning || !batch.some((b) => b.status === "pending")}>
                {batchRunning ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                {tBatch("batchStart")}
              </Button>
              <span className="text-xs text-[var(--text-muted)]">{tBatch("batchParallel")}</span>
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
                {tBatch("batchInstallSerial")}
              </label>
              {batchRunning && <Badge tone="info">{tBatch("batchRunning")}</Badge>}
            </div>

            {filteredBatch.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">{tBatch("batchEmpty")}</p>
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
                        <span className="text-xs text-[var(--text-muted)]">{tBatch("batchPriority")} {b.priority}</span>
                      </div>
                      {b.message && <p className="truncate text-xs text-[var(--text-muted)]">{b.message}</p>}
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <button aria-label={`${t("convPriorityUp")} ${b.name}`} title={t("convPriorityUp")} onClick={() => void handleBatchPriority(b.id, 1)} className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--brand-blue)]">
                        <ArrowUp size={14} />
                      </button>
                      <button aria-label={`${t("convPriorityDown")} ${b.name}`} title={t("convPriorityDown")} onClick={() => void handleBatchPriority(b.id, -1)} className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--brand-blue)]">
                        <ArrowDown size={14} />
                      </button>
                      {b.status === "running" && (
                        <button aria-label={`${t("batchCancel")} ${b.name}`} title={t("batchCancel")} onClick={() => void handleBatchCancel(b.id)} className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--warning)]">
                          <X size={14} />
                        </button>
                      )}
                      <button aria-label={`${t("convRemoveItem")} ${b.name}`} title={t("commonRemove")} onClick={() => void handleBatchRemove(b.id)} disabled={b.status === "running"} className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--danger)]">
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
        title={`${t("convCompatReport")} ${report?.grade ?? "?"}`}
      >
        {report && (
          <div className="flex flex-col gap-3">
            <Badge tone={overall === "error" ? "danger" : overall === "warning" ? "warning" : "success"}>
              {overall === "error" ? t("convBlocking") : overall === "warning" ? t("convWarnings") : t("convCleanStatus")}
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
                {t("convClose")}
              </Button>
              <Button
                variant={overall === "error" ? "danger" : "primary"}
                onClick={() => void handleApprove()}
              >
                {t("convInstallAnyway")}
              </Button>
            </div>
          </div>
        )}
      </Dialog>

      {/* Faz 8 (2.6): iptal onayi. */}
      <ConfirmDialog
        open={confirmCancel}
        title={t("confirmCancelTitle")}
        message={t("confirmCancelMsg")}
        confirmLabel={t("confirmConfirm")}
        cancelLabel={t("confirmCancel")}
        danger
        onConfirm={() => {
          setConfirmCancel(false);
          void handleCancel();
        }}
        onCancel={() => setConfirmCancel(false)}
      />
    </div>
  );
}
