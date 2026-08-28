import { useEffect, useRef, useState } from "react";
import { Copy, Trash2, Download } from "lucide-react";
import { cn } from "../lib/utils";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

export interface LogLine {
  message: string;
  level: string; // info | warning | error | success
}

const levelColors: Record<string, string> = {
  info: "text-[var(--text-secondary)]",
  warning: "text-[var(--warning)]",
  error: "text-[var(--danger)]",
  success: "text-[var(--success)]",
};

/** Performans icin en fazla bu kadar satir DOM'da tutulur. */
const MAX_LINES = 1000;

export interface LogViewerProps {
  lines: LogLine[];
  className?: string;
  maxHeight?: string;
  /** Verilirse basinlikta bir "Temizle" butonu gorunur. */
  onClear?: () => void;
}

/** Renk kodlu, otomatik kayan log paneli. Kullanici yukari kaydirinca
 *  otomatik kaydirma duraklar; en alta inince yeniden etkinlesir. */
export function LogViewer({ lines, className, maxHeight = "280px", onClear }: LogViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [stick, setStick] = useState(true);
  const t = tFor(useLang());

  const visible = lines.length > MAX_LINES ? lines.slice(-MAX_LINES) : lines;

  useEffect(() => {
    if (stick && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [visible.length, stick]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    setStick(atBottom);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(visible.map((l) => l.message).join("\n"));
    } catch {
      // pano erisimi yoksa sessizce gec
    }
  };

  // Faz 9 (5.2): loglari .txt olarak indir (sorun raporlamak icin).
  const handleDownload = () => {
    const text = visible.map((l) => l.message).join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "pkgforge-log.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={className}>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          {stick ? "Log" : t("logPaused")}
        </span>
        <div className="flex gap-0.5">
          <button
            onClick={() => void handleCopy()}
            aria-label={t("logCopyAria")}
            title={t("logCopy")}
            className="rounded p-1 text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            <Copy size={12} />
          </button>
          <button
            onClick={handleDownload}
            aria-label={t("logDownloadAria")}
            title={t("logDownload")}
            className="rounded p-1 text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            <Download size={12} />
          </button>
          {onClear && (
            <button
              onClick={onClear}
              aria-label={t("logClearAria")}
              title={t("logClear")}
              className="rounded p-1 text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--danger)]"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </div>
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        className={cn(
          "overflow-y-auto rounded-[var(--radius-input)] bg-[var(--bg-base)] border border-[var(--border-subtle)] p-3 text-xs leading-relaxed",
        )}
        style={{ maxHeight, fontFamily: "var(--font-mono)" }}
      >
        {visible.length === 0 && (
          <p className="text-[var(--text-muted)]">{t("logEmpty")}</p>
        )}
        {visible.map((line, i) => (
          <div key={i} className={cn("whitespace-pre-wrap", levelColors[line.level] ?? levelColors.info)}>
            {line.message}
          </div>
        ))}
      </div>
    </div>
  );
}
