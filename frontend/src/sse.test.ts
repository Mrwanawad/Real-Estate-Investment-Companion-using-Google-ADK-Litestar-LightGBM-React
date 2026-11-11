import { describe, expect, it } from "vitest";

import { parseSse } from "./sse";

describe("parseSse", () => {
  it("parses complete events and keeps the remainder", () => {
    const { events, rest } = parseSse('event: delta\ndata: {"text":"a"}\n\nevent: do');
    expect(events).toEqual([{ event: "delta", data: '{"text":"a"}' }]);
    expect(rest).toBe("event: do");
  });

  it("handles chunks split mid-line", () => {
    const chunks = ["event: del", 'ta\ndata: {"te', 'xt":"hi"}\n', "\nevent: done\ndata: {}\r\n\r\n"];
    let buf = "";
    const all: { event: string; data: string }[] = [];
    for (const c of chunks) {
      const r = parseSse(buf + c);
      all.push(...r.events);
      buf = r.rest;
    }
    expect(all).toEqual([
      { event: "delta", data: '{"text":"hi"}' },
      { event: "done", data: "{}" },
    ]);
    expect(buf).toBe("");
  });

  it("ignores comments", () => {
    expect(parseSse(": ping\n\n").events).toEqual([]);
  });
});
