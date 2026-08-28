import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, afterEach } from "vitest";
import { ErrorBoundary } from "../ErrorBoundary";

let shouldThrow = true;
function MaybeBoom() {
  if (shouldThrow) throw new Error("test crash");
  return <div>recovered</div>;
}

describe("ErrorBoundary (Faz 9 4.5)", () => {
  afterEach(() => {
    shouldThrow = true;
    vi.restoreAllMocks();
  });

  it("renders children when there is no error", () => {
    shouldThrow = false;
    render(
      <ErrorBoundary>
        <div>child ok</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("child ok")).toBeInTheDocument();
  });

  it("catches a render error and shows the message (full variant)", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <MaybeBoom />
      </ErrorBoundary>,
    );
    expect(screen.getByText("test crash")).toBeInTheDocument();
  });

  it("page variant shows the error and recovers on retry", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();
    render(
      <ErrorBoundary variant="page">
        <MaybeBoom />
      </ErrorBoundary>,
    );
    expect(screen.getByText("test crash")).toBeInTheDocument();
    shouldThrow = false;
    await user.click(screen.getByRole("button"));
    expect(screen.getByText("recovered")).toBeInTheDocument();
  });
});
