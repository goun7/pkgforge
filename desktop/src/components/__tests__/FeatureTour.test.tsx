import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { FeatureTour } from "../FeatureTour";

function openTour() {
  act(() => {
    window.dispatchEvent(new Event("pkgforge:open-tour"));
  });
}

/** Nokta navigasyonu: aktif adim noktasi genis (w-5) sinifindan taninir. */
function dotStates(container: HTMLElement): { total: number; active: number } {
  const dots = Array.from(container.querySelectorAll("span.rounded-full"));
  return { total: dots.length, active: dots.findIndex((d) => d.className.includes("w-5")) };
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

  it("shows the current step title, description and counter", () => {
    render(<FeatureTour />);
    openTour();
    expect(screen.getByText("Güvenlik ve Köken Doğrulama")).toBeInTheDocument();
    expect(screen.getByText(/Güvenlik sayfasında SBOM/)).toBeInTheDocument();
    expect(screen.getByText(/1 \/ 4/)).toBeInTheDocument();
  });

  it("has no prev button on the first step and goes back afterwards", async () => {
    const user = userEvent.setup();
    render(<FeatureTour />);
    openTour();
    expect(screen.queryByRole("button", { name: "Geri" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "İleri" }));
    expect(screen.getByText(/2 \/ 4/)).toBeInTheDocument();
    expect(screen.getByText("Fleet: Çoklu Makine")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Geri" }));
    expect(screen.getByText(/1 \/ 4/)).toBeInTheDocument();
    expect(screen.getByText("Güvenlik ve Köken Doğrulama")).toBeInTheDocument();
  });

  it("shows Bitir on the last step and closes the dialog", async () => {
    const user = userEvent.setup();
    render(<FeatureTour />);
    openTour();
    for (let i = 0; i < 3; i++) {
      await user.click(screen.getByRole("button", { name: "İleri" }));
    }
    expect(screen.getByText(/4 \/ 4/)).toBeInTheDocument();
    expect(screen.getByText("Komut Paleti")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "İleri" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Bitir" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("skip closes the tour", async () => {
    const user = userEvent.setup();
    render(<FeatureTour />);
    openTour();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Atla" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("moves the active dot with the step", async () => {
    const user = userEvent.setup();
    const { container } = render(<FeatureTour />);
    openTour();
    expect(dotStates(container)).toEqual({ total: 4, active: 0 });
    await user.click(screen.getByRole("button", { name: "İleri" }));
    expect(dotStates(container)).toEqual({ total: 4, active: 1 });
    await user.click(screen.getByRole("button", { name: "İleri" }));
    expect(dotStates(container)).toEqual({ total: 4, active: 2 });
  });

  it("reopening the tour resets to the first step", async () => {
    const user = userEvent.setup();
    render(<FeatureTour />);
    openTour();
    await user.click(screen.getByRole("button", { name: "İleri" }));
    expect(screen.getByText(/2 \/ 4/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Atla" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    openTour();
    expect(screen.getByText(/1 \/ 4/)).toBeInTheDocument();
    expect(screen.getByText("Güvenlik ve Köken Doğrulama")).toBeInTheDocument();
  });
});
