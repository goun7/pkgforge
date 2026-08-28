import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { FeatureTour } from "../FeatureTour";

function openTour() {
  act(() => {
    window.dispatchEvent(new Event("pkgforge:open-tour"));
  });
}

describe("FeatureTour (Faz 10 1.8)", () => {
  it("is hidden until the open-tour event fires", () => {
    render(<FeatureTour />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    openTour();
    expect(screen.getByText("Özellik Turu")).toBeInTheDocument();
  });

  it("advances through steps with the next button", async () => {
    const user = userEvent.setup();
    render(<FeatureTour />);
    openTour();
    expect(screen.getByText(/1 \/ 4/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "İleri" }));
    expect(screen.getByText(/2 \/ 4/)).toBeInTheDocument();
  });
});
