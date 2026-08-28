import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

import { TopbarActions } from "../TopbarActions";

describe("TopbarActions (Faz 10 1.2)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ result: {}, error: null });
  });

  it("renders shortcuts, language, and theme buttons", async () => {
    render(<TopbarActions />);
    expect(await screen.findByLabelText("Dili değiştir")).toBeInTheDocument();
    expect(screen.getByLabelText("Temayı değiştir")).toBeInTheDocument();
    expect(screen.getByLabelText("Klavye Kısayolları")).toBeInTheDocument();
  });

  it("shows the sidecar online indicator after a successful ping", async () => {
    render(<TopbarActions />);
    expect(await screen.findByLabelText("Sidecar bağlı")).toBeInTheDocument();
  });
});
