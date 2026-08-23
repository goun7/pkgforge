import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// --- Mock the Tauri API surface used by Convert / rpc ---
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

// DropZone's dynamic import of the dialog plugin must resolve to a stub.
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockResolvedValue([]),
}));

import { Convert } from "../Convert";
import { ToastProvider } from "../../components/ui/Toast";

function renderConvert() {
  return render(
    <ToastProvider>
      <Convert />
    </ToastProvider>,
  );
}

function emit(event: string, payload: unknown) {
  const cb = listeners.get(event);
  if (cb) cb({ payload });
}

describe("Convert page", () => {
  beforeEach(() => {
    listeners.clear();
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ started: true });
  });

  it("renders the drop zone and empty queue", () => {
    renderConvert();
    expect(screen.getByRole("button", { name: "drop-zone" })).toBeInTheDocument();
    expect(screen.getByText("Kuyruk (0)")).toBeInTheDocument();
  });

  it("subscribes to pipeline events on mount", () => {
    renderConvert();
    expect(listeners.has("event/step_changed")).toBe(true);
    expect(listeners.has("event/progress")).toBe(true);
    expect(listeners.has("event/log")).toBe(true);
    expect(listeners.has("event/finished")).toBe(true);
  });

  it("starts the pipeline when a path is dropped", async () => {
    renderConvert();
    // Simulate a native drag-drop with a real path.
    emit("tauri://drag-drop", { paths: ["/tmp/pkg_1.0_amd64.deb"] });
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "pipeline.start" }),
      ),
    );
    expect(screen.getByText("pkg_1.0_amd64.deb")).toBeInTheDocument();
  });

  it("marks the running item failed when finished reports failure", async () => {
    renderConvert();
    emit("tauri://drag-drop", { paths: ["/tmp/bad.deb"] });
    await vi.waitFor(() => expect(invokeMock).toHaveBeenCalled());
    emit("event/finished", { success: false, message: "analiz hatası" });
    await vi.waitFor(() => expect(screen.getByText("failed")).toBeInTheDocument());
  });

  it("shows the compatibility dialog and approves install", async () => {
    renderConvert();
    emit("tauri://drag-drop", { paths: ["/tmp/warn.deb"] });
    await vi.waitFor(() => expect(invokeMock).toHaveBeenCalled());
    emit("event/compatibility_ready", {
      report: {
        overall: "warning",
        grade: "B",
        checks: [{ name: "deps", severity: "warning", message: "eksik bağımlılık", details: [] }],
      },
    });
    await vi.waitFor(() =>
      expect(screen.getByText(/Uyumluluk Raporu/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Yine de Kur"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "pipeline.approve" }),
      ),
    );
  });

  it("renders the batch tab and loads the queue on switch", async () => {
    invokeMock.mockResolvedValue([]);
    renderConvert();
    fireEvent.click(screen.getByText("Toplu"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "queue.list" }),
      ),
    );
    expect(screen.getByText("Toplu Dönüştürme")).toBeInTheDocument();
  });
});
