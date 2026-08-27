import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.resetModules();
  sessionStorage.clear();
  document.cookie = "quant_home_csrf=; Max-Age=0; path=/";
});

it("refreshes a stale CSRF token and retries a state-changing request once", async () => {
  sessionStorage.setItem("quant-home-csrf", "stale-token");
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Invalid CSRF token" }), {
      status: 403, headers: { "Content-Type": "application/json" },
    }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "fresh-token" }), {
      status: 200, headers: { "Content-Type": "application/json" },
    }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: "configuration-1" }), {
      status: 200, headers: { "Content-Type": "application/json" },
    }));
  vi.stubGlobal("fetch", fetchMock);
  const { request } = await import("./client");

  const result = await request<{ id: string }>("/configurations", {
    method: "POST", body: JSON.stringify({ name: "test" }),
  });

  expect(result).toEqual({ id: "configuration-1" });
  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(fetchMock.mock.calls[1][0]).toBe("/api/auth/csrf");
  const retriedHeaders = fetchMock.mock.calls[2][1]?.headers as Headers;
  expect(retriedHeaders.get("X-CSRF-Token")).toBe("fresh-token");
});
