import { useCallback, useRef, useState, type DragEvent } from "react";
import { PackageOpen } from "lucide-react";
import { cn } from "../lib/utils";

export interface DropZoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
  hint?: string;
}

const ACCEPTED = [".deb", ".rpm"];

function filterAccepted(files: File[]): File[] {
  return files.filter((f) =>
    ACCEPTED.some((ext) => f.name.toLowerCase().endsWith(ext)),
  );
}

export function DropZone({ onFiles, disabled = false, hint }: DropZoneProps) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const files = filterAccepted(Array.from(e.dataTransfer.files));
      if (files.length) onFiles(files);
    },
    [onFiles, disabled],
  );

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="drop-zone"
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) inputRef.current?.click();
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-[var(--radius-card)] border-2 border-dashed p-10 text-center transition-all",
        dragging
          ? "border-[var(--brand-ember)] bg-[var(--brand-ember)]/5 shadow-[var(--glow-brand)]"
          : "border-[var(--border-strong)] bg-[var(--bg-surface)] hover:border-[var(--brand-blue)]",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <div
        className={cn(
          "flex h-14 w-14 items-center justify-center rounded-2xl transition-colors",
          dragging ? "bg-[var(--brand-ember)]/15" : "bg-[var(--bg-elevated)]",
        )}
      >
        <PackageOpen
          size={26}
          className={dragging ? "text-[var(--brand-ember)]" : "text-[var(--brand-blue)]"}
        />
      </div>
      <div>
        <p className="text-sm font-semibold text-[var(--text-primary)]">
          .deb / .rpm dosyalarını buraya bırakın
        </p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          {hint ?? "veya seçmek için tıklayın"}
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".deb,.rpm"
        className="hidden"
        onChange={(e) => {
          const files = filterAccepted(Array.from(e.target.files ?? []));
          if (files.length) onFiles(files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
