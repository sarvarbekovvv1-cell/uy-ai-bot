import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi, ApiError, setCsrfToken } from "../api/client";
import type { PropertyCreateInput, PropertyDetail } from "../types";

describe("Admin Property Creation Frontend Integration", () => {
  beforeEach(() => {
    setCsrfToken("test_csrf_token");
    vi.restoreAllMocks();
  });

  it("submits property creation payload with all required fields", async () => {
    const input: PropertyCreateInput = {
      listing_type: "sale",
      property_type: "apartment",
      title: "Chilonzor shinam 3 xona",
      description: "Yaxshi ta'mirlangan xonadon",
      region: "Toshkent",
      district: "Chilonzor",
      address: "Qatortol ko'chasi 10",
      rooms: 3,
      total_area: 75.0,
      living_area: 50.0,
      floor: 4,
      total_floors: 9,
      condition: "renovated",
      construction_type: "G'isht",
      has_furniture: true,
      cadastre_status: "available",
      price: 85000,
      currency: "USD",
      negotiable: false,
      auto_approve: true,
      media_unique_ids: ["media_abc123"],
    };

    const mockCreatedProperty: PropertyDetail = {
      id: 200,
      title: input.title || null,
      description: input.description || null,
      listing_type: input.listing_type,
      property_type: input.property_type,
      status: "approved",
      price: input.price,
      currency: input.currency || "USD",
      region: input.region,
      district: input.district,
      address: input.address,
      rooms: input.rooms,
      total_area: input.total_area,
      living_area: input.living_area || null,
      floor: input.floor || null,
      total_floors: input.total_floors || null,
      condition: input.condition,
      has_furniture: true,
      cadastre_status: "available",
      construction_type: "G'isht",
      negotiable: false,
      rejection_reason: null,
      created_at: "2026-10-26T16:00:00Z",
      approved_at: "2026-10-26T16:00:00Z",
      rejected_at: null,
      media: [
        {
          id: 1,
          file_type: "photo",
          safe_url: "/api/miniapp/v1/properties/media/media_abc123",
          is_main: true,
        },
      ],
      owner: null,
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => mockCreatedProperty,
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await adminApi.createProperty(input);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [path, init] = mockFetch.mock.calls[0];
    expect(path).toBe("/api/admin/v1/properties");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(input);
    expect(result.id).toBe(200);
    expect(result.status).toBe("approved");
    expect(result.media.length).toBe(1);
  });

  it("handles validation error from server on invalid property creation", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Price must be greater than zero." }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(
      adminApi.createProperty({
        listing_type: "sale",
        property_type: "apartment",
        region: "Toshkent",
        district: "Chilonzor",
        address: "Qatortol",
        rooms: 2,
        total_area: 50,
        condition: "renovated",
        price: -100,
      })
    ).rejects.toThrow(ApiError);
  });

  it("uploads property media and parses unique identifier", async () => {
    const file = new File(["fake image content"], "photo.jpg", { type: "image/jpeg" });

    const mockUploadResponse = {
      media_unique_id: "admin_media_deadbeef1234",
      file_type: "photo",
      safe_url: "/api/miniapp/v1/properties/media/admin_media_deadbeef1234",
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => mockUploadResponse,
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await adminApi.uploadPropertyMedia(file);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [path, init] = mockFetch.mock.calls[0];
    expect(path).toBe("/api/admin/v1/properties/upload-media");
    expect(init.method).toBe("POST");
    expect(result.media_unique_id).toBe("admin_media_deadbeef1234");
    expect(result.safe_url).toContain("admin_media_deadbeef1234");
  });
});
