import { useEffect, useRef } from "react";
import { cn } from "../lib/utils";

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

export interface LogViewerProps {
  lines: LogLine[];
  className?: string;
  maxHeight?: string;
}

/** Color-coded, auto-scrolling log panel (mono font). */
export function LogViewer({ lines, className, maxHeight = "280px" }: LogViewerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [lines.length]);

  return (
    <div
      role="log"
      aria-live="polite"
      className={cn(
        "overflow-y-auto rounded-[var(--radius-input)] bg-[var(--bg-base)] border border-[var(--border-subtle)] p-3 text-xs leading-relaxed",
        className,
      )}
      style={{ maxHeight, fontFamily: "var(--font-mono)" }}
    >
      {lines.length === 0 && (
        <p className="text-[var(--text-muted)]">Henüz log yok…</p>
      )}
      {lines.map((line, i) => (
        <div key={i} className={cn("whitespace-pre-wrap", levelColors[line.level] ?? levelColors.info)}>
          {line.message}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
