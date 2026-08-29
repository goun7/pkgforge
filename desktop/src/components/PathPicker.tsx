import { useRef } from "react";
import { FolderOpen, FileSearch } from "lucide-react";
import { cn } from "../lib/utils";
import { Input } from "./ui/Input";
import { Button } from "./ui/Button";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

/** Yerel dialog icin paket dosyasi filtresi (donusturulmus Arch paketleri + kaynaklar). */
export const PKG_DIALOG_FILTERS = [
  {
    name: "Paketler",
    extensions: [
      "pkg.tar.zst", "pkg.tar.xz", "pkg.tar.gz", "deb", "rpm",
      "tar.gz", "tgz", "tar.xz", "txz", "tar.bz2", "tbz2", "tar.zst",
      "tar", "zip", "AppImage", "flatpakref",
    ],
  },
];

export interface PathPickerProps {
  value: string;
  onChange: (path: string) => void;
  placeholder?: string;
  /** "file" dosya secici, "dir" klasor secici acar. */
  mode?: "file" | "dir";
  multiple?: boolean;
  filters?: { name: string; extensions: string[] }[];
  title?: string;
  className?: string;
  disabled?: boolean;
  /** Test icin enjekte edilebilir secici (varsayilan: Tauri dialog). */
  browse?: () => Promise<string[]>;
}

async function defaultBrowse(
  mode: "file" | "dir",
  multiple: boolean,
  filters?: { name: string; extensions: string[] }[],
  title?: string,
): Promise<string[]> {
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({
    directory: mode === "dir",
    multiple,
    filters,
    title,
  });
  if (!selected) return [];
  return Array.isArray(selected) ? selected : [selected];
}

/** Metin kutusu + yerel dosya/klasor secici dugmesi. Yol elle de yazilabilir,
 *  "Sec" dugmesiyle Tauri'nin yerel dialogu da acilabilir. */
export function PathPicker({
  value,
  onChange,
  placeholder,
  mode = "file",
  multiple = false,
  filters,
  title,
  className,
  disabled,
  browse,
}: PathPickerProps) {
  const busy = useRef(false);
  const t = tFor(useLang());

  const handleBrowse = async () => {
    if (disabled || busy.current) return;
    busy.current = true;
    try {
      const fn = browse ?? (() => defaultBrowse(mode, multiple, filters, title));
      const paths = (await fn()).filter((p) => typeof p === "string" && p.length > 0);
      if (!paths.length) return;
      onChange(multiple ? paths.join(",") : paths[0]);
    } catch {
      // Dialog acilamadi/kullanici iptal etti — sessizce gec; busy kilidi
      // finally'de duserek tekrar denenebilir hale gelir.
    } finally {
      busy.current = false;
    }
  };

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="h-9 flex-1 font-mono text-xs"
      />
      <Button
        variant="secondary"
        size="sm"
        onClick={() => void handleBrowse()}
        disabled={disabled}
        aria-label={t("pathBrowseAria")}
        type="button"
      >
        {mode === "dir" ? <FolderOpen size={14} /> : <FileSearch size={14} />}
        {t("pathSelect")}
      </Button>
    </div>
  );
}
