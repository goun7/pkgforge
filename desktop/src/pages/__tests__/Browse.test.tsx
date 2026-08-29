import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// --- Mock the Tauri API surface used by Browse / rpc ---
const listeners = new Map<string, (e: { payload: unknown }) => void>();

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn((event: string, cb: (e: { payload: unknown }) => void) => {
    listeners.set(event, cb);
    return Promise.resolve(() => listeners.delete(event));
  }),
}));

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

import { Browse } from "../Browse";
import { ToastProvider } from "../../components/ui/Toast";

async function renderBrowse() {
  const r = render(
    <ToastProvider>
      <Browse />
    </ToastProvider>,
  );
  await act(async () => {});
  return r;
}

function searchInput() {
  return screen.getByPlaceholderText(/AUR'da ara/i);
}

/** Fire a push event captured from the page's listen() subscription. */
function emit(event: string, payload: unknown) {
  const cb = listeners.get(event);
  if (!cb) throw new Error(`no listener registered for ${event}`);
  act(() => {
    cb({ payload });
  });
}

function rpcOk(result: unknown) {
  return { jsonrpc: "2.0", id: 1, result, error: null };
}

function rpcErr(code: number, message: string) {
  return { jsonrpc: "2.0", id: 1, result: null, error: { code, message } };
}

const firefox = {
  name: "firefox-bin",
  version: "130.0-1",
  description: "Standalone web browser",
  num_votes: 1200,
  out_of_date: false,
  url_path: "/packages/firefox-bin",
};

const langpack = {
  name: "firefox-i18n",
  version: "129.0-1",
  description: "Language packs",
  num_votes: 3,
  out_of_date: true,
  url_path: "/packages/firefox-i18n",
};

describe("Browse page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    listeners.clear();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
  });

  it("renders the search input and button", async () => {
    await renderBrowse();
    expect(screen.getByPlaceholderText(/AUR'da ara/i)).toBeInTheDocument();
    expect(screen.getByText("Ara")).toBeInTheDocument();
  });

  it("calls aur.search when searching", async () => {
    await renderBrowse();
    fireEvent.change(screen.getByPlaceholderText(/AUR'da ara/i), { target: { value: "firefox" } });
    fireEvent.click(screen.getByText("Ara"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "aur.search" }),
      ),
    );
  });

  it("does not search with empty query", async () => {
    await renderBrowse();
    fireEvent.click(screen.getByText("Ara"));
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it("restores the persisted query from sessionStorage", async () => {
    sessionStorage.setItem("pkgforge.browse.query", "vlc");
    await renderBrowse();
    expect(searchInput()).toHaveValue("vlc");
  });

  it("falls back to an empty query when sessionStorage is unavailable", async () => {
    const getItem = vi.spyOn(sessionStorage, "getItem").mockImplementation(() => {
      throw new Error("depolama yok");
    });
    const setItem = vi.spyOn(sessionStorage, "setItem").mockImplementation(() => {
      throw new Error("depolama yok");
    });
    await renderBrowse();
    expect(searchInput()).toHaveValue("");
    getItem.mockRestore();
    setItem.mockRestore();
  });

  it("shows skeletons and disables the search button while searching", async () => {
    await renderBrowse();
    fireEvent.change(searchInput(), { target: { value: "firefox" } });
    fireEvent.click(screen.getByText("Ara"));
    expect(screen.getByText("Ara").closest("button")).toBeDisabled();
    expect(document.querySelectorAll(".animate-pulse")).toHaveLength(3);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "aur.search",
          params: expect.objectContaining({ query: "firefox", limit: 25 }),
        }),
      ),
    );
    // RPC sadece aramayi baslatir; iskeletler done event'ine kadar kalir.
    expect(document.querySelectorAll(".animate-pulse")).toHaveLength(3);
  });

  it("searches on Enter but ignores other keys", async () => {
    await renderBrowse();
    fireEvent.change(searchInput(), { target: { value: "firefox" } });
    fireEvent.keyDown(searchInput(), { key: "a" });
    expect(invokeMock).not.toHaveBeenCalled();
    fireEvent.keyDown(searchInput(), { key: "Enter" });
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "aur.search" }),
      ),
    );
  });

  it("renders search results when aur_search_done arrives", async () => {
    await renderBrowse();
    await act(async () => emit("event/aur_search_done", { ok: true, result: [firefox, langpack] }));
    expect(screen.getByText("firefox-bin")).toBeInTheDocument();
    expect(screen.getByText("v130.0-1")).toBeInTheDocument();
    expect(screen.getByText("Standalone web browser")).toBeInTheDocument();
    expect(screen.getByText("1200")).toBeInTheDocument();
    // Eskimis rozeti yalnizca bayat sonucta render edilir.
    expect(screen.getAllByText("eski")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Bilgi firefox-bin" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bilgi firefox-i18n" })).toBeInTheDocument();
    expect(screen.getAllByText("Derle")).toHaveLength(2);
    expect(screen.queryByText("Sonuç bulunamadı.")).not.toBeInTheDocument();
    // 2 sonuc 25'lik limiti doldurmaz: load-more yok.
    expect(screen.queryByText("Daha fazla yükle")).not.toBeInTheDocument();
  });

  it("shows the empty state when the search returns no results", async () => {
    await renderBrowse();
    await act(async () => emit("event/aur_search_done", { ok: true, result: [] }));
    expect(screen.getByText("Sonuç bulunamadı.")).toBeInTheDocument();
  });

  it("toasts when the search done event reports failure", async () => {
    await renderBrowse();
    await act(async () => emit("event/aur_search_done", { ok: false, error: "AUR rate limit" }));
    await screen.findByText("AUR rate limit");
    // Sonuc yuku yoksa (ok olsa bile) fallback mesaj kullanilir.
    await act(async () => emit("event/aur_search_done", { ok: true }));
    await act(async () => emit("event/aur_search_done", { ok: false }));
    await vi.waitFor(() =>
      expect(screen.getAllByText("Arama başarısız")).toHaveLength(2),
    );
    expect(screen.getByText("Sonuç bulunamadı.")).toBeInTheDocument();
  });

  it("offers load more at the limit and raises the limit by 25", async () => {
    await renderBrowse();
    fireEvent.change(searchInput(), { target: { value: "firefox" } });
    const many = Array.from({ length: 25 }, (_, i) => ({
      name: `pkg-${i}`,
      version: "1.0-1",
      description: `Package ${i}`,
      num_votes: i,
      out_of_date: false,
      url_path: `/packages/pkg-${i}`,
    }));
    await act(async () => emit("event/aur_search_done", { ok: true, result: many }));
    fireEvent.click(screen.getByText("Daha fazla yükle"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "aur.search",
          params: expect.objectContaining({ query: "firefox", limit: 50 }),
        }),
      ),
    );
  });

  it("clears searching and toasts when the aur.search RPC fails", async () => {
    await renderBrowse();
    fireEvent.change(searchInput(), { target: { value: "firefox" } });
    invokeMock.mockResolvedValue(rpcErr(-32000, "aur offline"));
    fireEvent.click(screen.getByText("Ara"));
    await screen.findByText("-32000: aur offline");
    expect(screen.getByText("Ara").closest("button")).toBeEnabled();
    expect(document.querySelectorAll(".animate-pulse")).toHaveLength(0);
  });

  it("fetches package info and shows the info panel", async () => {
    await renderBrowse();
    await act(async () => emit("event/aur_search_done", { ok: true, result: [firefox] }));
    fireEvent.click(screen.getByRole("button", { name: "Bilgi firefox-bin" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "aur.info", params: { name: "firefox-bin" } }),
      ),
    );
    emit("event/aur_info_done", {
      ok: true,
      result: {
        status: "found",
        aur_version: "130.0-1",
        out_of_date: false,
        last_modified: "2024-09-01",
        detail: "Paket detayi burada",
      },
    });
    const badge = screen.getByText("found");
    expect(badge.className).toContain("var(--success)");
    expect(screen.getByText("AUR sürümü: 130.0-1")).toBeInTheDocument();
    expect(screen.getByText("Paket detayi burada")).toBeInTheDocument();
  });

  it("shows a danger badge for not_found info and omits empty fields", async () => {
    await renderBrowse();
    emit("event/aur_info_done", {
      ok: true,
      result: { status: "not_found", aur_version: "", out_of_date: false, last_modified: "", detail: "" },
    });
    const badge = screen.getByText("not_found");
    expect(badge.className).toContain("var(--danger)");
    expect(screen.queryByText(/AUR sürümü:/)).not.toBeInTheDocument();
  });

  it("toasts when the info done event reports failure", async () => {
    await renderBrowse();
    await act(async () => emit("event/aur_info_done", { ok: false, error: "info boom" }));
    await screen.findByText("info boom");
    await act(async () => emit("event/aur_info_done", { ok: false }));
    await screen.findByText("Bilgi alınamadı");
  });

  it("toasts when the aur.info RPC fails", async () => {
    await renderBrowse();
    await act(async () => emit("event/aur_search_done", { ok: true, result: [firefox] }));
    invokeMock.mockResolvedValue(rpcErr(-2, "info yok"));
    fireEvent.click(screen.getByRole("button", { name: "Bilgi firefox-bin" }));
    await screen.findByText("-2: info yok");
  });

  it("runs the build flow: progress steps, disabled buttons, success toast", async () => {
    await renderBrowse();
    await act(async () => emit("event/aur_search_done", { ok: true, result: [firefox, langpack] }));
    fireEvent.click(screen.getAllByText("Derle")[0]);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "aur.build", params: { name: "firefox-bin" } }),
      ),
    );
    // Banner "starting" adimini gosterir, tum Derle butonlari devre disi.
    expect(screen.getByText("firefox-bin başlatılıyor…")).toBeInTheDocument();
    for (const label of screen.getAllByText("Derle")) {
      expect(label.closest("button")).toBeDisabled();
    }
    await act(async () => emit("event/aur_build_progress", { name: "firefox-bin", step: "clone" }));
    expect(screen.getByText("firefox-bin klonlanıyor…")).toBeInTheDocument();
    await act(async () => emit("event/aur_build_progress", { name: "firefox-bin", step: "build" }));
    expect(screen.getByText("firefox-bin derleniyor (makepkg)…")).toBeInTheDocument();
    emit("event/aur_build_done", {
      ok: true,
      result: {
        name: "firefox-bin",
        pkg_path: "/home/gokun/out/firefox-bin-130.0-1-x86_64.pkg.tar.zst",
        installed: true,
      },
    });
    await screen.findByText("firefox-bin derlendi: firefox-bin-130.0-1-x86_64.pkg.tar.zst");
    expect(screen.queryByText(/klonlanıyor…/)).not.toBeInTheDocument();
    for (const label of screen.getAllByText("Derle")) {
      expect(label.closest("button")).toBeEnabled();
    }
  });

  it("toasts and clears the banner when the build done event fails", async () => {
    await renderBrowse();
    await act(async () => emit("event/aur_search_done", { ok: true, result: [firefox] }));
    fireEvent.click(screen.getByText("Derle"));
    await act(async () => emit("event/aur_build_done", { ok: false, error: "makepkg: hata" }));
    await screen.findByText("makepkg: hata");
    expect(screen.queryByText(/başlatılıyor…/)).not.toBeInTheDocument();
    // Acik hata mesaji yoksa fallback kullanilir.
    await act(async () => emit("event/aur_build_done", { ok: false }));
    await screen.findByText("Derleme başarısız");
  });

  it("clears building state and toasts when the aur.build RPC fails", async () => {
    await renderBrowse();
    await act(async () => emit("event/aur_search_done", { ok: true, result: [firefox] }));
    invokeMock.mockResolvedValue(rpcErr(-3, "build yok"));
    fireEvent.click(screen.getByText("Derle"));
    await screen.findByText("-3: build yok");
    expect(screen.queryByText(/başlatılıyor…/)).not.toBeInTheDocument();
    expect(screen.getByText("Derle").closest("button")).toBeEnabled();
  });
});
