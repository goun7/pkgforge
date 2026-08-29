import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

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

import { listen } from "@tauri-apps/api/event";
import { Security } from "../Security";
import { ToastProvider } from "../../components/ui/Toast";

async function renderSecurity() {
  const r = render(
    <ToastProvider>
      <Security />
    </ToastProvider>,
  );
  await act(async () => {});
  return r;
}

describe("Security page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("renders all six tabs", async () => {
    await renderSecurity();
    // Ozet karti da ayni etiketleri tasidigi icin getAllByText kullanilir.
    expect(screen.getAllByText("İmza").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SBOM").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Kalite").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Provenance").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sigstore").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CVE Tara").length).toBeGreaterThan(0);
  });

  it("calls security.cve_scan when CVE tab used with a path", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { started: true } });
    await renderSecurity();
    fireEvent.change(screen.getByPlaceholderText(/paket yolu/i), { target: { value: "/tmp/x.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("CVE Tara")); // open the tab
    fireEvent.click(screen.getByText("Taramayı Başlat")); // trigger the scan
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "security.cve_scan" }),
      ),
    );
  });

  it("has a package path input", async () => {
    await renderSecurity();
    expect(screen.getByPlaceholderText(/paket yolu/i)).toBeInTheDocument();
  });

  it("calls security.verify when verify clicked with a path", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: { signed: true, valid: true, key_id: "ABC", key_fingerprint: "fp", signer: "me", timestamp: "t", detail: "" },
    });
    await renderSecurity();
    const input = screen.getByPlaceholderText(/paket yolu/i);
    fireEvent.change(input, { target: { value: "/tmp/x.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Doğrula"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "security.verify" }),
      ),
    );
  });

  it("shows signature result after verify", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: { signed: true, valid: true, key_id: "ABC123", key_fingerprint: "fp", signer: "tester", timestamp: "t", detail: "" },
    });
    await renderSecurity();
    fireEvent.change(screen.getByPlaceholderText(/paket yolu/i), { target: { value: "/tmp/x.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Doğrula"));
    await vi.waitFor(() => expect(screen.getByText(/ABC123/)).toBeInTheDocument());
  });
});

/* --- Genisletilmis kapsam: tab panelleri, event akislari, hata/bos durumlar --- */

const rpcOk = (result: unknown) => ({ jsonrpc: "2.0", id: 1, result, error: null });
const rpcErr = (code: number, message: string) => ({
  jsonrpc: "2.0",
  id: 1,
  result: null,
  error: { code, message },
});

const SIG_VALID = {
  signed: true,
  valid: true,
  key_id: "ABC123",
  key_fingerprint: "fp",
  signer: "tester",
  timestamp: "2025-01-01T00:00:00Z",
  detail: "",
};

const SBOM_DOC = {
  package_name: "demo",
  package_version: "1.0.0",
  package_arch: "x86_64",
  package_description: "",
  files: [
    { path: "/usr/bin/demo", file_type: "elf", size_bytes: 1024, sha256: "s1" },
    { path: "/usr/lib/libdemo.so", file_type: "elf", size_bytes: 512, sha256: "s2" },
    { path: "/usr/share/demo/readme", file_type: "text", size_bytes: 512, sha256: "s3" },
  ],
  dependencies: ["glibc", "openssl"],
  total_files: 3,
  total_size_bytes: 2048,
  elf_count: 2,
  text_count: 1,
  symlink_count: 0,
  dir_count: 0,
};

const QUALITY_REPORT = {
  package_name: "demo",
  total_score: 60,
  max_score: 100,
  grade: "C",
  passed: false,
  checks: [
    { name: "Lisans", category: "legal", passed: true, score: 30, max_score: 30, detail: "" },
    { name: "Dokümantasyon", category: "docs", passed: false, score: 5, max_score: 20, detail: "" },
  ],
};

const QUALITY_PASS = {
  package_name: "demo",
  total_score: 95,
  max_score: 100,
  grade: "A",
  passed: true,
  checks: [
    { name: "Lisans", category: "legal", passed: true, score: 30, max_score: 30, detail: "" },
  ],
};

const PROV = {
  source_file: "demo-1.0.0.tar.gz",
  source_type: "url",
  source_url: "https://example.com/demo-1.0.0.tar.gz",
  source_sha256: "aa",
  output_file: "demo-1.0.0-x86_64.pkg.tar.zst",
  output_sha256: "bb",
};

const SIGSTORE_OK = {
  cosign_available: true,
  cosign_path: "/usr/bin/cosign",
  cosign_version: "v2.2.4",
};
const SIGSTORE_NONE = { cosign_available: false, cosign_path: "", cosign_version: "" };

const CVE_CLEAN = { package: "demo", deps_scanned: 14, vulns: [], count: 0, offline: false };
const CVE_VULNS = {
  package: "demo",
  deps_scanned: 20,
  count: 3,
  offline: true,
  vulns: [
    { id: "CVE-2024-0001", summary: "kritik açık", severity: "CRITICAL", affected_dep: "openssl" },
    { id: "CVE-2024-0002", summary: "", severity: "MEDIUM", affected_dep: "zlib" },
    { id: "CVE-2024-0003", summary: "düşük", severity: "LOW", affected_dep: "ncurses" },
  ],
};

const KEYS = [
  { key_id: "KEY1", uid: "Alice <alice@example.com>", algo: "ed25519", created: "2024-01-01" },
  { key_id: "KEY2" },
];

describe("Security page — tab panelleri ve branch kapsami", () => {
  let secEventCb: ((e: { payload: unknown }) => void) | null = null;

  function setPath(value = "/tmp/demo.pkg.tar.zst") {
    fireEvent.change(screen.getByPlaceholderText(/paket yolu/i), { target: { value } });
  }
  /** Ozet kartlarinin aria-label'i "... durumu: ..." oldugu icin tab
   *  dugmeleriyle karismaz; bu yardimci ikisi icin de kullanilir. */
  function clickButton(name: string) {
    fireEvent.click(screen.getByRole("button", { name }));
  }
  /** event/security_done dinleyicisini yakalar (handleSbom/Quality/Cve/RunAll). */
  function armSecurityEvent() {
    secEventCb = null;
    vi.mocked(listen).mockImplementation(((_event: string, cb: (e: { payload: unknown }) => void) => {
      secEventCb = cb;
      return Promise.resolve(() => {});
    }) as unknown as typeof listen);
  }
  /** Yakalanan dinleyiciye event payload'i gonderir; mikro gorevleri de flush eder. */
  async function fireSecurityEvent(payload: unknown) {
    if (!secEventCb) throw new Error("event/security_done dinleyicisi kayitli degil");
    const cb = secEventCb;
    await act(async () => {
      cb({ payload });
      await Promise.resolve();
      await Promise.resolve();
    });
  }
  async function waitForCall(method: string) {
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method }),
      ),
    );
  }
  /** Click sonrasi mikro gorev zincirini (RPC cozumleri + setState) act icinde flush eder. */
  async function flushMicrotasks(times = 24) {
    await act(async () => {
      for (let i = 0; i < times; i++) await Promise.resolve();
    });
  }

  beforeEach(() => {
    invokeMock.mockReset();
  });
  afterEach(() => {
    // Varsayilan no-op dinleyiciyi geri yukle (test izolasyonu).
    vi.mocked(listen).mockImplementation((() => Promise.resolve(() => {})) as unknown as typeof listen);
    secEventCb = null;
  });

  it("tab degisimi: her tabin kendi paneli acilir", async () => {
    await renderSecurity();
    clickButton("SBOM");
    expect(screen.getByText("SBOM Oluştur")).toBeInTheDocument();
    expect(screen.queryByText("Doğrula")).not.toBeInTheDocument();
    clickButton("Kalite");
    expect(screen.getByText("Kalite Analizi")).toBeInTheDocument();
    expect(screen.queryByText("SBOM Oluştur")).not.toBeInTheDocument();
    clickButton("Provenance");
    expect(screen.getByText("Provenance Sorgula")).toBeInTheDocument();
    clickButton("Sigstore");
    expect(screen.getByText("Sigstore Durumu")).toBeInTheDocument();
    clickButton("CVE Tara");
    expect(screen.getByText("Taramayı Başlat")).toBeInTheDocument();
    clickButton("İmza");
    expect(screen.getByText("Doğrula")).toBeInTheDocument();
    expect(screen.getByText("Anahtarları Yükle")).toBeInTheDocument();
  });

  it("ozet kartindaki duruma tiklayinca ilgili tab acilir", async () => {
    await renderSecurity();
    clickButton("SBOM durumu: —");
    expect(screen.getByText("SBOM Oluştur")).toBeInTheDocument();
    clickButton("CVE durumu: —");
    expect(screen.getByText("Taramayı Başlat")).toBeInTheDocument();
  });

  it("yol olmadan dogrulama: toast gosterilir, RPC cagrilamaz", async () => {
    await renderSecurity();
    // Yol bosken "Tum Kontrolleri Calistir" devre disidir.
    expect(screen.getByRole("button", { name: "Tüm Kontrolleri Çalıştır" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Doğrula" }));
    expect(await screen.findByText("Önce bir paket yolu girin")).toBeInTheDocument();
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it("yol olmadan sbom/kalite/provenance/cve islemleri engellenir", async () => {
    await renderSecurity();
    clickButton("SBOM");
    fireEvent.click(screen.getByText("SBOM Oluştur"));
    clickButton("Kalite");
    fireEvent.click(screen.getByText("Kalite Analizi"));
    clickButton("Provenance");
    fireEvent.click(screen.getByText("Provenance Sorgula"));
    clickButton("CVE Tara");
    fireEvent.click(screen.getByText("Taramayı Başlat"));
    expect(await screen.findAllByText("Önce bir paket yolu girin")).toHaveLength(4);
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it("verify RPC hatasi: hata mesaji toast'ta gosterilir", async () => {
    invokeMock.mockResolvedValue(rpcErr(-32000, "imza okunamadı"));
    await renderSecurity();
    setPath();
    fireEvent.click(screen.getByRole("button", { name: "Doğrula" }));
    expect(await screen.findByText("-32000: imza okunamadı")).toBeInTheDocument();
  });

  it("gecersiz imza: signed ama valid degilse rozet + detay + ozet 'Geçersiz'", async () => {
    invokeMock.mockResolvedValue(
      rpcOk({ ...SIG_VALID, valid: false, detail: "anahtar süresi dolmuş" }),
    );
    await renderSecurity();
    setPath();
    fireEvent.click(screen.getByRole("button", { name: "Doğrula" }));
    expect(await screen.findByText("Geçersiz imza")).toBeInTheDocument();
    expect(screen.getByText("ABC123")).toBeInTheDocument(); // signed → dl gorunur
    expect(screen.getByText("anahtar süresi dolmuş")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "İmza durumu: Geçersiz" })).toBeInTheDocument();
  });

  it("imzasiz paket: dl gizlenir, detail gosterilir, ozet 'İmzasız'", async () => {
    invokeMock.mockResolvedValue(
      rpcOk({
        signed: false,
        valid: false,
        key_id: "",
        key_fingerprint: "",
        signer: "",
        timestamp: "",
        detail: "imza kaydı bulunamadı",
      }),
    );
    await renderSecurity();
    setPath();
    fireEvent.click(screen.getByRole("button", { name: "Doğrula" }));
    // Rozet + ozet karti ayni metni tasir.
    expect(await screen.findAllByText("İmzasız")).toHaveLength(2);
    expect(screen.queryByText("Key ID")).not.toBeInTheDocument();
    expect(screen.getByText("imza kaydı bulunamadı")).toBeInTheDocument();
  });

  it("imza anahtarlari listelenir (uid'li ve uid'siz)", async () => {
    invokeMock.mockResolvedValue(rpcOk(KEYS));
    await renderSecurity();
    fireEvent.click(screen.getByRole("button", { name: "Anahtarları Yükle" }));
    expect(await screen.findByText("KEY1")).toBeInTheDocument();
    expect(screen.getByText("KEY2")).toBeInTheDocument();
    // uid yalnizca KEY1'de var.
    expect(screen.getAllByText("Alice <alice@example.com>")).toHaveLength(1);
    await waitForCall("security.keys");
  });

  it("anahtar yaniti null ise bos durum mesaji gosterilir", async () => {
    invokeMock.mockResolvedValue(rpcOk(null));
    await renderSecurity();
    fireEvent.click(screen.getByRole("button", { name: "Anahtarları Yükle" }));
    expect(await screen.findByText("Henüz anahtar yok")).toBeInTheDocument();
  });

  it("anahtar yukleme hatasi toast gosterir", async () => {
    invokeMock.mockResolvedValue(rpcErr(-1, "keyring erisilemez"));
    await renderSecurity();
    fireEvent.click(screen.getByRole("button", { name: "Anahtarları Yükle" }));
    expect(await screen.findByText("-1: keyring erisilemez")).toBeInTheDocument();
  });

  it("SBOM basarili: event sonucu istatistikler ve dosya tablosu render edilir", async () => {
    armSecurityEvent();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    const { container } = await renderSecurity();
    setPath();
    clickButton("SBOM");
    fireEvent.click(screen.getByText("SBOM Oluştur"));
    await waitForCall("security.sbom");
    // Event gelene kadar yukleme iskeleti gorunur.
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await fireSecurityEvent({ ok: true, result: SBOM_DOC });
    expect(await screen.findByText("/usr/bin/demo")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // toplam dosya sayisi
    expect(screen.getAllByText("elf")).toHaveLength(2);
    expect(screen.getByText("Yol")).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeNull();
    expect(screen.getByRole("button", { name: "SBOM durumu: 3 Dosya" })).toBeInTheDocument();
  });

  it("SBOM event hata tasiyorsa o mesaj toast gosterilir", async () => {
    armSecurityEvent();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderSecurity();
    setPath();
    clickButton("SBOM");
    fireEvent.click(screen.getByText("SBOM Oluştur"));
    await waitForCall("security.sbom");
    await fireSecurityEvent({ ok: false, error: "sbom motoru çöktü" });
    expect(await screen.findByText("sbom motoru çöktü")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SBOM durumu: —" })).toBeInTheDocument();
  });

  it("SBOM event hatasiz başarısızsa fallback mesaj gosterilir", async () => {
    armSecurityEvent();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderSecurity();
    setPath();
    clickButton("SBOM");
    fireEvent.click(screen.getByText("SBOM Oluştur"));
    await waitForCall("security.sbom");
    await fireSecurityEvent({ ok: false });
    expect(await screen.findByText("SBOM oluşturulamadı")).toBeInTheDocument();
  });

  it("SBOM RPC cagrisi reddedilirse catch devreye girer ve loading kapanir", async () => {
    armSecurityEvent();
    invokeMock.mockRejectedValue(new Error("sidecar koptu"));
    const { container } = await renderSecurity();
    setPath();
    clickButton("SBOM");
    fireEvent.click(screen.getByText("SBOM Oluştur"));
    expect(await screen.findByText("sidecar koptu")).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeNull();
  });

  it("Kalite basarili: skor, not rozeti ve check listesi render edilir", async () => {
    armSecurityEvent();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderSecurity();
    setPath();
    clickButton("Kalite");
    fireEvent.click(screen.getByText("Kalite Analizi"));
    await waitForCall("security.quality");
    await fireSecurityEvent({ ok: true, result: QUALITY_REPORT });
    expect(await screen.findByText("60/100")).toBeInTheDocument();
    expect(screen.getByText("C")).toBeInTheDocument();
    expect(screen.getByText("✓ Lisans")).toBeInTheDocument();
    expect(screen.getByText("✗ Dokümantasyon")).toBeInTheDocument();
    expect(screen.getByText("30/30")).toBeInTheDocument();
    expect(screen.getByText("5/20")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kalite durumu: C (60/100)" })).toBeInTheDocument();
  });

  it("Kalite event hatasiz başarısızsa fallback mesaj gosterilir", async () => {
    armSecurityEvent();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderSecurity();
    setPath();
    clickButton("Kalite");
    fireEvent.click(screen.getByText("Kalite Analizi"));
    await waitForCall("security.quality");
    await fireSecurityEvent({ ok: false });
    expect(await screen.findByText("Kalite analizi başarısız")).toBeInTheDocument();
  });

  it("Provenance bulundu: kaynak/cikti alanlari listelenir", async () => {
    invokeMock.mockResolvedValue(rpcOk(PROV));
    await renderSecurity();
    setPath();
    clickButton("Provenance");
    fireEvent.click(screen.getByText("Provenance Sorgula"));
    expect(await screen.findByText("demo-1.0.0.tar.gz")).toBeInTheDocument();
    expect(screen.getByText("url")).toBeInTheDocument();
    expect(screen.getByText("demo-1.0.0-x86_64.pkg.tar.zst")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Provenance durumu: Bulundu" })).toBeInTheDocument();
  });

  it("Provenance yoksa bilgi toasti gosterilir, panel bos kalir", async () => {
    invokeMock.mockResolvedValue(rpcOk(null));
    await renderSecurity();
    setPath();
    clickButton("Provenance");
    fireEvent.click(screen.getByText("Provenance Sorgula"));
    expect(
      await screen.findByText("Bu paket için provenance kaydı bulunamadı"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Kaynak dosya")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Provenance durumu: —" })).toBeInTheDocument();
  });

  it("Provenance RPC hatasi toast gosterir", async () => {
    invokeMock.mockResolvedValue(rpcErr(-2, "provenance okunamadı"));
    await renderSecurity();
    setPath();
    clickButton("Provenance");
    fireEvent.click(screen.getByText("Provenance Sorgula"));
    expect(await screen.findByText("-2: provenance okunamadı")).toBeInTheDocument();
  });

  it("Sigstore: cosign kurulu ise durum rozeti ve surum gosterilir", async () => {
    invokeMock.mockResolvedValue(rpcOk(SIGSTORE_OK));
    await renderSecurity();
    clickButton("Sigstore");
    fireEvent.click(screen.getByText("Sigstore Durumu"));
    expect(await screen.findByText("cosign kurulu")).toBeInTheDocument();
    expect(screen.getByText("v2.2.4")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sigstore durumu: Cosign hazır" })).toBeInTheDocument();
  });

  it("Sigstore: cosign yoksa uyari rozeti gosterilir, surum gizlenir", async () => {
    invokeMock.mockResolvedValue(rpcOk(SIGSTORE_NONE));
    await renderSecurity();
    clickButton("Sigstore");
    fireEvent.click(screen.getByText("Sigstore Durumu"));
    expect(await screen.findByText("cosign yok")).toBeInTheDocument();
    expect(screen.queryByText("v2.2.4")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sigstore durumu: Cosign yok" })).toBeInTheDocument();
  });

  it("Sigstore RPC hatasi toast gosterir", async () => {
    invokeMock.mockResolvedValue(rpcErr(-3, "cosign sorgulanamadı"));
    await renderSecurity();
    clickButton("Sigstore");
    fireEvent.click(screen.getByText("Sigstore Durumu"));
    expect(await screen.findByText("-3: cosign sorgulanamadı")).toBeInTheDocument();
  });

  it("CVE temiz: acik yok, offline rozeti yok", async () => {
    armSecurityEvent();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderSecurity();
    setPath();
    clickButton("CVE Tara");
    fireEvent.click(screen.getByText("Taramayı Başlat"));
    await waitForCall("security.cve_scan");
    await fireSecurityEvent({ ok: true, result: CVE_CLEAN });
    expect(await screen.findByText("Açık bulunamadı")).toBeInTheDocument();
    expect(screen.getByText("14 bağımlılık tarandı")).toBeInTheDocument();
    expect(screen.queryByText("çevrimdışı")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "CVE durumu: Temiz" })).toBeInTheDocument();
  });

  it("CVE acik buldu: liste, ciddiyet rozetleri ve offline isareti gosterilir", async () => {
    armSecurityEvent();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderSecurity();
    setPath();
    clickButton("CVE Tara");
    fireEvent.click(screen.getByText("Taramayı Başlat"));
    await waitForCall("security.cve_scan");
    await fireSecurityEvent({ ok: true, result: CVE_VULNS });
    expect(await screen.findByText("3 açık bulundu")).toBeInTheDocument();
    expect(screen.getByText("çevrimdışı")).toBeInTheDocument();
    expect(screen.getByText("20 bağımlılık tarandı")).toBeInTheDocument();
    expect(screen.getByText("CVE-2024-0001")).toBeInTheDocument();
    expect(screen.getByText("CVE-2024-0002")).toBeInTheDocument();
    expect(screen.getByText("CVE-2024-0003")).toBeInTheDocument();
    expect(screen.getByText("(openssl)")).toBeInTheDocument();
    expect(screen.getByText("kritik açık")).toBeInTheDocument();
    expect(screen.getByText("düşük")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "CVE durumu: 3 açık" })).toBeInTheDocument();
  });

  it("CVE event hata mesaji tasiyorsa toast gosterilir", async () => {
    armSecurityEvent();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderSecurity();
    setPath();
    clickButton("CVE Tara");
    fireEvent.click(screen.getByText("Taramayı Başlat"));
    await waitForCall("security.cve_scan");
    await fireSecurityEvent({ ok: false, error: "veritabanı güncel değil" });
    expect(await screen.findByText("veritabanı güncel değil")).toBeInTheDocument();
  });

  it("CVE event hatasiz başarısızsa fallback mesaj gosterilir", async () => {
    armSecurityEvent();
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderSecurity();
    setPath();
    clickButton("CVE Tara");
    fireEvent.click(screen.getByText("Taramayı Başlat"));
    await waitForCall("security.cve_scan");
    await fireSecurityEvent({ ok: false });
    expect(await screen.findByText("CVE taraması başarısız")).toBeInTheDocument();
  });

  it("Tum Kontrolleri Calistir: alti kontrol sirayla tamamlanir, ozet dolar", async () => {
    armSecurityEvent();
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
      switch (payload.method) {
        case "security.verify":
          return Promise.resolve(rpcOk(SIG_VALID));
        case "security.sigstore_status":
          return Promise.resolve(rpcOk(SIGSTORE_OK));
        case "security.provenance":
          return Promise.resolve(rpcOk(PROV));
        default:
          return Promise.resolve(rpcOk({ started: true }));
      }
    });
    await renderSecurity();
    setPath();
    fireEvent.click(screen.getByRole("button", { name: "Tüm Kontrolleri Çalıştır" }));
    await flushMicrotasks(); // verify/sigstore/provenance cozulur, sbom siraya girer
    await waitForCall("security.sbom");
    await fireSecurityEvent({ ok: true, result: SBOM_DOC });
    await waitForCall("security.quality");
    await fireSecurityEvent({ ok: true, result: QUALITY_PASS });
    await waitForCall("security.cve_scan");
    await fireSecurityEvent({ ok: true, result: CVE_CLEAN });
    expect(await screen.findByText("Tüm güvenlik kontrolleri tamamlandı")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "İmza durumu: Geçerli" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SBOM durumu: 3 Dosya" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kalite durumu: A (95/100)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Provenance durumu: Bulundu" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sigstore durumu: Cosign hazır" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "CVE durumu: Temiz" })).toBeInTheDocument();
  });

  it("Tum Kontrolleri Calistir: ara hatalar atlanir, akis yine de tamamlanir", async () => {
    armSecurityEvent();
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
      switch (payload.method) {
        case "security.verify":
          return Promise.reject(new Error("verify bozuk"));
        case "security.sbom":
          return Promise.reject(new Error("sbom servisi yok"));
        case "security.sigstore_status":
          return Promise.resolve(rpcOk(SIGSTORE_OK));
        case "security.provenance":
          return Promise.resolve(rpcOk(PROV));
        default:
          return Promise.resolve(rpcOk({ started: true }));
      }
    });
    await renderSecurity();
    setPath();
    fireEvent.click(screen.getByRole("button", { name: "Tüm Kontrolleri Çalıştır" }));
    await flushMicrotasks(); // hatalar atlanir, sbom null ile gecilir, quality siraya girer
    // sbom cagrisi reddedildigi icin event beklenmez; sirada quality vardir.
    await waitForCall("security.quality");
    await fireSecurityEvent({ ok: true, result: QUALITY_PASS });
    await waitForCall("security.cve_scan");
    await fireSecurityEvent({ ok: false, error: "cve veritabanı eski" });
    expect(await screen.findByText("Tüm güvenlik kontrolleri tamamlandı")).toBeInTheDocument();
    // Basarisiz/olay gelmeyen kontroller ozette bos kalir.
    expect(screen.getByRole("button", { name: "İmza durumu: —" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SBOM durumu: —" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "CVE durumu: —" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kalite durumu: A (95/100)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sigstore durumu: Cosign hazır" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Provenance durumu: Bulundu" })).toBeInTheDocument();
  });

  it("runEventCheck zaman asimi: event gelmezse null ile devam edilir", async () => {
    vi.useFakeTimers();
    try {
      invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
        if (
          payload.method === "security.sbom" ||
          payload.method === "security.quality" ||
          payload.method === "security.cve_scan"
        ) {
          return Promise.resolve(rpcOk({ started: true }));
        }
        return Promise.resolve(rpcOk(null));
      });
      await renderSecurity();
      setPath();
      fireEvent.click(screen.getByRole("button", { name: "Tüm Kontrolleri Çalıştır" }));
      // Uc event kontrolunun her biri 180sn zaman asimiyla sirayla null doner.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(180_000);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(180_000);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(180_000);
      });
      expect(screen.getByText("Tüm güvenlik kontrolleri tamamlandı")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "SBOM durumu: —" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Kalite durumu: —" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "CVE durumu: —" })).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("yukleme sirasinda butonlar devre disidir ve spinner gosterilir", async () => {
    // Hic cozulmeyen promise: loading true kalir.
    invokeMock.mockImplementation(() => new Promise(() => {}));
    const { container } = await renderSecurity();
    setPath();
    fireEvent.click(screen.getByRole("button", { name: "Doğrula" }));
    expect(screen.getByRole("button", { name: "Doğrula" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Tüm Kontrolleri Çalıştır" })).toBeDisabled();
    expect(container.querySelector(".animate-spin")).not.toBeNull();
  });
});

