import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StepIndicator, PIPELINE_STEPS } from "../StepIndicator";

describe("StepIndicator", () => {
  it("renders all pipeline steps", () => {
    render(<StepIndicator statuses={{}} />);
    for (const step of PIPELINE_STEPS) {
      expect(screen.getByTestId(`step-${step}`)).toBeInTheDocument();
    }
  });

  it("marks a running step with the running status", () => {
    render(<StepIndicator statuses={{ conversion: "running" }} />);
    const el = screen.getByTestId("step-conversion");
    expect(el).toHaveAttribute("data-status", "running");
  });

  it("marks done and error steps", () => {
    render(
      <StepIndicator statuses={{ security: "done", analysis: "error" }} />,
    );
    expect(screen.getByTestId("step-security")).toHaveAttribute("data-status", "done");
    expect(screen.getByTestId("step-analysis")).toHaveAttribute("data-status", "error");
  });
});
