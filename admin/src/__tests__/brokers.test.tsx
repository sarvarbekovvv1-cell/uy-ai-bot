import React, { act } from "react";
import ReactDOM from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { BrokersPage } from "../pages/BrokersPage";
import type { BrokerWorkloadItem } from "../types";

describe("Admin Brokers Page & ErrorBoundary Resilience", () => {
  let container: HTMLDivElement | null = null;
  let root: ReactDOM.Root | null = null;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = ReactDOM.createRoot(container);
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
    vi.restoreAllMocks();
  });

  // Test A: Broker API returns valid list -> BrokersPage renders table and rows
  it("Test A: renders brokers list successfully when API returns valid data", async () => {
    const mockBrokers: BrokerWorkloadItem[] = [
      {
        id: 10,
        telegram_id: 998877,
        full_name: "Aziz Rahimov",
        username: "aziz_broker",
        phone_masked: "+998 90 *** ** 12",
        roles: ["sales_broker"],
        active_leads_count: 5,
        pending_viewings_count: 2,
      },
    ];

    vi.spyOn(adminApi, "listBrokers").mockResolvedValue(mockBrokers);

    await act(async () => {
      root?.render(<BrokersPage />);
    });

    // Wait for microtasks
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    expect(container?.textContent).toContain("Aziz Rahimov");
    expect(container?.textContent).toContain("+998 90 *** ** 12");
    expect(container?.textContent).toContain("sales_broker");
    expect(container?.textContent).toContain("5");
    expect(container?.textContent).toContain("2");
  });

  // Test B: Broker list empty -> Empty state renders
  it("Test B: renders empty state when no brokers exist", async () => {
    vi.spyOn(adminApi, "listBrokers").mockResolvedValue([]);

    await act(async () => {
      root?.render(<BrokersPage />);
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    const emptyCell = container?.querySelector('[data-testid="brokers-empty-state"]');
    expect(emptyCell).not.toBeNull();
    expect(emptyCell?.textContent).toContain("Hozircha brokerlar mavjud emas.");
  });

  // Test C: Nullable broker fields -> No runtime crash, handles missing fields cleanly
  it("Test C: handles brokers with null or missing fields without throwing", async () => {
    const sparseBrokers: BrokerWorkloadItem[] = [
      {
        id: 25,
        full_name: null,
        first_name: null,
        last_name: null,
        username: "solitary_agent",
        phone_masked: null,
        roles: undefined,
        role: "rental_broker",
        active_leads_count: undefined,
        pending_viewings_count: undefined,
      },
    ];

    vi.spyOn(adminApi, "listBrokers").mockResolvedValue(sparseBrokers);

    await act(async () => {
      root?.render(<BrokersPage />);
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    // Does not crash, falls back safely
    expect(container?.textContent).toContain("@solitary_agent");
    expect(container?.textContent).toContain("rental_broker");
    expect(container?.textContent).toContain("—"); // masked phone fallback
  });

  // Test D: API failure -> Controlled error state renders with retry button
  it("Test D: renders controlled error state with retry button on API failure", async () => {
    vi.spyOn(adminApi, "listBrokers").mockRejectedValue(new Error("Network connection error"));

    await act(async () => {
      root?.render(<BrokersPage />);
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    const errorState = container?.querySelector('[data-testid="brokers-error-state"]');
    expect(errorState).not.toBeNull();
    expect(errorState?.textContent).toContain("Network connection error");
    expect(errorState?.querySelector("button")?.textContent).toBe("Qayta urinish");
  });

  // Test E: 403 Forbidden -> Controlled error message, no blank page
  it("Test E: renders permission denied error message on 403 response without blank page", async () => {
    const error403 = new Error("Forbidden");
    // @ts-expect-error attach status
    error403.status = 403;
    vi.spyOn(adminApi, "listBrokers").mockRejectedValue(error403);

    await act(async () => {
      root?.render(<BrokersPage />);
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    expect(container?.textContent).toContain("403 Forbidden");
    expect(container?.textContent).toContain("faqat rahbar yoki ruxsatli xodimlar uchun");
    expect(container?.innerHTML).not.toBe("");
  });

  // Test F: Missing optional stats do not crash
  it("Test F: renders default zeros when active_leads_count and pending_viewings_count are missing", async () => {
    const noStatsBroker: BrokerWorkloadItem[] = [
      {
        id: 30,
        full_name: "Botir Qodirov",
        username: "botir",
        phone_masked: "+998 91 123 45 67",
        roles: ["head_broker"],
      },
    ];

    vi.spyOn(adminApi, "listBrokers").mockResolvedValue(noStatsBroker);

    await act(async () => {
      root?.render(<BrokersPage />);
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    const row = container?.querySelector('[data-testid="broker-row-30"]');
    expect(row).not.toBeNull();
    expect(row?.textContent).toContain("Botir Qodirov");
    expect(row?.textContent).toContain("0"); // fallback count
  });

  // Test G: ErrorBoundary catches unhandled component crashes and prevents whole app blank screen
  it("Test G: ErrorBoundary catches unexpected rendering exception and shows recovery UI", () => {
    const BadComponent: React.FC = () => {
      throw new Error("Simulated component render explosion");
    };

    // Suppress console.error in vitest output for expected boundary catch
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    act(() => {
      root?.render(
        <ErrorBoundary>
          <BadComponent />
        </ErrorBoundary>
      );
    });

    const fallback = container?.querySelector('[data-testid="error-boundary-fallback"]');
    expect(fallback).not.toBeNull();
    expect(fallback?.textContent).toContain("Sahifada kutilmagan xatolik yuz berdi");
    expect(fallback?.textContent).toContain("Qayta urinish");

    consoleSpy.mockRestore();
  });
});
