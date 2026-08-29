import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PathPicker } from "../PathPicker";

describe("PathPicker — Faz 19 kapsam dalları", () => {
  it("boş seçim onChange çağırmaz (iptal)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const browse = vi.fn().mockResolvedValue([]);
    render(<PathPicker value="" onChange={onChange} browse={browse} />);
    await user.click(screen.getByRole("button"));
    expect(browse).toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("multiple=true seçimleri virgülle birleştirir", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const browse = vi.fn().mockResolvedValue(["/a.deb", "/b.rpm"]);
    render(<PathPicker value="" onChange={onChange} browse={browse} multiple />);
    await user.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledWith("/a.deb,/b.rpm");
  });

  it("disabled iken Seç butonu tıklanamaz ve browse çağrılmaz", () => {
    const browse = vi.fn();
    render(<PathPicker value="" onChange={() => {}} browse={browse} disabled />);
    expect(screen.getByRole("button")).toBeDisabled();
    fireEvent.click(screen.getByRole("button"));
    expect(browse).not.toHaveBeenCalled();
  });

  it("dir modunda klasör ikonu ve aynı onChange akışı çalışır", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const browse = vi.fn().mockResolvedValue(["/home/user/cikti"]);
    render(
      <PathPicker value="" onChange={onChange} browse={browse} mode="dir" multiple={false} />,
    );
    await user.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledWith("/home/user/cikti");
  });

  it("boş string dönen yol filtrelenir", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const browse = vi.fn().mockResolvedValue(["", "/gecerli.pkg"]);
    render(<PathPicker value="" onChange={onChange} browse={browse} />);
    await user.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledWith("/gecerli.pkg");
  });

  it("çift tık koruması: browse reddederse busy kilidi düşer ve tekrar çalışır", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    let calls = 0;
    const browse = vi.fn().mockImplementation(() => {
      calls += 1;
      if (calls === 1) return Promise.reject(new Error("dialog patladi"));
      return Promise.resolve(["/ikinci.pkg"]);
    });
    render(<PathPicker value="" onChange={onChange} browse={browse} />);
    // İlk çağrı reddeder — busy kilidi finally ile düşmeli.
    await user.click(screen.getByRole("button"));
    await user.click(screen.getByRole("button"));
    await vi.waitFor(() => expect(onChange).toHaveBeenCalledWith("/ikinci.pkg"));
  });
});
