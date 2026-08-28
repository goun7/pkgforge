import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

import { DoctorPanel } from "../DoctorPanel";
import { ToastProvider } from "../ui/Toast";

const doctorReport = {
  version: "2.0.0",
  ok: true,
  tools: { ok: true, missing_required: [], missing_optional: [], debtap: true, pkexec: true, distrobox: false },
  keyring: { ok: true },
  storage: { ok: true, profile: "default" },
  dbus: { ok: true },
  scheduler: { ok: true, tasks: 0 },
};

describe("DoctorPanel (Faz 10 1.1)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ result: doctorReport, error: null });
  });

  it("runs diagnostics and shows the report", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <DoctorPanel />
      </ToastProvider>,
    );
    expect(screen.getByText("Sistem Doktoru")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByText(/2\.0\.0/)).toBeInTheDocument();
  });

  it("offers a copy-diagnostics button once a report exists", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <DoctorPanel />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByRole("button", { name: /Tanıyı kopyala/ })).toBeInTheDocument();
  });
});
