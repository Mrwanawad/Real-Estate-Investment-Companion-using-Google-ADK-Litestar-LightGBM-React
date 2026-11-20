import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import ChatPage from "./ChatPage";

const unit = {
  code: "U-1",
  project_name: "Palm Gardens",
  area_name: "New Cairo",
  type: "apartment",
  bedrooms: 2,
  bua_m2: 120,
  price_egp: 3000000,
  delivery_year: 2028,
  developer_tier: "A",
  score: 0.9,
  reasons: ["Within budget"],
};

function sse(parts: [string, unknown][]): string {
  return parts.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");
}

function streamOf(text: string, split: number): Response {
  const bytes = new TextEncoder().encode(text);
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(bytes.slice(0, split));
      c.enqueue(bytes.slice(split));
      c.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("ChatPage", () => {
  it("renders streamed text, a shortlist card and a citation", async () => {
    const body = sse([
      ["tool", { name: "search_units", status: "started" }],
      ["tool", { name: "search_units", status: "finished" }],
      ["delta", { text: "Here are **two** options." }],
      ["artifact", { kind: "shortlist", data: { units: [unit] } }],
      ["artifact", { kind: "citations", data: { items: [{ doc_id: "d1", title: "Buyer guide", snippet: "Fees apply." }] } }],
      ["done", {}],
    ]);
    const fetchMock = vi.fn((url: string) =>
      Promise.resolve(
        url.endsWith("/chat/sessions")
          ? new Response(JSON.stringify({ session_id: "s1" }), { status: 200 })
          : streamOf(body, 37),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ChatPage />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("two")).toBeInTheDocument();
    expect(await screen.findByText("Palm Gardens")).toBeInTheDocument();
    expect(await screen.findByText("Buyer guide")).toBeInTheDocument();
    expect(screen.getByText("Within budget")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/chat/sessions/s1/messages",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("restores a saved conversation and remembers new sessions", async () => {
    window.localStorage.setItem("reic.session.en", "saved-1");
    const fetchMock = vi.fn((url: string) =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            messages: [
              { role: "user", text: "my budget is 5M" },
              { role: "assistant", text: "Here is **one** unit.", artifacts: [{ kind: "shortlist", data: { units: [unit] } }] },
            ],
          }),
          { status: url.endsWith("/chat/sessions/saved-1") ? 200 : 404 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ChatPage />);
    expect(await screen.findByText("my budget is 5M")).toBeInTheDocument();
    expect(await screen.findByText("Palm Gardens")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(window.localStorage.getItem("reic.session.en")).toBeNull();
    expect(screen.queryByText("my budget is 5M")).not.toBeInTheDocument();
  });

  it("forgets a session the server no longer has", async () => {
    window.localStorage.setItem("reic.session.en", "gone");
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("{}", { status: 404 }))));
    render(<ChatPage />);
    await vi.waitFor(() => expect(window.localStorage.getItem("reic.session.en")).toBeNull());
  });
});
