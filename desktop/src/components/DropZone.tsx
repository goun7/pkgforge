import { useRef } from "react";
import { PackageOpen } from "lucide-react";
import { cn } from "../lib/utils";
import { useLang, getLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

/** Known package extensions (used by the native dialog hint). */
export const ACCEPTED_EXTENSIONS = [
  ".deb", ".rpm", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2",
  ".tbz2", ".tar.zst", ".tar", ".zip", ".appimage", ".pkg.tar.zst",
  ".pkg.tar.xz", ".pkg.tar.gz", ".flatpakref",
];

/** Universal intake: forward every non-empty path to the backend, where
 * core.intake.classify() decides the route (and asks the user when a
 * tarball is ambiguous). The frontend no longer gates by extension. */
export function filterAcceptedPaths(paths: string[]): string[] {
  return paths.filter((p) => typeof p === "string" && p.length > 0);
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
  const t = tFor(getLang());
  const selected = await open({
    multiple: true,
    title: t("dropBrowseTitle"),
    filters: [
      {
        name: t("dropFilterPackages"),
        extensions: [
          "deb", "rpm", "tar.gz", "tgz", "tar.xz", "txz", "tar.bz2", "tbz2",
          "tar.zst", "tar", "zip", "AppImage", "pkg.tar.zst", "flatpakref",
        ],
      },
    ],
  });
  if (!selected) return [];
  return Array.isArray(selected) ? selected : [selected];
}

/** Gorsel ipucu: kabul edilen ana tur rozetleri (3.6). */
const TYPE_HINTS = [".deb", ".rpm", ".tar.gz", ".zip", "AppImage", ".pkg.tar.zst"];

export function DropZone({
  onPaths,
  dragging = false,
  disabled = false,
  hint,
  browse = defaultBrowse,
}: DropZoneProps) {
  const busy = useRef(false);
  const t = tFor(useLang());

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
      aria-label={t("dropzoneAria")}
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
          {t("dropzoneTitle")}
        </p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          {hint ?? t("dropzoneHint")}
        </p>
      </div>
      {/* Kabul edilen tur rozetleri */}
      <div className="mt-1 flex flex-wrap items-center justify-center gap-1.5">
        {TYPE_HINTS.map((ty) => (
          <span
            key={ty}
            className="rounded-full border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]"
          >
            {ty}
          </span>
        ))}
      </div>
    </div>
  );
}
