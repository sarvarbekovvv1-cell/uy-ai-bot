import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ApiError } from "../api/client";

describe("api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("attaches Authorization and X-Telegram-Init-Data headers when present", async () => {
    // Mock getInitData by setting window.Telegram.WebApp.initData
    window.Telegram = {
      WebApp: {
        initData: "auth_date=123&hash=abc",
        initDataUnsafe: {},
        version: "7.0",
        platform: "ios",
        colorScheme: "light",
        themeParams: {},
        isExpanded: true,
        viewportHeight: 600,
        viewportStableHeight: 600,
        ready: () => {},
        expand: () => {},
        close: () => {},
        BackButton: { isVisible: false, show: () => {}, hide: () => {}, onClick: () => {}, offClick: () => {} },
        MainButton: {
          text: "",
          color: "",
          textColor: "",
          isVisible: false,
          isActive: false,
          show: () => {},
          hide: () => {},
          enable: () => {},
          disable: () => {},
          showProgress: () => {},
          hideProgress: () => {},
          onClick: () => {},
          offClick: () => {},
          setText: () => {},
        },
        openTelegramLink: () => {},
        openLink: () => {},
      },
    };

    const mockResponse = { id: 1, first_name: "Aziz", language: "uz" };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const user = await api.getMe();
    expect(user).toEqual(mockResponse);

    const callArgs = (globalThis.fetch as any).mock.calls[0];
    const headers = callArgs[1].headers as Headers;
    expect(headers.get("Authorization")).toBe("tma auth_date=123&hash=abc");
    expect(headers.get("X-Telegram-Init-Data")).toBe("auth_date=123&hash=abc");
  });

  it("throws ApiError when response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Invalid or expired Telegram signature" }),
    });

    await expect(api.getMe()).rejects.toThrow(ApiError);
  });

  it("fetches map properties with expected contract fields", async () => {
    const mockMapItems = [
      {
        id: 1,
        latitude: "41.2800",
        longitude: "69.2000",
        price: "90000.00",
        currency: "USD",
        rooms: 2,
        property_type: "apartment",
        listing_type: "sale",
        title: "2 xonali Chilonzor",
        district: "Chilonzor",
        thumbnail_url: "/api/miniapp/v1/properties/1/media/1",
      },
    ];

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockMapItems,
    });

    const items = await api.getMapProperties({
      min_lat: 41.25,
      max_lat: 41.3,
      min_lng: 69.15,
      max_lng: 69.25,
    });

    expect(items).toEqual(mockMapItems);
    expect(items[0]).toHaveProperty("id");
    expect(items[0]).toHaveProperty("latitude");
    expect(items[0]).toHaveProperty("longitude");
    expect(items[0]).toHaveProperty("price");
    expect(items[0]).toHaveProperty("currency");
  });
});
