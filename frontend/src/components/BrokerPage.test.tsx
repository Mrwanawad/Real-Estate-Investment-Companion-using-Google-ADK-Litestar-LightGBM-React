import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import BrokerPage from "./BrokerPage";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("BrokerPage", () => {
  it("shows a message on 401", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response("{}", { status: 401 })));
    vi.stubGlobal("fetch", fetchMock);
    render(<BrokerPage />);
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: "Load leads" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid API key (401).");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/broker/leads",
      expect.objectContaining({ headers: { "X-API-Key": "bad" } }),
    );
  });
});
