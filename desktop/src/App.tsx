import { useEffect, useState } from "react";
import { call } from "./lib/rpc";
import type { AppVersion } from "./lib/types";

/**
 * Faz 0 shell: proves the Tauri -> Rust relay -> Python sidecar round trip.
 * Full page routing (Convert/Installed/Settings) lands in Tasks 5-7.
 */
export default function App() {
  const [version, setVersion] = useState<AppVersion | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    call<AppVersion>("app.version")
      .then(setVersion)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="rounded-[var(--radius-card)] bg-[var(--bg-surface)] p-8 shadow-[var(--shadow-md)]">
        <h1
          className="bg-[var(--brand-gradient)] bg-clip-text text-2xl font-bold text-transparent"
        >
          PkgForge
        </h1>
        {version && (
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            {version.name} v{version.version} — sidecar bağlantısı aktif
          </p>
        )}
        {error && (
          <p className="mt-2 text-sm text-[var(--danger)]">
            Sidecar hatası: {error}
          </p>
        )}
        {!version && !error && (
          <p className="mt-2 text-sm text-[var(--text-muted)]">Bağlanıyor…</p>
        )}
      </div>
    </div>
  );
}
