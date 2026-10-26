import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { adminApi, ApiError, getCsrfToken, setCsrfToken } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import { ErrorBoundary } from "../components/ErrorBoundary";
import type { StaffUser } from "../types";

const mockSuperadmin: StaffUser = {
  id: 1,
  telegram_id: 100001,
  phone: "+998901234567",
  username: "super_boss",
  first_name: "Super",
  last_name: "Admin",
  roles: ["superadmin"],
  permissions: [
    "dashboard.view",
    "properties.view",
    "properties.moderate",
    "properties.archive",
    "properties.create",
    "users.view",
    "users.manage_roles",
    "brokers.view",
    "brokers.manage",
    "leads.view",
    "leads.assign",
    "leads.change_stage",
    "leads.add_note",
    "viewings.view",
    "viewings.manage",
    "crm.view",
    "crm.retry",
    "ai.view_safe_metrics",
    "audit.view",
    "kaizen.view",
    "kaizen.manage",
    "kaizen.generate",
  ],
  csrf_token: "csrf_initial_super_token",
};

function changeInputValue(input: HTMLInputElement, value: string) {
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value"
  )?.set;
  nativeSetter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("UyAI Admin Authentication V2 & Session Stabilization", () => {
  let container: HTMLDivElement | null = null;
  let root: Root | null = null;

  beforeEach(() => {
    setCsrfToken(null);
    vi.restoreAllMocks();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    window.history.replaceState({}, "", "/");
  });

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount();
      });
    }
    if (container && container.parentNode) {
      container.parentNode.removeChild(container);
    }
    container = null;
    root = null;
    setCsrfToken(null);
  });

  // 1. Initial auth checking state
  it("Scenario 1: Initial auth checking state renders session check indicator without flicker", async () => {
    let resolveGetMe: (value: StaffUser) => void = () => {};
    const pendingPromise = new Promise<StaffUser>((resolve) => {
      resolveGetMe = resolve;
    });
    vi.spyOn(adminApi, "getMe").mockReturnValue(pendingPromise);

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    const checkingEl = container?.querySelector('[data-testid="auth-checking"]');
    expect(checkingEl).not.toBeNull();
    expect(checkingEl?.textContent).toContain("Sessiya tekshirilmoqda...");
    expect(container?.querySelector('[data-testid="username-input"]')).toBeNull();

    // Resolve the promise
    await act(async () => {
      resolveGetMe(mockSuperadmin);
    });
  });

  // 2. /auth/me -> 200 (authenticated)
  it("Scenario 2: /auth/me -> 200 transitions to authenticated and renders dashboard", async () => {
    vi.spyOn(adminApi, "getMe").mockResolvedValue(mockSuperadmin);

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    expect(container?.querySelector('[data-testid="auth-checking"]')).toBeNull();
    expect(container?.textContent).toContain("UyAI Admin");
    expect(getCsrfToken()).toBe("csrf_initial_super_token");
  });

  // 3. /auth/me -> 401 (unauthenticated)
  it("Scenario 3: /auth/me -> 401 transitions cleanly to unauthenticated and renders login page", async () => {
    vi.spyOn(adminApi, "getMe").mockRejectedValue(new ApiError("Unauthorized", 401));

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    expect(container?.querySelector('[data-testid="auth-checking"]')).toBeNull();
    expect(container?.querySelector('[data-testid="username-input"]')).not.toBeNull();
    expect(container?.querySelector('[data-testid="password-input"]')).not.toBeNull();
    expect(container?.querySelector('[data-testid="login-submit"]')).not.toBeNull();
  });

  // 4. Login success flow
  it("Scenario 4: Login success canonically verifies session via /auth/me and navigates to dashboard", async () => {
    vi.spyOn(adminApi, "getMe")
      .mockRejectedValueOnce(new ApiError("Unauthorized", 401)) // initial load
      .mockResolvedValueOnce(mockSuperadmin); // canonical check after login

    vi.spyOn(adminApi, "login").mockResolvedValue({
      user: mockSuperadmin,
      csrf_token: "csrf_after_login",
    });

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    const userInput = container?.querySelector('[data-testid="username-input"]') as HTMLInputElement;
    const passInput = container?.querySelector('[data-testid="password-input"]') as HTMLInputElement;
    const submitBtn = container?.querySelector('[data-testid="login-submit"]') as HTMLButtonElement;

    await act(async () => {
      changeInputValue(userInput, "super_boss");
      changeInputValue(passInput, "Password123!");
    });

    await act(async () => {
      submitBtn.click();
    });

    expect(adminApi.login).toHaveBeenCalledWith("super_boss", "Password123!");
    expect(adminApi.getMe).toHaveBeenCalledTimes(2); // Initial check + canonical verification
    expect(container?.textContent).toContain("UyAI Admin");
  });

  // 5. Wrong credentials failure
  it("Scenario 5: Wrong credentials renders generic error without crash and keeps login page open", async () => {
    vi.spyOn(adminApi, "getMe").mockRejectedValue(new ApiError("Unauthorized", 401));
    vi.spyOn(adminApi, "login").mockRejectedValue(new ApiError("Login yoki parol noto‘g‘ri.", 401));

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    const userInput = container?.querySelector('[data-testid="username-input"]') as HTMLInputElement;
    const passInput = container?.querySelector('[data-testid="password-input"]') as HTMLInputElement;
    const submitBtn = container?.querySelector('[data-testid="login-submit"]') as HTMLButtonElement;

    await act(async () => {
      changeInputValue(userInput, "wrong_user");
      changeInputValue(passInput, "WrongPassword!");
    });

    await act(async () => {
      submitBtn.click();
    });

    const errorEl = container?.querySelector('[data-testid="login-error"]');
    expect(errorEl).not.toBeNull();
    expect(errorEl?.textContent).toContain("Login yoki parol noto‘g‘ri.");
    expect(container?.querySelector('[data-testid="username-input"]')).not.toBeNull();
  });

  // 6. Backend unavailable / network failure
  it("Scenario 6: Backend unavailable shows controlled error message with retry", async () => {
    vi.spyOn(adminApi, "getMe").mockRejectedValue(
      new ApiError("Server bilan bog‘lanib bo‘lmadi. Qayta urinib ko‘ring.", 0)
    );

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    const errorBox = container?.querySelector('[data-testid="auth-error"]');
    expect(errorBox).not.toBeNull();
    expect(errorBox?.textContent).toContain("Server bilan bog‘lanib bo‘lmadi");

    const retryBtn = container?.querySelector('[data-testid="auth-retry-btn"]') as HTMLButtonElement;
    expect(retryBtn).not.toBeNull();

    // Now server comes back online
    vi.spyOn(adminApi, "getMe").mockResolvedValue(mockSuperadmin);
    await act(async () => {
      retryBtn.click();
    });

    expect(container?.textContent).toContain("UyAI Admin");
  });

  // 7. Login double-submit prevention
  it("Scenario 7: Prevents double submit and disables submit button during login request", async () => {
    vi.spyOn(adminApi, "getMe").mockRejectedValueOnce(new ApiError("Unauthorized", 401));

    let resolveLogin: (val: any) => void = () => {};
    const pendingLogin = new Promise<any>((resolve) => {
      resolveLogin = resolve;
    });
    vi.spyOn(adminApi, "login").mockReturnValue(pendingLogin);

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    const userInput = container?.querySelector('[data-testid="username-input"]') as HTMLInputElement;
    const passInput = container?.querySelector('[data-testid="password-input"]') as HTMLInputElement;
    const submitBtn = container?.querySelector('[data-testid="login-submit"]') as HTMLButtonElement;

    await act(async () => {
      changeInputValue(userInput, "admin_user");
      changeInputValue(passInput, "SecretPassword!");
    });

    await act(async () => {
      submitBtn.click();
    });

    // During in-flight request: button is disabled and shows loading text
    expect(submitBtn.disabled).toBe(true);
    expect(submitBtn.textContent).toContain("Kirilmoqda...");

    // Second click should be ignored
    await act(async () => {
      submitBtn.click();
    });
    expect(adminApi.login).toHaveBeenCalledTimes(1);

    // Clean up
    await act(async () => {
      resolveLogin({ user: mockSuperadmin, csrf_token: "tok" });
    });
  });

  // 8. Session expiry
  it("Scenario 8: Centralized 401 on protected request transitions state to expired and redirects to login with notice", async () => {
    vi.spyOn(adminApi, "getMe").mockResolvedValue(mockSuperadmin);

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    expect(container?.textContent).toContain("UyAI Admin");

    // Simulate mock fetch returning 401 on an API request
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Session revoked or expired." }),
    });
    vi.stubGlobal("fetch", mockFetch);

    // Any protected API call
    try {
      await adminApi.listBrokers();
    } catch {
      // Expected
    }

    // Wait for React state transition to expired
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    const noticeEl = container?.querySelector('[data-testid="login-notice"]');
    expect(noticeEl).not.toBeNull();
    expect(noticeEl?.textContent).toContain("Sessiya tugagan. Qayta kiring.");
    expect(container?.querySelector('[data-testid="username-input"]')).not.toBeNull();
  });

  // 9. Logout flow
  it("Scenario 9: Logout revokes session, clears credentials and redirects to login", async () => {
    vi.spyOn(adminApi, "getMe").mockResolvedValue(mockSuperadmin);
    vi.spyOn(adminApi, "logout").mockResolvedValue();

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    const logoutBtn = container?.querySelector('[data-testid="logout-btn"]') as HTMLButtonElement;
    expect(logoutBtn).not.toBeNull();

    await act(async () => {
      logoutBtn.click();
    });

    expect(adminApi.logout).toHaveBeenCalledTimes(1);
    expect(getCsrfToken()).toBeNull();
    expect(container?.querySelector('[data-testid="username-input"]')).not.toBeNull();
  });

  // 10. 403 Permission handling
  it("Scenario 10: 403 Forbidden renders controlled unauthorized banner without logging out user", async () => {
    const brokerUser: StaffUser = {
      ...mockSuperadmin,
      roles: ["sales_broker"],
      permissions: ["dashboard.view"], // lacks users.view
    };
    vi.spyOn(adminApi, "getMe").mockResolvedValue(brokerUser);

    await act(async () => {
      window.history.replaceState({}, "", "/users");
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    const forbiddenBanner = container?.querySelector('[data-testid="forbidden-message"]');
    expect(forbiddenBanner).not.toBeNull();
    expect(forbiddenBanner?.textContent).toContain("Ruxsat berilmagan (403 Forbidden)");
    // User is still authenticated and sees sidebar
    expect(container?.textContent).toContain("UyAI Admin");
    expect(container?.querySelector('[data-testid="username-input"]')).toBeNull();
  });

  // 11. CSRF failure handling
  it("Scenario 11: CSRF failure on mutating request refreshes token from /auth/me and retries once", async () => {
    setCsrfToken("old_csrf_expired");

    let callCount = 0;
    const mockFetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/admin/v1/properties/42/approve") {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve({
            ok: false,
            status: 403,
            headers: new Headers({ "content-type": "application/json" }),
            json: async () => ({ detail: "Invalid or missing CSRF token." }),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ status: "ok", message: "Approved successfully" }),
        });
      }
      if (url === "/api/admin/v1/auth/me") {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ ...mockSuperadmin, csrf_token: "refreshed_csrf_token" }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    vi.stubGlobal("fetch", mockFetch);

    const result = await adminApi.approveProperty(42);
    expect(result).toEqual({ status: "ok", message: "Approved successfully" });
    expect(callCount).toBe(2);
    expect(getCsrfToken()).toBe("refreshed_csrf_token");
  });

  // 12. Authenticated /login access
  it("Scenario 12: Authenticated user attempting to access /login redirects to /dashboard", async () => {
    vi.spyOn(adminApi, "getMe").mockResolvedValue(mockSuperadmin);
    window.history.replaceState({}, "", "/login");

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    expect(window.location.pathname).toBe("/dashboard");
    expect(container?.textContent).toContain("UyAI Admin");
  });

  // 13. Protected route refresh preservation
  it("Scenario 13: Browser refresh on protected route (/brokers) preserves route when authenticated", async () => {
    vi.spyOn(adminApi, "getMe").mockResolvedValue(mockSuperadmin);
    vi.spyOn(adminApi, "listBrokers").mockResolvedValue([]);
    window.history.replaceState({}, "", "/brokers");

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    expect(window.location.pathname).toBe("/brokers");
    expect(container?.textContent).toContain("Brokerlar va Ish Yuklamasi");
    expect(container?.querySelector('[data-testid="username-input"]')).toBeNull();
  });

  // 14. Error Boundary resilience
  it("Scenario 14: Error Boundary catches unexpected child rendering exceptions and displays localized recovery UI", async () => {
    const CrashingChild: React.FC = () => {
      throw new Error("Simulated rendering explosion in broken widget");
    };

    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    await act(async () => {
      root?.render(
        <ErrorBoundary>
          <CrashingChild />
        </ErrorBoundary>
      );
    });

    const errorContainer = container?.querySelector('[data-testid="error-boundary-fallback"]');
    expect(errorContainer).not.toBeNull();
    expect(errorContainer?.textContent).toContain("kutilmagan xatolik yuz berdi");
    expect(container?.querySelector('[data-testid="error-boundary-retry"]')).not.toBeNull();

    consoleError.mockRestore();
  });

  // 15. Brokers navigation after login
  it("Scenario 15: Brokers navigation after login functions smoothly without blank page", async () => {
    vi.spyOn(adminApi, "getMe")
      .mockRejectedValueOnce(new ApiError("Unauthorized", 401)) // initial load
      .mockResolvedValueOnce(mockSuperadmin); // canonical check after login

    vi.spyOn(adminApi, "login").mockResolvedValue({
      user: mockSuperadmin,
      csrf_token: "csrf_after_login",
    });

    vi.spyOn(adminApi, "listBrokers").mockResolvedValue([
      {
        id: 7,
        full_name: "Ali Valiyev",
        role: "sales_broker",
        roles: ["sales_broker"],
        phone_masked: "+998 90 *** ** 11",
        active_leads_count: 5,
        pending_viewings_count: 2,
        viewings_count: 2,
        won_leads_count: 1,
        lost_leads_count: 0,
      },
    ]);

    await act(async () => {
      root?.render(
        <AuthProvider>
          <App />
        </AuthProvider>
      );
    });

    // 1. Submit login
    const userInput = container?.querySelector('[data-testid="username-input"]') as HTMLInputElement;
    const passInput = container?.querySelector('[data-testid="password-input"]') as HTMLInputElement;
    const submitBtn = container?.querySelector('[data-testid="login-submit"]') as HTMLButtonElement;

    await act(async () => {
      changeInputValue(userInput, "super_boss");
      changeInputValue(passInput, "Password123!");
    });

    await act(async () => {
      submitBtn.click();
    });

    // Now on Dashboard
    expect(container?.textContent).toContain("UyAI Admin");

    // 2. Navigate to Brokers tab
    const brokersTabBtn = container?.querySelector('[data-testid="nav-brokers"]') as HTMLButtonElement;
    expect(brokersTabBtn).not.toBeNull();

    await act(async () => {
      brokersTabBtn.click();
    });

    // 3. Verify Brokers page rendered without blank page
    expect(container?.textContent).toContain("Ali Valiyev");
    expect(container?.textContent).toContain("+998 90 *** ** 11");
    expect(window.location.pathname).toBe("/brokers");
  });
});
