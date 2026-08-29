import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Topbar } from "../Topbar";
import { call } from "../../lib/rpc";

describe("Topbar", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: {}, error: null });
  });

  it("renders the page title and subtitle", () => {
    render(<Topbar title="Dönüştür" subtitle="Linux paketlerini Arch için dönüştürün" />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Dönüştür" })).toBeInTheDocument();
    expect(screen.getByText("Linux paketlerini Arch için dönüştürün")).toBeInTheDocument();
    // Henuz RPC aktivitesi yok: cizgi gizli.
    expect(document.querySelector(".rpc-activity")).toBeNull();
  });

  it("omits the subtitle line when no subtitle is given", () => {
    const { container } = render(<Topbar title="Dönüştür" />);
    expect(container.querySelector("p")).toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "Dönüştür" })).toBeInTheDocument();
  });

  it("renders the search button with shortcut hint and fires onSearchClick", () => {
    const onSearchClick = vi.fn();
    render(<Topbar title="X" onSearchClick={onSearchClick} />);
    const btn = screen.getByRole("button", { name: "Ara" });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent("Ara…");
    expect(btn).toHaveTextContent("⌘K");
    fireEvent.click(btn);
    expect(onSearchClick).toHaveBeenCalledTimes(1);
  });

  it("does not render the search button without onSearchClick", () => {
    render(<Topbar title="X" />);
    expect(screen.queryByRole("button", { name: "Ara" })).toBeNull();
  });

  it("renders the right slot content", () => {
    render(<Topbar title="X" right={<div data-testid="right-slot">sağ blok</div>} />);
    expect(screen.getByTestId("right-slot")).toBeInTheDocument();
    expect(screen.getByText("sağ blok")).toBeInTheDocument();
  });

  it("shows the RPC activity line while a call is in flight and hides it after", async () => {
    let resolveInvoke!: (v: unknown) => void;
    invokeMock.mockImplementationOnce(
      () =>
        new Promise((res) => {
          resolveInvoke = res;
        }),
    );
    render(<Topbar title="X" />);
    expect(document.querySelector(".rpc-activity")).toBeNull();
    let pending!: Promise<unknown>;
    act(() => {
      pending = call("pkg.list");
    });
    await waitFor(() => expect(document.querySelector(".rpc-activity")).not.toBeNull());
    await act(async () => {
      resolveInvoke({ jsonrpc: "2.0", id: 1, result: {}, error: null });
      await pending;
    });
    await waitFor(() => expect(document.querySelector(".rpc-activity")).toBeNull());
  });

  it("clears the RPC activity line when an in-flight call fails", async () => {
    let rejectInvoke!: (e: Error) => void;
    invokeMock.mockImplementationOnce(
      () =>
        new Promise((_res, rej) => {
          rejectInvoke = rej;
        }),
    );
    render(<Topbar title="X" />);
    let pending!: Promise<unknown>;
    act(() => {
      pending = call("pkg.fail");
    });
    await waitFor(() => expect(document.querySelector(".rpc-activity")).not.toBeNull());
    await act(async () => {
      rejectInvoke(new Error("boom"));
      await expect(pending).rejects.toThrow("boom");
    });
    await waitFor(() => expect(document.querySelector(".rpc-activity")).toBeNull());
  });
});
