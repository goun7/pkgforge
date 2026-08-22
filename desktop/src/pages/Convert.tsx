import { useCallback, useEffect, useRef, useState } from "react";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { Play, Square } from "lucide-react";
import { call } from "../lib/rpc";
import type {
  StepChangedEvent,
  ProgressEvent,
  LogEvent,
  CompatibilityReadyEvent,
  FinishedEvent,
} from "../lib/types";
import { DropZone, filterAcceptedPaths } from "../components/DropZone";
import { StepIndicator, PIPELINE_STEPS, type StepStatus } from "../components/StepIndicator";
import { ProgressBar } from "../components/ui/ProgressBar";
import { LogViewer, type LogLine } from "../components/LogViewer";
import { QueueList, type QueueItem } from "../components/QueueList";
import { Button } from "../components/ui/Button";
import { Dialog } from "../components/ui/Dialog";
import { Badge } from "../components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { useToast } from "../components/ui/Toast";
import type { CompatibilityReport } from "../lib/types";

/** Map a pipeline step index (0-5) to the StepIndicator step name. */
function stepName(index: number): string {
  return PIPELINE_STEPS[index] ?? "unknown";
}

export function Convert() {
  const { toast } = useToast();
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [statuses, setStatuses] = useState<Record<string, StepStatus>>({});
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [running, setRunning] = useState(false);
  const [report, setReport] = useState<CompatibilityReport | null>(null);
  const [dragging, setDragging] = useState(false);

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
      listen<StepChangedEvent>("event.step_changed", (e) => {
        const name = stepName(e.payload.step);
        setStatuses((prev) => ({ ...prev, [name]: e.payload.status as StepStatus }));
      }),
      listen<ProgressEvent>("event.progress", (e) => setProgress(e.payload.value)),
      listen<LogEvent>("event.log", (e) =>
        setLogs((prev) => [...prev, { message: e.payload.message, level: e.payload.level }]),
      ),
      listen<CompatibilityReadyEvent>("event.compatibility_ready", (e) =>
        setReport(e.payload.report),
      ),
      listen<FinishedEvent>("event.finished", (e) => {
        const { success, message } = e.payload;
        setRunning(false);
        setReport(null);
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

  const overall = report?.overall ?? "pass";
  const needsDecision = report !== null;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-5">
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
