import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost, MODES, STATE_META } from "./api.js";

describe("api helpers", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("apiGet returns JSON on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ state: "idle" }),
      }),
    );
    await expect(apiGet("/status")).resolves.toEqual({ state: "idle" });
  });

  it("apiGet throws response text on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        text: async () => "nope",
      }),
    );
    await expect(apiGet("/status")).rejects.toThrow("nope");
  });

  it("apiPost sends JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiPost("/jargon", { term: "deploy" })).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/jargon"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ term: "deploy" }),
      }),
    );
  });
});

describe("status metadata", () => {
  it("exposes labels for known states and modes", () => {
    expect(STATE_META.idle.label).toBeTruthy();
    expect(STATE_META.listening.pulse).toBe(true);
    expect(MODES.map((m) => m.id)).toEqual(expect.arrayContaining(["normal", "meeting"]));
  });
});
