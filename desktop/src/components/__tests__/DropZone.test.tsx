import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DropZone } from "../DropZone";

function makeFile(name: string): File {
  return new File(["x"], name, { type: "application/octet-stream" });
}

describe("DropZone", () => {
  it("renders the drop hint", () => {
    render(<DropZone onFiles={() => {}} />);
    expect(screen.getByRole("button", { name: "drop-zone" })).toBeInTheDocument();
  });

  it("accepts dropped .deb files", () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} />);
    const zone = screen.getByRole("button", { name: "drop-zone" });
    fireEvent.drop(zone, {
      dataTransfer: { files: [makeFile("pkg_1.0_amd64.deb")] },
    });
    expect(onFiles).toHaveBeenCalledTimes(1);
    expect(onFiles.mock.calls[0][0][0].name).toBe("pkg_1.0_amd64.deb");
  });

  it("filters out non-package files", () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} />);
    const zone = screen.getByRole("button", { name: "drop-zone" });
    fireEvent.drop(zone, {
      dataTransfer: { files: [makeFile("readme.txt")] },
    });
    expect(onFiles).not.toHaveBeenCalled();
  });

  it("ignores drops when disabled", () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} disabled />);
    const zone = screen.getByRole("button", { name: "drop-zone" });
    fireEvent.drop(zone, {
      dataTransfer: { files: [makeFile("pkg.deb")] },
    });
    expect(onFiles).not.toHaveBeenCalled();
  });
});
