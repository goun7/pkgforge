import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// --- Tauri dialog plugin mock: defaultBrowse dinamik import'u bu stub'a dusmeli.
const openMock = vi.fn();
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: (...args: unknown[]) => openMock(...args),
}));

import { DropZone, filterAcceptedPaths } from "../DropZone";

const ZONE = "Paket bırakma alanı";

function zone() {
  return screen.getByRole("button", { name: ZONE });
}

describe("filterAcceptedPaths", () => {
  it("forwards every path (backend intake classifies)", () => {
    expect(
      filterAcceptedPaths(["/a/pkg_1.0.deb", "/b/x.rpm", "/c/app.tar.gz"]),
    ).toEqual(["/a/pkg_1.0.deb", "/b/x.rpm", "/c/app.tar.gz"]);
  });

  it("drops empty entries only", () => {
    expect(filterAcceptedPaths(["/a/PKG.DEB", ""])).toEqual(["/a/PKG.DEB"]);
  });

  it("drops non-string entries defensively", () => {
    expect(
      filterAcceptedPaths([
        "/a/p.deb",
        null,
        undefined,
        42,
        "/b/q.rpm",
      ] as unknown as string[]),
    ).toEqual(["/a/p.deb", "/b/q.rpm"]);
  });
});

describe("DropZone", () => {
  beforeEach(() => {
    openMock.mockReset();
  });

  it("renders the drop hint", () => {
    render(<DropZone onPaths={() => {}} browse={async () => []} />);
    expect(screen.getByRole("button", { name: "Paket bırakma alanı" })).toBeInTheDocument();
  });

  it("passes browsed paths through to the backend", async () => {
    const onPaths = vi.fn();
    const browse = vi.fn().mockResolvedValue(["/a/p.deb", "/b/app.tar.gz"]);
    render(<DropZone onPaths={onPaths} browse={browse} />);
    fireEvent.click(screen.getByRole("button", { name: "Paket bırakma alanı" }));
    await vi.waitFor(() => expect(onPaths).toHaveBeenCalledTimes(1));
    expect(onPaths).toHaveBeenCalledWith(["/a/p.deb", "/b/app.tar.gz"]);
  });

  it("does not call onPaths when nothing selected", async () => {
    const onPaths = vi.fn();
    const browse = vi.fn().mockResolvedValue([]);
    render(<DropZone onPaths={onPaths} browse={browse} />);
    fireEvent.click(screen.getByRole("button", { name: "Paket bırakma alanı" }));
    await vi.waitFor(() => expect(browse).toHaveBeenCalled());
    expect(onPaths).not.toHaveBeenCalled();
  });

  it("ignores clicks when disabled", () => {
    const browse = vi.fn();
    render(<DropZone onPaths={() => {}} browse={browse} disabled />);
    fireEvent.click(screen.getByRole("button", { name: "Paket bırakma alanı" }));
    expect(browse).not.toHaveBeenCalled();
  });

  it("shows a custom hint instead of the default one (idle styling)", () => {
    const { container } = render(
      <DropZone onPaths={() => {}} browse={async () => []} hint="Özel ipucu metni" />,
    );
    expect(screen.getByText("Özel ipucu metni")).toBeInTheDocument();
    expect(screen.queryByText("veya seçmek için tıklayın")).not.toBeInTheDocument();
    // pasif durum: dis kenarlik guclu border, ikon marka mavisi
    expect(zone().className).toContain("border-[var(--border-strong)]");
    expect(container.querySelector("svg")?.getAttribute("class")).toContain(
      "text-[var(--brand-blue)]",
    );
  });

  it("applies the active drag styling when dragging", () => {
    const { container } = render(
      <DropZone onPaths={() => {}} browse={async () => []} dragging />,
    );
    expect(screen.getByText("Paket dosyalarını buraya bırakın")).toBeInTheDocument();
    // aktif surukleme: ember kenarlik + parlama, ikon ember rengi
    expect(zone().className).toContain("border-[var(--brand-ember)]");
    expect(zone().className).toContain("shadow-[var(--glow-brand)]");
    expect(container.querySelector("svg")?.getAttribute("class")).toContain(
      "text-[var(--brand-ember)]",
    );
  });

  it("marks the zone visually disabled", () => {
    render(<DropZone onPaths={() => {}} browse={async () => []} disabled />);
    expect(zone().className).toContain("cursor-not-allowed");
    expect(zone().className).toContain("opacity-50");
  });

  it("opens the browser on Enter and Space keys", async () => {
    const browse = vi.fn().mockResolvedValue([]);
    render(<DropZone onPaths={() => {}} browse={browse} />);
    fireEvent.keyDown(zone(), { key: "Enter" });
    await vi.waitFor(() => expect(browse).toHaveBeenCalledTimes(1));
    // ilk gezinme bitmeden busy guard ikinciyi engeller; once bitmesini bekle
    fireEvent.keyDown(zone(), { key: " " });
    await vi.waitFor(() => expect(browse).toHaveBeenCalledTimes(2));
  });

  it("ignores keys other than Enter/Space", () => {
    const browse = vi.fn();
    render(<DropZone onPaths={() => {}} browse={browse} />);
    fireEvent.keyDown(zone(), { key: "a" });
    fireEvent.keyDown(zone(), { key: "Escape" });
    expect(browse).not.toHaveBeenCalled();
  });

  it("ignores keyboard activation when disabled", () => {
    const browse = vi.fn();
    render(<DropZone onPaths={() => {}} browse={browse} disabled />);
    fireEvent.keyDown(zone(), { key: "Enter" });
    fireEvent.keyDown(zone(), { key: " " });
    expect(browse).not.toHaveBeenCalled();
  });

  it("ignores further clicks while a browse is in flight and re-arms after", async () => {
    const onPaths = vi.fn();
    let resolveBrowse: (v: string[]) => void = () => {};
    const browse = vi.fn(
      () => new Promise<string[]>((res) => { resolveBrowse = res; }),
    );
    render(<DropZone onPaths={onPaths} browse={browse} />);
    fireEvent.click(zone());
    fireEvent.click(zone()); // ikinci tiklama busy guard'a carpip yok sayilir
    expect(browse).toHaveBeenCalledTimes(1);
    resolveBrowse(["/a/p.deb"]);
    await vi.waitFor(() => expect(onPaths).toHaveBeenCalledWith(["/a/p.deb"]));
    // busy finally blogunda sifirlandi: yeni tiklama tekrar ise yarar
    fireEvent.click(zone());
    await vi.waitFor(() => expect(browse).toHaveBeenCalledTimes(2));
    resolveBrowse(["/b/q.rpm"]);
    await vi.waitFor(() => expect(onPaths).toHaveBeenCalledTimes(2));
  });
});

describe("DropZone default browse (native dialog)", () => {
  beforeEach(() => {
    openMock.mockReset();
  });

  it("opens the native dialog with the package filter and forwards array selections", async () => {
    const onPaths = vi.fn();
    openMock.mockResolvedValueOnce(["/x/a.deb", "/y/b.rpm"]);
    render(<DropZone onPaths={onPaths} />);
    fireEvent.click(zone());
    await vi.waitFor(() =>
      expect(onPaths).toHaveBeenCalledWith(["/x/a.deb", "/y/b.rpm"]),
    );
    expect(openMock).toHaveBeenCalledTimes(1);
    const opts = openMock.mock.calls[0][0] as {
      multiple: boolean;
      title: string;
      filters: { name: string; extensions: string[] }[];
    };
    expect(opts.multiple).toBe(true);
    expect(opts.title).toBe("Paket seç");
    expect(opts.filters[0].name).toBe("Paketler");
    expect(opts.filters[0].extensions).toEqual([
      "deb", "rpm", "tar.gz", "tgz", "tar.xz", "txz", "tar.bz2", "tbz2",
      "tar.zst", "tar", "zip", "AppImage", "pkg.tar.zst", "flatpakref",
    ]);
  });

  it("wraps a single selected file into a list", async () => {
    const onPaths = vi.fn();
    openMock.mockResolvedValueOnce("/single/paket.deb");
    render(<DropZone onPaths={onPaths} />);
    fireEvent.click(zone());
    await vi.waitFor(() =>
      expect(onPaths).toHaveBeenCalledWith(["/single/paket.deb"]),
    );
  });

  it("yields no paths when the dialog is cancelled", async () => {
    const onPaths = vi.fn();
    openMock.mockResolvedValueOnce(null);
    render(<DropZone onPaths={onPaths} />);
    fireEvent.click(zone());
    await vi.waitFor(() => expect(openMock).toHaveBeenCalledTimes(1));
    await act(async () => { await Promise.resolve(); });
    expect(onPaths).not.toHaveBeenCalled();
  });
});
