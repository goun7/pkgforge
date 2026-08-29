import { render, screen, fireEvent } from "@testing-library/react";
import { act } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(() => Promise.resolve(null)),
}));

import { Export, __resetFlatpakCache } from "../Export";
import { ToastProvider } from "../../components/ui/Toast";
import { listen as tauriListen } from "@tauri-apps/api/event";
import type { FlatpakApp } from "../../lib/types";

type ListenCb = (e: { payload: unknown }) => void;

async function renderExport() {
  const r = render(
    <ToastProvider>
      <Export />
    </ToastProvider>,
  );
  await act(async () => {});
  return r;
}

/** JSON-RPC basari yaniti. */
function rpcOk(result: unknown) {
  return { jsonrpc: "2.0", id: 1, result, error: null };
}

/** JSON-RPC hata yaniti; call() "kod: mesaj" biciminde Error firlatir. */
function rpcErr(code: number, message: string) {
  return { jsonrpc: "2.0", id: 1, result: null, error: { code, message } };
}

/** event/export_done aboneligini yakalar; olayi elle ateslemeyi saglar.
 *  (Ustteki statik listen mock'u korunur; yalnizca tek cagrilik yakalayici kurulur.) */
function captureExportDone() {
  let handler: ListenCb | null = null;
  vi.mocked(tauriListen).mockImplementationOnce(
    ((_event: string, cb: ListenCb) => {
      handler = cb;
      return Promise.resolve(() => {});
    }) as unknown as typeof tauriListen,
  );
  return {
    fire(payload: unknown) {
      if (!handler) throw new Error("event/export_done dinleyicisi kaydedilmedi");
      handler({ payload });
    },
  };
}

/** invokeMock cagrilarindaki RPC metot adlari. */
function invokedMethods(): (string | undefined)[] {
  return invokeMock.mock.calls.map((c) => (c[1] as { method?: string } | undefined)?.method);
}

const GIMP: FlatpakApp = {
  app_id: "org.gimp.GIMP",
  name: "GIMP",
  version: "2.10.36",
  branch: "stable",
  description: "Goruntu duzenleyici",
  origin: "flathub",
};

const INKSCAPE_NO_NAME: FlatpakApp = {
  app_id: "org.inkscape.Inkscape",
  name: "",
  version: "1.3.2",
  branch: "stable",
  description: "",
  origin: "flathub",
};

describe("Export page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    __resetFlatpakCache(); // Faz 7: onbellegi her test oncesi sifirla
    // flatpak_list returns empty by default on mount
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: [] });
    // onceki testten kalabilecek implementationOnce'i temizle, varsayilani geri koy
    vi.mocked(tauriListen).mockReset();
    vi.mocked(tauriListen).mockImplementation(() => Promise.resolve(() => {}));
  });

  it("renders the three export cards", async () => {
    await renderExport();
    await vi.waitFor(() => expect(screen.getByText(/AppImage/)).toBeInTheDocument());
    expect(screen.getAllByText(/Flatpak/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/OCI/)).toBeInTheDocument();
  });

  it("loads flatpak app list on mount", async () => {
    await renderExport();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "export.flatpak_list" }),
      ),
    );
  });

  it("shows empty flatpak message when no apps", async () => {
    await renderExport();
    await vi.waitFor(() =>
      expect(screen.getByText(/Flatpak uygulaması bulunamadı/i)).toBeInTheDocument(),
    );
  });

  // --- AppImage -> DEB ---

  it("AppImage: yol bosken donusturmeyi baslatmaz, uyari toast'i gosterir", async () => {
    await renderExport();
    const convert = (await screen.findAllByRole("button", { name: "Dönüştür" }))[0];
    fireEvent.click(convert);
    expect(await screen.findByText("Bir AppImage dosyası seçin")).toBeInTheDocument();
    expect(invokedMethods()).not.toContain("export.appimage_to_deb");
  });

  it("AppImage: donusumu baslatir, export_done basarisinda sonucu ve deb yolunu gosterir", async () => {
    await renderExport();
    fireEvent.change(screen.getByPlaceholderText("AppImage yolu…"), {
      target: { value: "/tmp/app.AppImage" },
    });
    const done = captureExportDone();
    const convert = (await screen.findAllByRole("button", { name: "Dönüştür" }))[0];
    fireEvent.click(convert);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "export.appimage_to_deb",
          params: { appimage_path: "/tmp/app.AppImage" },
        }),
      ),
    );
    // islem surerken dugme devre disi ve iskelet gosteriliyor
    expect(convert).toBeDisabled();
    expect(document.querySelector(".h-8.w-full")).not.toBeNull();

    act(() =>
      done.fire({ ok: true, result: { ok: true, message: "DEB hazir", deb_path: "/out/app.deb" } }),
    );
    expect(await screen.findByText("Başarılı")).toBeInTheDocument();
    // mesaj hem toast'ta hem sonuc satirinda gorunur
    expect((await screen.findAllByText("DEB hazir")).length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText("/out/app.deb")).toBeInTheDocument();
    await vi.waitFor(() => expect(convert).not.toBeDisabled());
  });

  it("AppImage: result.ok=false ise Basarisiz rozeti ve Yeniden dene dugmesi gosterilir", async () => {
    await renderExport();
    fireEvent.change(screen.getByPlaceholderText("AppImage yolu…"), {
      target: { value: "/tmp/app.AppImage" },
    });
    const done = captureExportDone();
    const convert = (await screen.findAllByRole("button", { name: "Dönüştür" }))[0];
    fireEvent.click(convert);
    await vi.waitFor(() => expect(invokedMethods()).toContain("export.appimage_to_deb"));
    act(() => done.fire({ ok: true, result: { ok: false, message: "donusum basarisiz" } }));
    expect(await screen.findByText("Başarısız")).toBeInTheDocument();
    expect((await screen.findAllByText("donusum basarisiz")).length).toBeGreaterThanOrEqual(1);
    const retry = screen.getByRole("button", { name: "Yeniden dene" });
    fireEvent.click(retry);
    await vi.waitFor(() =>
      expect(invokedMethods().filter((m) => m === "export.appimage_to_deb")).toHaveLength(2),
    );
  });

  it("AppImage: export_done sonucsuz gelirse event'teki hata mesaji toast'ta gosterilir", async () => {
    await renderExport();
    fireEvent.change(screen.getByPlaceholderText("AppImage yolu…"), {
      target: { value: "/tmp/app.AppImage" },
    });
    const done = captureExportDone();
    const convert = (await screen.findAllByRole("button", { name: "Dönüştür" }))[0];
    fireEvent.click(convert);
    await vi.waitFor(() => expect(invokedMethods()).toContain("export.appimage_to_deb"));
    act(() => done.fire({ ok: false, error: "disk doldu" }));
    expect(await screen.findByText("disk doldu")).toBeInTheDocument();
    await vi.waitFor(() => expect(convert).not.toBeDisabled());
  });

  it("AppImage: export_done hata mesajsiz gelirse varsayilan basarisizlik metni gosterilir", async () => {
    await renderExport();
    fireEvent.change(screen.getByPlaceholderText("AppImage yolu…"), {
      target: { value: "/tmp/app.AppImage" },
    });
    const done = captureExportDone();
    fireEvent.click((await screen.findAllByRole("button", { name: "Dönüştür" }))[0]);
    await vi.waitFor(() => expect(invokedMethods()).toContain("export.appimage_to_deb"));
    act(() => done.fire({ ok: false }));
    expect(await screen.findByText("Dışa aktarma başarısız")).toBeInTheDocument();
  });

  it("AppImage: RPC hata yaniti toast gosterir ve dugmeyi tekrar etkinlestirir", async () => {
    invokeMock.mockReset();
    invokeMock
      .mockResolvedValueOnce(rpcOk([])) // mount: flatpak_list
      .mockResolvedValueOnce(rpcErr(-32000, "appimage bozuk"));
    await renderExport();
    fireEvent.change(screen.getByPlaceholderText("AppImage yolu…"), {
      target: { value: "/tmp/app.AppImage" },
    });
    const convert = (await screen.findAllByRole("button", { name: "Dönüştür" }))[0];
    fireEvent.click(convert);
    expect(await screen.findByText("-32000: appimage bozuk")).toBeInTheDocument();
    await vi.waitFor(() => expect(convert).not.toBeDisabled());
  });

  // --- Flatpak -> DEB ---

  it("Flatpak: uygulama listesi render edilir, secim yoksa Dönüştür devre disidir", async () => {
    invokeMock.mockResolvedValue(rpcOk([GIMP, INKSCAPE_NO_NAME]));
    await renderExport();
    expect(await screen.findByText("GIMP")).toBeInTheDocument();
    // bos name -> app_id'e dusen dal
    expect(await screen.findByText("org.inkscape.Inkscape")).toBeInTheDocument();
    expect(screen.getByText("2.10.36")).toBeInTheDocument();
    expect(screen.getByText("1.3.2")).toBeInTheDocument();
    const convert = screen.getAllByRole("button", { name: "Dönüştür" })[1];
    expect(convert).toBeDisabled();
    fireEvent.click(screen.getByText("GIMP"));
    await vi.waitFor(() => expect(convert).not.toBeDisabled());
  });

  it("Flatpak: secili uygulama donusturulur ve basari rozeti gosterilir", async () => {
    invokeMock.mockResolvedValue(rpcOk([GIMP]));
    await renderExport();
    fireEvent.click(await screen.findByText("GIMP"));
    const done = captureExportDone();
    const convert = screen.getAllByRole("button", { name: "Dönüştür" })[1];
    await vi.waitFor(() => expect(convert).not.toBeDisabled());
    fireEvent.click(convert);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "export.flatpak_to_deb",
          params: { app_id: "org.gimp.GIMP" },
        }),
      ),
    );
    act(() => done.fire({ ok: true, result: { ok: true, message: "flatpak deb hazir" } }));
    expect(await screen.findByText("Başarılı")).toBeInTheDocument();
  });

  it("Flatpak: donusum RPC hatasi toast gosterir ve dugmeyi serbest birakir", async () => {
    invokeMock.mockReset();
    invokeMock
      .mockResolvedValueOnce(rpcOk([GIMP]))
      .mockResolvedValueOnce(rpcErr(-32001, "flatpak donusturulemedi"));
    await renderExport();
    fireEvent.click(await screen.findByText("GIMP"));
    const convert = screen.getAllByRole("button", { name: "Dönüştür" })[1];
    await vi.waitFor(() => expect(convert).not.toBeDisabled());
    fireEvent.click(convert);
    expect(await screen.findByText("-32001: flatpak donusturulemedi")).toBeInTheDocument();
    await vi.waitFor(() => expect(convert).not.toBeDisabled());
  });

  it("Flatpak: Yenile dugmesi onbellege ragmen listeyi zorla yeniden yukler", async () => {
    invokeMock.mockResolvedValue(rpcOk([GIMP]));
    await renderExport();
    await screen.findByText("GIMP");
    fireEvent.click(screen.getByRole("button", { name: "Yenile" }));
    await vi.waitFor(() =>
      expect(invokedMethods().filter((m) => m === "export.flatpak_list")).toHaveLength(2),
    );
  });

  it("Flatpak: ikinci mount onbellegi kullanir, flatpak_list yeniden cagrilir olmaz", async () => {
    invokeMock.mockResolvedValue(rpcOk([GIMP]));
    const first = await renderExport();
    await screen.findByText("GIMP");
    first.unmount();
    await renderExport();
    await screen.findByText("GIMP");
    expect(invokedMethods().filter((m) => m === "export.flatpak_list")).toHaveLength(1);
  });

  it("Flatpak: liste yuklenemezse hata toast'i ve bos durum mesaji gosterilir", async () => {
    invokeMock.mockResolvedValue(rpcErr(-1, "flatpak listelenemedi"));
    await renderExport();
    expect(await screen.findByText("-1: flatpak listelenemedi")).toBeInTheDocument();
    expect(await screen.findByText("Flatpak uygulaması bulunamadı.")).toBeInTheDocument();
  });

  // --- OCI container ---

  it("OCI: paket yolu bosken imaj olusturmaz, uyari toast'i gosterir", async () => {
    await renderExport();
    fireEvent.click(await screen.findByRole("button", { name: "İmaj Oluştur" }));
    expect(await screen.findByText("Bir .pkg.tar.zst paketi seçin")).toBeInTheDocument();
    expect(invokedMethods()).not.toContain("export.oci");
  });

  it("OCI: etiketle imaj olusturur, basarida cikti yolunu gosterir", async () => {
    await renderExport();
    fireEvent.change(screen.getByPlaceholderText("Paket yolu (.pkg.tar.zst)…"), {
      target: { value: "/tmp/foo.pkg.tar.zst" },
    });
    fireEvent.change(screen.getByPlaceholderText("İmaj etiketi (opsiyonel)…"), {
      target: { value: "v1.0" },
    });
    const done = captureExportDone();
    const create = screen.getByRole("button", { name: "İmaj Oluştur" });
    fireEvent.click(create);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "export.oci",
          params: { pkg_path: "/tmp/foo.pkg.tar.zst", tag: "v1.0" },
        }),
      ),
    );
    act(() =>
      done.fire({
        ok: true,
        result: { ok: true, message: "OCI imaji hazir", output_path: "/out/foo-oci.tar" },
      }),
    );
    expect(await screen.findByText("Başarılı")).toBeInTheDocument();
    expect(await screen.findByText("/out/foo-oci.tar")).toBeInTheDocument();
  });

  it("OCI: etiket bos birakilirsa tag undefined gonderilir", async () => {
    await renderExport();
    fireEvent.change(screen.getByPlaceholderText("Paket yolu (.pkg.tar.zst)…"), {
      target: { value: "/tmp/foo.pkg.tar.zst" },
    });
    const done = captureExportDone();
    fireEvent.click(screen.getByRole("button", { name: "İmaj Oluştur" }));
    await vi.waitFor(() => expect(invokedMethods()).toContain("export.oci"));
    const ociCall = invokeMock.mock.calls.find(
      (c) => (c[1] as { method?: string } | undefined)?.method === "export.oci",
    );
    const params = (ociCall?.[1] as { params?: { pkg_path?: string; tag?: string } } | undefined)
      ?.params;
    expect(params?.pkg_path).toBe("/tmp/foo.pkg.tar.zst");
    expect(params?.tag).toBeUndefined();
    act(() => done.fire({ ok: true, result: { ok: true, message: "OCI hazir" } }));
    expect(await screen.findByText("Başarılı")).toBeInTheDocument();
  });

  it("OCI: RPC hata yaniti toast gosterir ve dugmeyi tekrar etkinlestirir", async () => {
    invokeMock.mockReset();
    invokeMock
      .mockResolvedValueOnce(rpcOk([])) // mount: flatpak_list
      .mockResolvedValueOnce(rpcErr(-32002, "oci olusturulamadi"));
    await renderExport();
    fireEvent.change(screen.getByPlaceholderText("Paket yolu (.pkg.tar.zst)…"), {
      target: { value: "/tmp/foo.pkg.tar.zst" },
    });
    const create = screen.getByRole("button", { name: "İmaj Oluştur" });
    fireEvent.click(create);
    expect(await screen.findByText("-32002: oci olusturulamadi")).toBeInTheDocument();
    await vi.waitFor(() => expect(create).not.toBeDisabled());
  });
});
