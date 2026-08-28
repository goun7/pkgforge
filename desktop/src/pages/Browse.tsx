import { useEffect, useState } from "react";
import { Globe, Search, Loader2, Hammer, Info, ThumbsUp } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { AurSearchResult, AurInfo } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Input } from "../components/ui/Input";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

export function Browse() {
  const { toast } = useToast();
  const lang = useLang();
  const t = tFor(lang);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AurSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [building, setBuilding] = useState("");
  const [buildStep, setBuildStep] = useState("");
  const [info, setInfo] = useState<AurInfo | null>(null);
  const [infoName, setInfoName] = useState("");

  useEffect(() => {
    const unsubs: (() => void)[] = [];
    void onEvent<{ ok: boolean; result?: AurSearchResult[]; error?: string }>(
      "event/aur_search_done",
      (p) => {
        setSearching(false);
        setSearched(true);
        if (p.ok && p.result) setResults(p.result);
        else toast("error", p.error ?? "Arama başarısız");
      },
    ).then((u) => unsubs.push(u));
    void onEvent<{ ok: boolean; result?: AurInfo; error?: string }>(
      "event/aur_info_done",
      (p) => {
        if (p.ok && p.result) setInfo(p.result);
        else toast("error", p.error ?? "Bilgi alınamadı");
      },
    ).then((u) => unsubs.push(u));
    void onEvent<{ name: string; step: string }>(
      "event/aur_build_progress",
      (p) => setBuildStep(p.step),
    ).then((u) => unsubs.push(u));
    void onEvent<{ ok: boolean; result?: { name: string; pkg_path: string; installed: boolean }; error?: string }>(
      "event/aur_build_done",
      (p) => {
        setBuilding("");
        setBuildStep("");
        if (p.ok && p.result) {
          toast("success", `${p.result.name} derlendi: ${p.result.pkg_path.split("/").pop()}`);
        } else {
          toast("error", p.error ?? "Derleme başarısız");
        }
      },
    ).then((u) => unsubs.push(u));
    return () => { unsubs.forEach((u) => u()); };
  }, [toast]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setResults([]);
    setSearched(false);
    try {
      await call("aur.search", { query, limit: 25 });
    } catch (e) {
      setSearching(false);
      toast("error", (e as Error).message);
    }
  };

  const handleInfo = async (name: string) => {
    setInfoName(name);
    setInfo(null);
    try {
      await call("aur.info", { name });
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleBuild = async (name: string) => {
    setBuilding(name);
    setBuildStep("başlatılıyor");
    try {
      await call("aur.build", { name });
    } catch (e) {
      setBuilding("");
      setBuildStep("");
      toast("error", (e as Error).message);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-5">
      <Card>
        <CardHeader>
          <CardTitle>{t("browseTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <Input
              placeholder={t("browsePlaceholder")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void handleSearch(); }}
              className="h-9 flex-1"
            />
            <Button onClick={() => void handleSearch()} disabled={searching}>
              {searching ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
              {t("browseSearch")}
            </Button>
          </div>

          {searching && (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          )}

          {!searching && searched && results.length === 0 && (
            <p className="text-sm text-[var(--text-muted)]">{t("browseNoResults")}</p>
          )}

          {!searching && results.length > 0 && (
            <div className="space-y-2">
              {results.map((r) => (
                <div key={r.name} className="flex items-center justify-between rounded-md bg-[var(--bg-elevated)] px-3 py-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm">
                      <Globe size={14} className="shrink-0 text-[var(--brand-blue)]" />
                      <span className="font-medium">{r.name}</span>
                      <Badge tone="neutral">v{r.version}</Badge>
                      {r.out_of_date && <Badge tone="warning">{t("browseOutOfDate")}</Badge>}
                      <span className="flex items-center gap-0.5 text-xs text-[var(--text-muted)]">
                        <ThumbsUp size={11} /> {r.num_votes}
                      </span>
                    </div>
                    <p className="truncate text-xs text-[var(--text-muted)]">{r.description}</p>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <button
                      aria-label={`${t("browseInfo")} ${r.name}`}
                      title={t("browseInfo")}
                      onClick={() => void handleInfo(r.name)}
                      className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-surface)] hover:text-[var(--brand-blue)]"
                    >
                      <Info size={14} />
                    </button>
                    <Button size="sm" variant="secondary" onClick={() => void handleBuild(r.name)} disabled={building !== ""}>
                      {building === r.name ? <Loader2 size={13} className="animate-spin" /> : <Hammer size={13} />}
                      {t("browseBuild")}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {building && (
            <div className="flex items-center gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2 text-sm">
              <Loader2 size={14} className="animate-spin text-[var(--brand-blue)]" />
              <span>
                {building} {buildStep === "clone" ? t("browseCloning") : buildStep === "build" ? t("browseBuilding") : t("browseStarting")}
              </span>
            </div>
          )}

          {info && (
            <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm">
              <div className="mb-1 flex items-center gap-2">
                <span className="font-medium">{infoName}</span>
                <Badge tone={info.status === "not_found" ? "danger" : "success"}>{info.status}</Badge>
              </div>
              {info.aur_version && <p className="text-xs text-[var(--text-muted)]">{t("browseAurVersion")} {info.aur_version}</p>}
              {info.detail && <p className="text-xs text-[var(--text-muted)]">{info.detail}</p>}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
