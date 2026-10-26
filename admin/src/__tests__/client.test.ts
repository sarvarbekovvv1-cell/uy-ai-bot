import { describe, expect, it, vi, beforeEach } from "vitest";
import { adminApi, ApiError, getCsrfToken, setCsrfToken } from "../api/client";

describe("Admin API Client", () => {
  beforeEach(() => {
    setCsrfToken(null);
    vi.restoreAllMocks();
  });

  it("stores and retrieves CSRF token in memory", () => {
    expect(getCsrfToken()).toBeNull();
    setCsrfToken("csrf_token_abc_123");
    expect(getCsrfToken()).toBe("csrf_token_abc_123");
    setCsrfToken(null);
    expect(getCsrfToken()).toBeNull();
  });

  it("injects X-CSRF-Token on mutating POST requests", async () => {
    setCsrfToken("active_csrf_secret");

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ status: "ok", message: "Approved" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await adminApi.approveProperty(42);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [path, init] = mockFetch.mock.calls[0];
    expect(path).toBe("/api/admin/v1/properties/42/approve");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    const headers = init.headers as Headers;
    expect(headers.get("X-CSRF-Token")).toBe("active_csrf_secret");
  });

  it("extracts detail message into ApiError on failed responses", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Invalid rejection reason." }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(adminApi.rejectProperty(10, "short")).rejects.toThrow(ApiError);
    await expect(adminApi.rejectProperty(10, "short")).rejects.toThrow("Invalid rejection reason.");
  });

  it("clears CSRF token on 401 Unauthorized response", async () => {
    setCsrfToken("existing_token");

    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Session expired." }),
    });
    vi.stubGlobal("fetch", mockFetch);

    try {
      await adminApi.getMe();
    } catch {
      // Expected
    }

    expect(getCsrfToken()).toBeNull();
  });

  it("sends PATCH /api/admin/v1/auth/username with new_username", async () => {
    setCsrfToken("csrf_token_test");

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ id: 1, username: "new_superadmin", roles: ["superadmin"], permissions: [] }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const res = await adminApi.updateUsername("new_superadmin");
    expect(res.username).toBe("new_superadmin");

    const [path, init] = mockFetch.mock.calls[0];
    expect(path).toBe("/api/admin/v1/auth/username");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ new_username: "new_superadmin" });
  });

  it("sends POST /api/admin/v1/auth/password with current and new passwords", async () => {
    setCsrfToken("csrf_token_pass");

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ status: "ok", message: "Password updated" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const res = await adminApi.updatePassword("OldPass123!", "NewPass123!", "NewPass123!");
    expect(res.status).toBe("ok");

    const [path, init] = mockFetch.mock.calls[0];
    expect(path).toBe("/api/admin/v1/auth/password");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      current_password: "OldPass123!",
      new_password: "NewPass123!",
      new_password_confirm: "NewPass123!",
    });
  });
});
