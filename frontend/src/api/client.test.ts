import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch } from "./client";

function mockFetch(body: string, init: { status?: number } = {}) {
  const status = init.status ?? 200;
  const res = new Response(body, { status });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(res));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("parses a JSON body on 200", async () => {
    mockFetch(JSON.stringify({ hello: "world" }));
    await expect(apiFetch<{ hello: string }>("/api/x")).resolves.toEqual({
      hello: "world",
    });
  });

  it("returns null when the body is empty", async () => {
    mockFetch("");
    await expect(apiFetch("/api/x")).resolves.toBeNull();
  });

  it("returns the raw text when the body is not JSON", async () => {
    mockFetch("plain text");
    await expect(apiFetch("/api/x")).resolves.toBe("plain text");
  });

  it("throws ApiError carrying status and parsed body on non-2xx", async () => {
    mockFetch(JSON.stringify({ detail: "nope" }), { status: 404 });
    await expect(apiFetch("/api/x")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      body: { detail: "nope" },
    });
  });

  it("ApiError default message is HTTP <status>", () => {
    const err = new ApiError(500, null);
    expect(err.message).toBe("HTTP 500");
  });
});
