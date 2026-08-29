import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LogViewer } from "../LogViewer";

// jsdom'da navigator.clipboard yok — kopya/indirme daglarini dogrulamak icin stub.
const clipboardWriteText = vi.fn().mockResolvedValue(undefined);
Object.defineProperty(navigator, "clipboard", {
  value: { writeText: clipboardWriteText },
  configurable: true,
});

describe("LogViewer — Faz 19 kapsam dalları", () => {
  it("Temizle butonu onClear'i çağırır; verilmezse görünmez", () => {
    const onClear = vi.fn();
    const { rerender } = render(
      <LogViewer lines={[]} onClear={onClear} />,
    );
    fireEvent.click(screen.getByLabelText("Logu temizle"));
    expect(onClear).toHaveBeenCalledTimes(1);

    rerender(<LogViewer lines={[]} />);
    expect(screen.queryByLabelText("Logu temizle")).not.toBeInTheDocument();
  });

  it("kopyala butonu görünür logları pano metnine yazar", async () => {
    render(
      <LogViewer
        lines={[
          { message: "satir1", level: "info" },
          { message: "satir2", level: "warning" },
        ]}
      />,
    );
    fireEvent.click(screen.getByLabelText("Logu kopyala"));
    await vi.waitFor(() => expect(clipboardWriteText).toHaveBeenCalled());
    expect(clipboardWriteText.mock.calls[0][0]).toBe("satir1\nsatir2");
  });

  it("indir butonu .txt blob indirmesi tetikler (URL.createObjectURL yolu)", () => {
    const createObjectURL = vi.fn(() => "blob:log");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });
    const clickSpy = vi.fn();
    // HTMLAnchorElement.click jsdom'da navigasyon yapmaz — spy ile doğrula.
    const anchorProto = HTMLAnchorElement.prototype;
    const origClick = anchorProto.click;
    anchorProto.click = clickSpy;

    render(<LogViewer lines={[{ message: "x", level: "info" }]} />);
    try {
      fireEvent.click(screen.getByLabelText("Logu indir"));
      expect(createObjectURL).toHaveBeenCalled();
      expect(clickSpy).toHaveBeenCalled();
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:log");
    } finally {
      anchorProto.click = origClick;
    }
  });

  it("1000+ satır kırpılır: son satır görünür, ilk satır DOM'da yok", () => {
    const many = Array.from({ length: 1200 }, (_, i) => ({
      message: "log-" + i,
      level: "info",
    }));
    render(<LogViewer lines={many} />);
    expect(screen.getByText("log-1199")).toBeInTheDocument();
    expect(screen.queryByText("log-0")).not.toBeInTheDocument();
    expect(screen.queryByText("log-199")).not.toBeInTheDocument();
    expect(screen.getByText("log-200")).toBeInTheDocument();
  });

  it("bilinmeyen seviye varsayılan (info) rengine düşer", () => {
    render(
      <LogViewer lines={[{ message: "garip", level: "tanimsiz" }]} />,
    );
    expect(screen.getByText("garip")).toBeInTheDocument();
  });
});
