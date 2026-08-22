import { useRef } from "react";
import { PackageOpen } from "lucide-react";
import { cn } from "../lib/utils";

export const ACCEPTED_EXTENSIONS = [".deb", ".rpm"];

/** Pure filter: keep only paths ending in an accepted extension. */
export function filterAcceptedPaths(paths: string[]): string[] {
  return paths.filter((p) => {
    const lower = p.toLowerCase();
    return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
  });
}

export interface DropZoneProps {
  /** Called with real filesystem paths (from native dialog or native drag-drop). */
  onPaths: (paths: string[]) => void;
  /** Whether a native drag is currently hovering (set by the page from Tauri events). */
  dragging?: boolean;
  disabled?: boolean;
  hint?: string;
  /** Opens the native file dialog; injected so tests can stub it. */
  browse?: () => Promise<string[]>;
}

async function defaultBrowse(): Promise<string[]> {
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({
    multiple: true,
    title: "Paket seç",
    filters: [{ name: "Paketler", extensions: ["deb", "rpm"] }],
  });
  if (!selected) return [];
  return Array.isArray(selected) ? selected : [selected];
}

export function DropZone({
  onPaths,
  dragging = false,
  disabled = false,
  hint,
  browse = defaultBrowse,
}: DropZoneProps) {
  const busy = useRef(false);

  const handleBrowse = async () => {
    if (disabled || busy.current) return;
    busy.current = true;
    try {
      const paths = filterAcceptedPaths(await browse());
      if (paths.length) onPaths(paths);
    } finally {
      busy.current = false;
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="drop-zone"
      onClick={handleBrowse}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") handleBrowse();
      }}
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
    </div>
  );
}
