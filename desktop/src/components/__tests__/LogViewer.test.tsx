import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LogViewer } from "../LogViewer";

describe("LogViewer", () => {
  it("shows placeholder when empty", () => {
    render(<LogViewer lines={[]} />);
    expect(screen.getByText(/Henüz log yok/)).toBeInTheDocument();
  });

  it("renders log lines", () => {
    render(
      <LogViewer
        lines={[
          { message: "Pipeline başlatıldı", level: "info" },
          { message: "Hata oluştu", level: "error" },
        ]}
      />,
    );
    expect(screen.getByText("Pipeline başlatıldı")).toBeInTheDocument();
    expect(screen.getByText("Hata oluştu")).toBeInTheDocument();
  });
});
