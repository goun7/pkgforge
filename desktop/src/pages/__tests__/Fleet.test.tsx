import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Fleet } from "../Fleet";
import { ToastProvider } from "../../components/ui/Toast";

const FLEET_STATUS = {
  backends: {
    webdav: { configured: true, available: true },
    git: { configured: false, available: true },
    "rclone-s3": { configured: false, available: false },
  },
  backend_names: ["webdav", "git", "rclone-s3"],
  age_available: true,
  profiles: ["default", "is"],
  sync_configured: true,
  history_count: 7,
  policy_level: "STRICT",
};

function renderFleet() {
  return render(
    <ToastProvider>
      <Fleet />
    </ToastProvider>,
  );
}

describe("Fleet page (Fleet konsolu)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: FLEET_STATUS });
  });

  it("loads fleet.status on mount", async () => {
    renderFleet();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "fleet.status" }),
      ),
    );
  });

  it("renders backend names and policy after load", async () => {
    renderFleet();
    await vi.waitFor(() =>
      expect(screen.getByText("webdav")).toBeInTheDocument(),
    );
    expect(screen.getByText("git")).toBeInTheDocument();
    expect(screen.getByText("rclone-s3")).toBeInTheDocument();
    expect(screen.getAllByText("STRICT").length).toBeGreaterThan(0);
  });

  it("shows profiles and history count", async () => {
    renderFleet();
    await vi.waitFor(() =>
      expect(screen.getByText(/default, is/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/7 gecmis kayit/)).toBeInTheDocument();
  });

  it("calls sync.push when Push clicked", async () => {
    renderFleet();
    fireEvent.click(screen.getByText("Push"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.push" }),
      ),
    );
  });

  it("calls sync.export when Yedek Export clicked", async () => {
    renderFleet();
    fireEvent.click(screen.getByText("Yedek Export"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.export" }),
      ),
    );
  });
});
