// Tur-55 C9: Package Manifest contract (TypeScript mirror).
// Python `PackageManifest` dataclass'ına karşılık gelen TS arayüzü.
// JSON Schema: ../../shared/contracts/package_manifest.schema.json
export interface PackageManifest {
  name: string;
  version: string;
  arch: "amd64" | "arm64" | "i386" | "any";
  size_bytes: number;
  sha256: string; // 64-hex
  dependencies: string[];
  signed: boolean;
  signature_path?: string;
}

export function isPackageManifest(obj: unknown): obj is PackageManifest {
  if (typeof obj !== "object" || obj === null) return false;
  const m = obj as Record<string, unknown>;
  return (
    typeof m.name === "string" &&
    typeof m.version === "string" &&
    typeof m.arch === "string" &&
    typeof m.size_bytes === "number" &&
    typeof m.sha256 === "string" &&
    Array.isArray(m.dependencies)
  );
}
