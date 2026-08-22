import { FileArchive, X } from "lucide-react";
import { cn } from "../lib/utils";
import { StatusPill, type PipelineStatus } from "./StatusPill";

export interface QueueItem {
  id: string;
  name: string;
  status: PipelineStatus;
  progress?: number;
}

export interface QueueListProps {
  items: QueueItem[];
  onRemove?: (id: string) => void;
  className?: string;
}

export function QueueList({ items, onRemove, className }: QueueListProps) {
  if (items.length === 0) {
    return (
      <p className={cn("py-6 text-center text-sm text-[var(--text-muted)]", className)}>
        Kuyruk boş
      </p>
    );
  }
  return (
    <ul className={cn("flex flex-col gap-2", className)}>
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-center gap-3 rounded-[var(--radius-input)] bg-[var(--bg-elevated)] px-3 py-2.5"
        >
          <FileArchive size={18} className="shrink-0 text-[var(--brand-blue)]" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-[var(--text-primary)]">
              {item.name}
            </p>
            {typeof item.progress === "number" && item.status === "running" && (
              <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-[var(--bg-base)]">
                <div
                  className="h-full rounded-full bg-[var(--brand-gradient)] transition-all"
                  style={{ width: `${item.progress}%` }}
                />
              </div>
            )}
          </div>
          <StatusPill status={item.status} />
          {onRemove && item.status === "pending" && (
            <button
              aria-label={`remove ${item.name}`}
              onClick={() => onRemove(item.id)}
              className="rounded-md p-1 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--danger)]"
            >
              <X size={14} />
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
