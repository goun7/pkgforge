import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SidecarGuard } from "../SidecarGuard";
import { ToastProvider } from "../ui/Toast";

describe("SidecarGuard (Faz 10 1.7)", () => {
  it("renders nothing of its own and subscribes without crashing", () => {
    const { container } = render(
      <ToastProvider>
        <SidecarGuard />
      </ToastProvider>,
    );
    expect(container.textContent).toBe("");
  });
});
