import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QueueList, type QueueItem } from "../QueueList";

const items: QueueItem[] = [
  { id: "1", name: "a_1.0.deb", status: "pending" },
  { id: "2", name: "b_2.0.rpm", status: "running", progress: 40 },
  { id: "3", name: "c_3.0.deb", status: "success" },
];

describe("QueueList", () => {
  it("shows empty message when no items", () => {
    render(<QueueList items={[]} />);
    expect(screen.getByText("Kuyruk boş")).toBeInTheDocument();
  });

  it("renders each item name and status", () => {
    render(<QueueList items={items} />);
    expect(screen.getByText("a_1.0.deb")).toBeInTheDocument();
    expect(screen.getByText("b_2.0.rpm")).toBeInTheDocument();
    expect(screen.getByText("Başarılı")).toBeInTheDocument();
  });

  it("calls onRemove for pending items only", () => {
    const onRemove = vi.fn();
    render(<QueueList items={items} onRemove={onRemove} />);
    const removeBtn = screen.getByLabelText("Kaldır a_1.0.deb");
    fireEvent.click(removeBtn);
    expect(onRemove).toHaveBeenCalledWith("1");
    expect(screen.queryByLabelText("Kaldır b_2.0.rpm")).not.toBeInTheDocument();
  });
});
